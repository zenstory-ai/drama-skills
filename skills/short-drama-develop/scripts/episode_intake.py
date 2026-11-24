#!/usr/bin/env python3
"""Mechanical intake guards for a multi-episode screenplay source.

This tool deliberately does not interpret story content.  It records exact byte
spans once, verifies them before every read, exposes one episode at a time, and
atomically merges agent-authored episode-map records in small configurable
batches.  The episode map remains the completion truth; a progress checkpoint
is only a reproducible derived cache.
"""

from __future__ import annotations

import argparse
from bisect import bisect_left
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "episode_intake.py requires Python {}.{} or newer; found {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )

SCHEMA_VERSION = "1.0.0"
CHINESE_NUMBER = "零〇一二三四五六七八九十百千两"
_HEADING_SEP = r"(?:——|[·：:–—-])"
_HEADING_TAIL = rf"(?:[ \t　]*{_HEADING_SEP}(?:[ \t　]*\S.*)?|[ \t　]+\S.*)?"
_EN_HEADING_SEP = r"(?:——|[·：:–—-]|\.(?=[ \t　]|$))"
_EN_HEADING_TAIL = rf"(?:[ \t　]*{_EN_HEADING_SEP}(?:[ \t　]*\S.*)?|[ \t　]+\S.*)?"
CHINESE_HEADING_RE = re.compile(
    r"^[ \t　]*(?:#{1,6}[ \t　]+)?第\s*([0-9]+|["
    + CHINESE_NUMBER
    + r"]+)\s*集"
    + _HEADING_TAIL
    + r"[ \t　]*$"
)
EP_HEADING_RE = re.compile(
    r"^[ \t　]*(?:#{1,6}[ \t　]+)?(?:EPISODE|EP)[ \t　]*([0-9]+)"
    r"(?![0-9])"
    rf"(?![ \t　]*{_HEADING_SEP}?[ \t　]*SC[0-9])"
    r"(?![ \t　]*[-–—][ \t　]*(?:(?:EPISODE|EP)[ \t　]*)?[0-9]+)"
    + _EN_HEADING_TAIL
    + r"[ \t　]*$",
    re.IGNORECASE,
)
EPISODE_ID_RE = re.compile(r"^EP([0-9]{3}|[1-9][0-9]{3,})$")
MAX_HEADING_LENGTH = 80
_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_FENCE_OPEN_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})(.*)$")
EPISODE_MAP_CORE_KEYS = (
    "episode_id",
    "title",
    "goal",
    "hook",
    "conflict",
    "turn",
    "climax",
    "ending_hook",
    "handoff_state",
    "setup_payoff",
    "locations",
    "characters",
)
EPISODE_MAP_TEXT_KEYS = (
    "title",
    "goal",
    "hook",
    "conflict",
    "turn",
    "climax",
    "ending_hook",
    "handoff_state",
)
EPISODE_MAP_LIST_KEYS = ("setup_payoff", "locations", "characters")
EPISODE_MAP_PLACEHOLDERS = frozenset({"__FILL__"})
SOURCE_SPAN_KEYS = ("source_chapters", "chapter_range", "source_chapter_span", "source_span")
_CHAPTER_RANGE_TOKEN_RE = re.compile(
    r"(?:^|[\s,，、;；])(?:ch-?|第)?(\d+)\s*(?:\.\.|[-–—~至到])\s*(?:ch-?|第)?(\d+)章?(?=$|[\s,，、;；])",
    re.IGNORECASE,
)
_MAX_CHAPTER_RANGE_EXPANSION = 1000


def _is_strict_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _strict_int(value: Any) -> int | None:
    return value if _is_strict_int(value) and isinstance(value, int) else None


# BEGIN SHARED: cn_num
CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000}


def chinese_to_int(text: str) -> int | None:
    """Convert 一 / 十五 / 两百零三 / 两零八 / 一千零十五 to an int, or None if malformed."""
    if not text:
        return None
    if text.isascii() and text.isdigit():
        return int(text)
    if all(character in CHINESE_DIGITS for character in text):
        if "两" in text[1:]:
            return None
        value = 0
        for character in text:
            value = value * 10 + CHINESE_DIGITS[character]
        return value
    if not all(
        character in CHINESE_DIGITS or character in CHINESE_UNITS
        for character in text
    ):
        return None

    total = 0
    previous_weight: int | None = None
    pending_digit: int | None = None
    saw_zero = False

    for index, character in enumerate(text):
        if character in CHINESE_DIGITS:
            digit = CHINESE_DIGITS[character]
            if digit == 0:
                if previous_weight is None or pending_digit is not None or saw_zero:
                    return None
                saw_zero = True
            else:
                if pending_digit is not None:
                    return None
                pending_digit = digit
            continue

        weight = CHINESE_UNITS[character]
        if pending_digit is None:
            if character == "十" and (
                (index == 0 and not saw_zero)
                or (saw_zero and previous_weight is not None and previous_weight >= 1000)
            ):
                digit = 1
            else:
                return None
        else:
            digit = pending_digit
            pending_digit = None

        if previous_weight is not None:
            if weight >= previous_weight:
                return None
            if (previous_weight > weight * 10) != saw_zero:
                return None
        saw_zero = False
        previous_weight = weight
        total += digit * weight

    if pending_digit is None:
        return None if saw_zero else total
    assert previous_weight is not None
    if (previous_weight > 10) != saw_zero:
        return None
    return total + pending_digit
# END SHARED: cn_num


def _line_table(data: bytes) -> tuple[list[bytes], list[int]]:
    data.decode("utf-8")
    lines = data.splitlines(keepends=True)
    if data and (not lines or sum(map(len, lines)) != len(data)):
        raise ValueError("could not construct exact source line table")
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    return lines, offsets


def _fence_open(line_text: str) -> tuple[str, int] | None:
    match = _FENCE_OPEN_RE.match(line_text)
    if match is None:
        return None
    marker, info = match.group(1), match.group(2)
    fence_char = marker[0]
    if fence_char == "`" and "`" in info:
        return None
    return fence_char, len(marker)


def _fence_close(line_text: str, fence_char: str, fence_len: int) -> bool:
    stripped = line_text.rstrip(" \t")
    indent = len(stripped) - len(stripped.lstrip(" "))
    if indent > 3:
        return False
    marker = stripped[indent:]
    return len(marker) >= fence_len and all(ch == fence_char for ch in marker)


def _heading_number_from_text(raw_text: str) -> int | None:
    clean = _HTML_COMMENT_RE.sub("", raw_text)
    if "<!--" in clean:
        return None
    if len(clean.strip()) > MAX_HEADING_LENGTH:
        return None
    match = CHINESE_HEADING_RE.fullmatch(clean)
    if match:
        number = chinese_to_int(match.group(1))
        return number if number and number > 0 else None
    match = EP_HEADING_RE.fullmatch(clean)
    number = int(match.group(1)) if match else None
    return number if number and number > 0 else None


def _heading_number(line: bytes) -> int | None:
    try:
        text = line.decode("utf-8").removeprefix("\ufeff").rstrip("\r\n")
    except UnicodeDecodeError:
        return None
    return _heading_number_from_text(text)


def _episode_id(number: int) -> str:
    if number <= 0:
        raise ValueError("episode numbers must be positive")
    return f"EP{number:03d}"


def _validate_portable_source_ref(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("source_ref must be a portable project-relative path")
    segments = value.split("/")
    candidate = Path(value)
    if (
        candidate.is_absolute()
        or any(segment in {"", ".", ".."} for segment in segments)
        or "://" in value
        or "\\" in value
        or re.match(r"^[A-Za-z]:", value)
    ):
        raise ValueError("source_ref must be a portable project-relative path")
    return candidate.as_posix()


def _portable_source_ref(source: Path, source_ref: str | None) -> str:
    value = source.name if source_ref is None else source_ref
    return _validate_portable_source_ref(value)


def _structural_problems(
    episodes: list[dict[str, Any]], data: bytes, *, manual: bool = False
) -> list[str]:
    problems: list[str] = []
    numbers: list[int] = []
    previous_end = 0
    for position, row in enumerate(episodes, 1):
        if not isinstance(row, dict):
            problems.append(f"episode row {position} is not an object")
            continue
        episode_id = row.get("episode_id")
        match = EPISODE_ID_RE.fullmatch(episode_id) if isinstance(episode_id, str) else None
        if not match:
            problems.append(f"episode row {position} has an invalid episode_id")
            continue
        number = int(match.group(1))
        if number <= 0:
            problems.append(f"episode row {position} has a non-positive episode_id")
            continue
        numbers.append(number)
        source_number = row.get("source_number")
        if not _is_strict_int(source_number) or source_number != number:
            problems.append(f"{row['episode_id']} source_number does not match episode_id")
        if "line_start" in row or "line_end" in row:
            line_start = _strict_int(row.get("line_start"))
            line_end = _strict_int(row.get("line_end"))
            if (
                line_start is None
                or line_end is None
                or not (1 <= line_start <= line_end)
            ):
                problems.append(f"{row['episode_id']} line span does not match its byte span")
        start = _strict_int(row.get("byte_start"))
        end = _strict_int(row.get("byte_end"))
        if start is not None and end is not None and 0 <= start < end <= len(data):
            if "byte_length" in row:
                byte_length = _strict_int(row.get("byte_length"))
                if byte_length is None or byte_length != end - start:
                    problems.append(f"{row['episode_id']} byte_length does not match its byte span")
            if start < previous_end:
                problems.append(f"episode row {position} overlaps or is out of source order")
            previous_end = max(previous_end, end)
            lines = data[start:end].splitlines(keepends=True)
            if manual or not lines or _heading_number(lines[0]) is None:
                if not data[start:end].strip():
                    problems.append(f"empty episode: {row['episode_id']}")
            elif not b"".join(lines[1:]).strip():
                problems.append(f"empty episode: {row['episode_id']}")
        else:
            problems.append(f"episode row {position} has an invalid byte span")
    seen: set[int] = set()
    duplicates: list[int] = []
    for number in numbers:
        if number in seen and number not in duplicates:
            duplicates.append(number)
        seen.add(number)
    if duplicates:
        problems.append("duplicate episode numbers: " + ", ".join(map(str, duplicates)))
    if numbers:
        if numbers != sorted(numbers):
            problems.append("episode numbers are out of source order")
    else:
        problems.append("no episode headings found")
    return problems


def build_index(
    source_path: str | Path, *, source_ref: str | None = None
) -> dict[str, Any]:
    source = Path(source_path)
    data = source.read_bytes()
    lines, offsets = _line_table(data)
    headings: list[tuple[int, int]] = []
    in_comment = False
    fence_state: tuple[str, int] | None = None
    for line_index, line in enumerate(lines):
        raw_text = line.decode("utf-8")
        if line_index == 0:
            raw_text = raw_text.removeprefix("\ufeff")
        raw_text = raw_text.rstrip("\r\n")

        if fence_state is not None:
            if _fence_close(raw_text, fence_state[0], fence_state[1]):
                fence_state = None
            continue

        if in_comment:
            close_idx = raw_text.find("-->")
            if close_idx == -1:
                continue
            raw_text = raw_text[close_idx + 3 :]
            in_comment = False

        after_closed = _HTML_COMMENT_RE.sub("", raw_text)
        opened_fence = _fence_open(raw_text) or _fence_open(after_closed)
        if opened_fence is not None:
            fence_state = opened_fence
            continue

        if "<!--" in after_closed:
            in_comment = True
            continue

        number = _heading_number_from_text(after_closed)
        if number is not None:
            headings.append((line_index, number))
    episodes: list[dict[str, Any]] = []
    for position, (line_index, number) in enumerate(headings):
        next_line = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        start = offsets[line_index]
        end = offsets[next_line]
        episodes.append(
            {
                "episode_id": _episode_id(number),
                "source_number": number,
                "line_start": line_index + 1,
                "line_end": next_line,
                "byte_start": start,
                "byte_end": end,
                "byte_length": end - start,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "episode_intake_index",
        "source_name": source.name,
        "source_ref": _portable_source_ref(source, source_ref),
        "source_byte_length": len(data),
        "episode_count": len(episodes),
        "episodes": episodes,
        "unmapped_spans": _unmapped_spans(episodes, data, offsets),
        "problems": _structural_problems(episodes, data),
    }


def _line_number(offsets: list[int], byte_offset: int, *, end: bool = False) -> int:
    if not _is_strict_int(byte_offset):
        raise ValueError(f"byte offset {byte_offset} is not a line boundary")
    index = bisect_left(offsets, byte_offset)
    if index >= len(offsets) or offsets[index] != byte_offset:
        raise ValueError(f"byte offset {byte_offset} is not a line boundary")
    return index if end else index + 1


def _unmapped_spans(
    episodes: list[dict[str, Any]], data: bytes, offsets: list[int]
) -> list[dict[str, Any]]:
    """Locate meaningful source bytes outside episode spans without copying them."""

    spans: list[dict[str, Any]] = []
    cursor = 0
    ranges = [
        (row.get("byte_start"), row.get("byte_end"))
        for row in episodes
        if isinstance(row, dict)
    ]
    for raw_start, raw_end in ranges:
        start = _strict_int(raw_start)
        end = _strict_int(raw_end)
        if start is None or end is None:
            continue
        if start > cursor and data[cursor:start].strip():
            spans.append(
                {
                    "line_start": _line_number(offsets, cursor),
                    "line_end": _line_number(offsets, start, end=True),
                    "byte_start": cursor,
                    "byte_end": start,
                    "byte_length": start - cursor,
                }
            )
        cursor = max(cursor, end)
    if cursor < len(data) and data[cursor:].strip():
        spans.append(
            {
                "line_start": _line_number(offsets, cursor),
                "line_end": _line_number(offsets, len(data), end=True),
                "byte_start": cursor,
                "byte_end": len(data),
                "byte_length": len(data) - cursor,
            }
        )
    return spans


def make_manual_index(
    source_path: str | Path,
    spans: Iterable[tuple[str, int, int]],
    *,
    source_ref: str | None = None,
) -> dict[str, Any]:
    """Create a verifiable index from agent-selected, line-aligned byte spans.

    This is the escape hatch for nonstandard headings.  The agent chooses the
    boundaries; this function only binds those choices to exact source bytes.
    """

    source = Path(source_path)
    data = source.read_bytes()
    _, offsets = _line_table(data)
    episodes: list[dict[str, Any]] = []
    for episode_id, start, end in spans:
        match = EPISODE_ID_RE.fullmatch(episode_id) if isinstance(episode_id, str) else None
        if not match or int(match.group(1)) <= 0:
            raise ValueError(f"invalid episode_id: {episode_id}")
        if not (_is_strict_int(start) and _is_strict_int(end) and 0 <= start < end <= len(data)):
            raise ValueError(f"invalid byte span for {episode_id}")
        episodes.append(
            {
                "episode_id": episode_id,
                "source_number": int(match.group(1)),
                "line_start": _line_number(offsets, start),
                "line_end": _line_number(offsets, end, end=True),
                "byte_start": start,
                "byte_end": end,
                "byte_length": end - start,
            }
        )
    document = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "episode_intake_index",
        "boundary_mode": "manual",
        "source_name": source.name,
        "source_ref": _portable_source_ref(source, source_ref),
        "source_byte_length": len(data),
        "episode_count": len(episodes),
        "episodes": episodes,
        "unmapped_spans": _unmapped_spans(episodes, data, offsets),
        "problems": [],
    }
    document["problems"] = _structural_problems(episodes, data, manual=True)
    return document


def build_manual_index(
    source_path: str | Path,
    boundaries_path: str | Path,
    *,
    source_ref: str | None = None,
) -> dict[str, Any]:
    """Turn agent-selected one-based line starts into exact verified spans."""

    source = Path(source_path)
    data = source.read_bytes()
    lines, offsets = _line_table(data)
    boundaries = _read_jsonl(Path(boundaries_path))
    if not boundaries:
        raise ValueError("boundaries JSONL must contain at least one episode")
    prepared: list[tuple[str, int, int | None]] = []
    seen: set[str] = set()
    for position, boundary in enumerate(boundaries, 1):
        episode_id = boundary.get("episode_id")
        line_start = _strict_int(boundary.get("line_start"))
        raw_line_end = boundary.get("line_end")
        if not isinstance(episode_id, str):
            raise ValueError(f"boundary {position} has an invalid episode_id")
        match = EPISODE_ID_RE.fullmatch(episode_id)
        if match is None or int(match.group(1)) <= 0:
            raise ValueError(f"boundary {position} has an invalid episode_id")
        if episode_id in seen:
            raise ValueError(f"boundaries contain duplicate episode_id {episode_id}")
        seen.add(episode_id)
        if line_start is None:
            raise ValueError(f"{episode_id} line_start must be an integer")
        line_end: int | None = None
        if raw_line_end is not None:
            line_end = _strict_int(raw_line_end)
            if line_end is None:
                raise ValueError(f"{episode_id} line_end must be an integer")
        prepared.append((episode_id, line_start, line_end))
    spans: list[tuple[str, int, int]] = []
    for position, (episode_id, line_start, explicit_end) in enumerate(prepared):
        if not 1 <= line_start <= len(lines):
            raise ValueError(f"{episode_id} line_start is outside the source")
        next_start = prepared[position + 1][1] if position + 1 < len(prepared) else None
        if next_start is not None and next_start <= line_start:
            raise ValueError("boundary line_start values must be strictly increasing")
        line_end = explicit_end if explicit_end is not None else (
            next_start - 1 if next_start is not None else len(lines)
        )
        if not line_start <= line_end <= len(lines):
            raise ValueError(f"{episode_id} line_end is outside its source span")
        if next_start is not None and line_end >= next_start:
            raise ValueError(f"{episode_id} line_end overlaps the next episode")
        spans.append((episode_id, offsets[line_start - 1], offsets[line_end]))
    return make_manual_index(source, spans, source_ref=source_ref)


def _json_bytes(document: Any) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_index(path: str | Path, document: dict[str, Any]) -> None:
    _atomic_write(Path(path), _json_bytes(document))


def _load_index(index_path: str | Path) -> dict[str, Any]:
    document = json.loads(Path(index_path).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("episodes"), list):
        raise ValueError("index must be a JSON object containing an episodes list")
    return document


def _valid_unmapped_spans(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    int_keys = ("line_start", "line_end", "byte_start", "byte_end", "byte_length")
    return all(
        isinstance(item, dict) and all(_is_strict_int(item.get(key)) for key in int_keys)
        for item in value
    )


def verify_index(index_path: str | Path, source_path: str | Path) -> dict[str, Any]:
    problems: list[str] = []
    try:
        document = _load_index(index_path)
        data = Path(source_path).read_bytes()
        _, offsets = _line_table(data)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        return {"verified": False, "problems": [str(error)]}
    if document.get("schema_version") != SCHEMA_VERSION:
        problems.append("unsupported schema_version")
    if document.get("record_type") != "episode_intake_index":
        problems.append("record_type is not episode_intake_index")
    boundary_mode = document.get("boundary_mode")
    if boundary_mode is not None and boundary_mode not in {"heading", "manual"}:
        problems.append("unsupported boundary_mode")
    manual_mode = boundary_mode == "manual"
    source_byte_length = document.get("source_byte_length")
    if not _is_strict_int(source_byte_length) or source_byte_length != len(data):
        problems.append("source_byte_length does not match")
    try:
        _validate_portable_source_ref(document.get("source_ref"))
    except ValueError as error:
        problems.append(str(error))
    episodes = document["episodes"]
    episode_count = document.get("episode_count")
    if not _is_strict_int(episode_count) or episode_count != len(episodes):
        problems.append("episode_count does not match episodes")
    previous_end = -1
    for position, row in enumerate(episodes, 1):
        if not isinstance(row, dict):
            problems.append(f"episode row {position} is not an object")
            continue
        label = str(row.get("episode_id", f"row {position}"))
        start = _strict_int(row.get("byte_start"))
        end = _strict_int(row.get("byte_end"))
        if (
            start is None
            or end is None
            or not (0 <= start < end <= len(data))
        ):
            problems.append(f"{label} has an invalid byte span")
            continue
        if start < previous_end:
            problems.append(f"{label} overlaps or is out of source order")
        previous_end = end
        try:
            expected_line_start = _line_number(offsets, start)
            expected_line_end = _line_number(offsets, end, end=True)
        except ValueError as error:
            problems.append(f"{label}: {error}")
        else:
            line_start = _strict_int(row.get("line_start"))
            line_end = _strict_int(row.get("line_end"))
            if (
                line_start is None
                or line_end is None
                or line_start != expected_line_start
                or line_end != expected_line_end
            ):
                problems.append(f"{label} line span does not match its byte span")
        byte_length = _strict_int(row.get("byte_length"))
        if byte_length is None or byte_length != end - start:
            problems.append(f"{label} byte_length does not match its byte span")
    problems.extend(_structural_problems(episodes, data, manual=manual_mode))
    if not any("byte span" in problem or "overlaps" in problem for problem in problems):
        try:
            expected_unmapped = _unmapped_spans(episodes, data, offsets)
        except ValueError:
            problems.append("unmapped spans cannot be located in the current source")
        else:
            raw_unmapped = document.get("unmapped_spans")
            if not _valid_unmapped_spans(raw_unmapped) or raw_unmapped != expected_unmapped:
                problems.append("unmapped_spans do not match bytes outside episode spans")
    # Avoid multiplying an identical structural message if a hand-edited index
    # already carried it in its advisory problems field.
    problems = list(dict.fromkeys(problems))
    return {"verified": not problems, "problems": problems}


def _require_verified(index_path: str | Path, source_path: str | Path) -> dict[str, Any]:
    result = verify_index(index_path, source_path)
    if not result["verified"]:
        raise ValueError("index verification failed: " + "; ".join(result["problems"]))
    return _load_index(index_path)


def slice_episode(
    index_path: str | Path,
    source_path: str | Path,
    episode_id: str,
    output_path: str | Path | None = None,
) -> bytes:
    if output_path is not None and Path(output_path).resolve() in {
        Path(index_path).resolve(),
        Path(source_path).resolve(),
    }:
        raise ValueError("slice output must not replace its source or index")
    document = _require_verified(index_path, source_path)
    matches = [row for row in document["episodes"] if row.get("episode_id") == episode_id]
    if len(matches) != 1:
        raise ValueError(f"episode_id must identify exactly one span: {episode_id}")
    data = Path(source_path).read_bytes()
    row = matches[0]
    content = data[row["byte_start"] : row["byte_end"]]
    if output_path is not None:
        _atomic_write(Path(output_path), content)
    return content


def _read_jsonl(path: Path, *, absent_ok: bool = False) -> list[dict[str, Any]]:
    if absent_ok and not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_bytes().splitlines(), 1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"{path}: invalid JSONL line {line_number}: {error}") from error
        if not isinstance(record, dict):
            raise ValueError(f"{path}: JSONL line {line_number} is not an object")
        records.append(record)
    return records


def _episode_number(episode_id: str) -> int:
    match = EPISODE_ID_RE.fullmatch(episode_id)
    if match is None:
        raise ValueError(f"invalid episode_id: {episode_id}")
    return int(match.group(1))


def _validated_records(
    records: list[dict[str, Any]], valid_ids: set[str] | None, label: str
) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for position, record in enumerate(records, 1):
        episode_id = record.get("episode_id")
        if valid_ids is not None:
            if not isinstance(episode_id, str) or episode_id not in valid_ids:
                raise ValueError(f"{label} record {position} has an episode_id outside the index")
        else:
            match = EPISODE_ID_RE.fullmatch(episode_id) if isinstance(episode_id, str) else None
            if match is None or int(match.group(1)) <= 0:
                raise ValueError(f"{label} record {position} has an invalid episode_id")
        assert isinstance(episode_id, str)
        if episode_id in by_id:
            raise ValueError(f"{label} contains duplicate episode_id {episode_id}")
        by_id[episode_id] = record
    return by_id


def _jsonl_bytes(records: Iterable[dict[str, Any]]) -> bytes:
    return b"".join(_json_bytes(record) for record in records)


def progress(
    index_path: str | Path,
    source_path: str | Path,
    map_path: str | Path,
    checkpoint_path: str | Path | None = None,
    *,
    batch_size: int,
) -> dict[str, Any]:
    if not _is_strict_int(batch_size) or batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if checkpoint_path is not None and Path(checkpoint_path).resolve() in {
        Path(index_path).resolve(),
        Path(source_path).resolve(),
        Path(map_path).resolve(),
    }:
        raise ValueError("checkpoint must not replace the index, source, or episode-map")
    document = _require_verified(index_path, source_path)
    ordered_ids = [row["episode_id"] for row in document["episodes"]]
    records = _read_jsonl(Path(map_path), absent_ok=True)
    by_id = _validated_records(records, None, "episode-map")
    completed = [episode_id for episode_id in ordered_ids if episode_id in by_id]
    pending = [episode_id for episode_id in ordered_ids if episode_id not in by_id]
    checkpoint = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "episode_intake_progress",
        "completed": completed,
        "pending": pending,
        "next_batch": pending[:batch_size],
        "complete": not pending,
    }
    if checkpoint_path is not None:
        _atomic_write(Path(checkpoint_path), _json_bytes(checkpoint))
    return checkpoint


def merge_batch(
    index_path: str | Path,
    source_path: str | Path,
    batch_path: str | Path,
    current_map_path: str | Path,
    output_path: str | Path,
    checkpoint_path: str | Path | None = None,
    *,
    batch_size: int,
) -> dict[str, Any]:
    if not _is_strict_int(batch_size) or batch_size <= 0:
        raise ValueError("batch_size must be positive")
    protected = {
        Path(index_path).resolve(),
        Path(source_path).resolve(),
        Path(batch_path).resolve(),
    }
    current_map = Path(current_map_path)
    output = Path(output_path)
    if current_map.resolve() in protected:
        raise ValueError("current episode-map must not replace an index or source input")
    if output.resolve() in {*protected, current_map.resolve()}:
        raise ValueError("merged output must be separate from every input")
    if checkpoint_path is not None and Path(checkpoint_path).resolve() in {
        *protected,
        current_map.resolve(),
        output.resolve(),
    }:
        raise ValueError("checkpoint must not replace an input or merged output")
    document = _require_verified(index_path, source_path)
    ordered_ids = [row["episode_id"] for row in document["episodes"]]
    valid_ids = set(ordered_ids)
    batch_records = _read_jsonl(Path(batch_path))
    if len(batch_records) > batch_size:
        raise ValueError(f"batch contains {len(batch_records)} records; maximum is {batch_size}")
    batch = _validated_records(batch_records, valid_ids, "batch")
    existing_records = _read_jsonl(current_map, absent_ok=True)
    existing = _validated_records(existing_records, None, "episode-map")
    added: list[str] = []
    updated: list[str] = []
    for episode_id, record in batch.items():
        if episode_id in existing:
            if _json_bytes(existing[episode_id]) != _json_bytes(record):
                existing[episode_id] = record
                updated.append(episode_id)
        else:
            existing[episode_id] = record
            added.append(episode_id)
    merged_records = [
        existing[episode_id]
        for episode_id in sorted(existing, key=_episode_number)
    ]
    _atomic_write(output, _jsonl_bytes(merged_records))
    derived = progress(
        index_path,
        source_path,
        output,
        checkpoint_path,
        batch_size=batch_size,
    )
    return {
        "output": str(output),
        "added": [episode_id for episode_id in ordered_ids if episode_id in set(added)],
        "updated": [episode_id for episode_id in ordered_ids if episode_id in set(updated)],
        "progress": derived,
    }


def _extract_chapter_refs(value: Any) -> tuple[bool, list[int]]:
    """Return ``(is_empty, chapter_numbers)`` for an optional source chapter span value."""
    if value is None:
        return True, []
    if _is_strict_int(value):
        assert isinstance(value, int)
        return False, [value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return True, []
        refs: list[int] = []
        covered_spans: list[tuple[int, int]] = []
        for match in _CHAPTER_RANGE_TOKEN_RE.finditer(stripped):
            start_num, end_num = int(match.group(1)), int(match.group(2))
            covered_spans.append(match.span())
            if start_num <= end_num and end_num - start_num <= _MAX_CHAPTER_RANGE_EXPANSION:
                refs.extend(range(start_num, end_num + 1))
            else:
                refs.extend([start_num, end_num])
        for match in re.finditer(r"\d+", stripped):
            pos = match.start()
            if any(span_start <= pos < span_end for span_start, span_end in covered_spans):
                continue
            refs.append(int(match.group(0)))
        return False, refs
    if isinstance(value, list):
        if not value:
            return True, []
        refs = []
        any_non_empty = False
        for item in value:
            item_empty, item_refs = _extract_chapter_refs(item)
            if not item_empty:
                any_non_empty = True
                refs.extend(item_refs)
        return (not any_non_empty), refs
    if isinstance(value, dict):
        if not value:
            return True, []
        start_val = _strict_int(value.get("start"))
        end_val = _strict_int(value.get("end"))
        if start_val is None or end_val is None:
            start_val = _strict_int(value.get("chapter_start"))
            end_val = _strict_int(value.get("chapter_end"))
        if start_val is not None and end_val is not None:
            if start_val <= end_val and end_val - start_val <= _MAX_CHAPTER_RANGE_EXPANSION:
                return False, list(range(start_val, end_val + 1))
            return False, [start_val, end_val]
        if "chapters" in value:
            return _extract_chapter_refs(value["chapters"])
        return False, []
    return False, []


def _load_novel_chapter_ids(novel_index_path: Path) -> set[int]:
    document = json.loads(novel_index_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("chapters"), list):
        raise ValueError("novel index must be a JSON object containing a chapters list")
    chapter_ids: set[int] = set()
    for chapter in document["chapters"]:
        if not isinstance(chapter, dict):
            continue
        seq = _strict_int(chapter.get("sequence"))
        if seq is not None:
            chapter_ids.add(seq)
        src_num = _strict_int(chapter.get("source_number"))
        if src_num is not None:
            chapter_ids.add(src_num)
    return chapter_ids


def check_episode_map(
    map_path: str | Path,
    *,
    novel_index_path: str | Path | None = None,
) -> dict[str, Any]:
    """Deterministically validate ``episode-map.jsonl`` syntax, IDs, core schema, and spans."""
    try:
        records = _read_jsonl(Path(map_path))
    except (OSError, UnicodeError, ValueError) as error:
        return {
            "valid": False,
            "episode_count": 0,
            "episode_ids": [],
            "problems": [str(error)],
            "warnings": [],
        }

    known_chapters: set[int] | None = None
    if novel_index_path is not None:
        try:
            known_chapters = _load_novel_chapter_ids(Path(novel_index_path))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            return {
                "valid": False,
                "episode_count": len(records),
                "episode_ids": [],
                "problems": [str(error)],
                "warnings": [],
            }

    if not records:
        return {
            "valid": False,
            "episode_count": 0,
            "episode_ids": [],
            "problems": ["episode-map is empty"],
            "warnings": [],
        }

    problems: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    episode_ids: list[str] = []
    episode_numbers: list[tuple[int, str]] = []
    span_keys_seen: list[str] = []
    missing_span_rows: list[str] = []

    for position, record in enumerate(records, 1):
        raw_id = record.get("episode_id")
        match = EPISODE_ID_RE.fullmatch(raw_id) if isinstance(raw_id, str) else None
        if match is None or int(match.group(1)) <= 0:
            label = f"record {position}"
            problems.append(f"{label}: invalid episode_id {raw_id!r}")
        else:
            assert isinstance(raw_id, str)
            label = raw_id
            number = int(match.group(1))
            if raw_id in seen_ids:
                problems.append(f"duplicate episode_id: {raw_id}")
            else:
                seen_ids.add(raw_id)
            episode_ids.append(raw_id)
            episode_numbers.append((number, raw_id))

        missing = [key for key in EPISODE_MAP_CORE_KEYS if key not in record]
        if missing:
            problems.append(f"{label}: missing required keys: {', '.join(missing)}")

        for key in EPISODE_MAP_TEXT_KEYS:
            if key not in record:
                continue
            value = record[key]
            if not isinstance(value, str):
                problems.append(f"{label}: {key} must be a string")
            elif value.strip() in EPISODE_MAP_PLACEHOLDERS:
                problems.append(f"{label}: {key} contains unfilled placeholder {value.strip()!r}")
            elif not value.strip():
                warnings.append(f"{label}: {key} is empty")

        for key in EPISODE_MAP_LIST_KEYS:
            if key not in record:
                continue
            value = record[key]
            if not isinstance(value, list):
                problems.append(f"{label}: {key} must be a list")
            elif key in {"locations", "characters"} and not value:
                warnings.append(f"{label}: {key} is empty")

        present_span_keys = [key for key in SOURCE_SPAN_KEYS if key in record]
        if present_span_keys:
            for span_key in present_span_keys:
                if span_key not in span_keys_seen:
                    span_keys_seen.append(span_key)
                is_empty, chapter_refs = _extract_chapter_refs(record[span_key])
                if is_empty:
                    warnings.append(f"{label}: empty source chapter span ({span_key})")
                elif known_chapters is not None and chapter_refs:
                    unknown = sorted({num for num in chapter_refs if num not in known_chapters})
                    if unknown:
                        warnings.append(
                            f"{label}: source chapter(s) not found in novel index: "
                            + ", ".join(map(str, unknown))
                        )
        else:
            missing_span_rows.append(label)

    for (prev_num, prev_id), (curr_num, curr_id) in zip(episode_numbers, episode_numbers[1:]):
        if curr_num < prev_num:
            problems.append(f"episode_id out of order: {curr_id} follows {prev_id}")
        elif curr_num > prev_num + 1:
            warnings.append(f"episode numbering jumps from {prev_id} to {curr_id}")

    if novel_index_path is not None:
        for label in missing_span_rows:
            warnings.append(
                f"{label}: unlinked source chapter span (no source_chapters / chapter_range field)"
            )
    elif span_keys_seen and missing_span_rows:
        declared = ", ".join(span_keys_seen)
        for label in missing_span_rows:
            warnings.append(
                f"{label}: unlinked source chapter span (other episodes declare {declared})"
            )

    problems = list(dict.fromkeys(problems))
    warnings = list(dict.fromkeys(warnings))
    return {
        "valid": not problems,
        "episode_count": len(records),
        "episode_ids": episode_ids,
        "problems": problems,
        "warnings": warnings,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Byte-accurate multi-episode screenplay intake guard")
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index")
    index.add_argument("source", type=Path)
    index.add_argument("--out", type=Path, required=True)
    index.add_argument("--source-ref")
    manual = commands.add_parser("manual-index")
    manual.add_argument("source", type=Path)
    manual.add_argument("boundaries", type=Path)
    manual.add_argument("--out", type=Path, required=True)
    manual.add_argument("--source-ref")
    verify = commands.add_parser("verify")
    verify.add_argument("index", type=Path)
    verify.add_argument("source", type=Path)
    slice_command = commands.add_parser("slice")
    slice_command.add_argument("index", type=Path)
    slice_command.add_argument("source", type=Path)
    slice_command.add_argument("episode_id")
    slice_command.add_argument("--out", type=Path, required=True)
    status = commands.add_parser("progress", aliases=["status"])
    status.add_argument("index", type=Path)
    status.add_argument("source", type=Path)
    status.add_argument("episode_map", type=Path)
    status.add_argument("--checkpoint", type=Path)
    status.add_argument("--batch-size", type=int, required=True)
    merge = commands.add_parser("merge")
    merge.add_argument("index", type=Path)
    merge.add_argument("source", type=Path)
    merge.add_argument("batch", type=Path)
    merge.add_argument("current_episode_map", type=Path)
    merge.add_argument("--out", type=Path, required=True)
    merge.add_argument("--checkpoint", type=Path)
    merge.add_argument("--batch-size", type=int, required=True)
    check_map = commands.add_parser("check-map", help="validate episode-map.jsonl syntax, IDs, and core keys")
    check_map.add_argument("episode_map", type=Path)
    check_map.add_argument("--novel-index", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command in {"index", "manual-index"}:
            if args.source.resolve() == args.out.resolve():
                raise ValueError("index output must not replace its source")
            if args.command == "manual-index" and args.boundaries.resolve() == args.out.resolve():
                raise ValueError("index output must not replace its boundaries input")
            document = (
                build_index(args.source, source_ref=args.source_ref)
                if args.command == "index"
                else build_manual_index(
                    args.source,
                    args.boundaries,
                    source_ref=args.source_ref,
                )
            )
            write_index(args.out, document)
            result: Any = {"output": str(args.out), "episode_count": document["episode_count"]}
            if document["unmapped_spans"]:
                result["warnings"] = [
                    f"{len(document['unmapped_spans'])} unmapped span(s) outside episode boundaries; "
                    "inspect unmapped_spans in the index"
                ]
            if document["problems"]:
                result["problems"] = document["problems"]
                print(json.dumps(result, sort_keys=True))
                return 2
        elif args.command == "verify":
            result = verify_index(args.index, args.source)
            if not result["verified"]:
                print(json.dumps(result, sort_keys=True), file=sys.stderr)
                return 1
        elif args.command == "slice":
            content = slice_episode(args.index, args.source, args.episode_id, args.out)
            result = {"output": str(args.out), "episode_id": args.episode_id, "byte_length": len(content)}
        elif args.command in {"progress", "status"}:
            result = progress(args.index, args.source, args.episode_map, args.checkpoint, batch_size=args.batch_size)
        elif args.command == "check-map":
            result = check_episode_map(args.episode_map, novel_index_path=args.novel_index)
            if not result["valid"]:
                print(json.dumps(result, sort_keys=True), file=sys.stderr)
                return 1
        else:
            result = merge_batch(
                args.index,
                args.source,
                args.batch,
                args.current_episode_map,
                args.out,
                args.checkpoint,
                batch_size=args.batch_size,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
