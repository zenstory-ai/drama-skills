#!/usr/bin/env python3
"""Build, verify and sample one stable chapter index for a long source novel.

Every stage of source analysis slices the same file. If each stage ran its own
regular expression the slices would disagree, and a chapter analysed under one
boundary would be aggregated under another. This script owns the only slicing
truth: it detects chapter boundaries once, records each span's line range and
character count, and refuses to stay quiet about numbering it cannot explain.

It performs no editorial judgement. Which chapters matter, what they mean and
how they adapt are decisions for the skill workflow, not for this file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Optional

# Creators run these scripts on whatever interpreter their machine provides, so
# an unsupported version must say so instead of failing inside an import.
MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "short-drama-novel-analyze needs Python {}.{} or newer; this interpreter is {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )

SCHEMA_VERSION = "1.0.0-draft"

# Chapter numbers appear as Arabic digits or Chinese numerals. 千 and 两 are
# included because serialized fiction routinely passes 1000 chapters, and
# 第两百章 is as common as 第二百章 in that range.
CHINESE_NUMERALS = "零〇一二三四五六七八九十百千两"
# Books and episodic scripts number their chapters with 章, 回, 集, 话/話, 幕 or 节 —
# but a book that uses 章 for chapters may also use 节 for subsections inside
# them. Matching every unit at once turns those subsections into chapters, so
# the unit is captured here and a single dominant unit is chosen below.
CHAPTER_UNITS = ("章", "回", "集", "话", "話", "幕", "节")
CHAPTER_RE = re.compile(
    r"^[ \t　]*(?:#{1,6}\s+)?[ \t　]*第\s*([0-9]+|["
    + CHINESE_NUMERALS
    + r"]+)\s*(["
    + "".join(CHAPTER_UNITS)
    + r"])[ \t　]*(.*?)[ \t　]*$"
)
MD_HEADING_PREFIX_RE = re.compile(r"^[ \t　]*#{1,6}\s+")
CHINESE_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000}
# A chapter heading is a short standalone line. A body paragraph that happens to
# open with 第三章 — a character recalling what happened back then — otherwise
# becomes a chapter boundary, and the index silently gains a chapter whose span
# starts mid-scene. Generous enough for the long titles serialized fiction uses.
MAX_HEADING_LINE_WIDTH = 50


def chinese_to_int(text: str) -> int | None:
    """Convert 一 / 十五 / 两百零三 / 一零八 / 一千零一 to an int, or None if malformed.

    Returning None rather than raising matters: a heading whose number cannot be
    read must be reported as an unreadable heading, not crash the whole index
    and leave the creator with no boundary table at all.
    """

    if not text:
        return None
    if text.isascii() and text.isdigit():
        return int(text)
    if not any(character in CHINESE_UNITS for character in text):
        if not all(character in CHINESE_DIGITS for character in text):
            return None
        if len(text) == 1:
            return CHINESE_DIGITS[text]
        if "两" in text:
            return None
        return int("".join(str(CHINESE_DIGITS[character]) for character in text))

    total = 0
    current_digit: int | None = None
    last_unit = 10000
    zero_pending = False
    for character in text:
        if character in ("零", "〇"):
            if total == 0 or current_digit is not None or zero_pending:
                return None
            zero_pending = True
        elif character in CHINESE_DIGITS:
            if current_digit is not None:
                return None
            current_digit = CHINESE_DIGITS[character]
        elif character in CHINESE_UNITS:
            unit_val = CHINESE_UNITS[character]
            if unit_val >= last_unit:
                return None
            if total > 0 and not zero_pending and last_unit // unit_val > 10:
                return None
            if current_digit is None:
                if unit_val != 10 or not (
                    (total == 0 and not zero_pending)
                    or (zero_pending and last_unit >= 1000)
                ):
                    return None
                multiplier = 1
            else:
                multiplier = current_digit
            total += multiplier * unit_val
            last_unit = unit_val
            current_digit = None
            zero_pending = False
        else:
            return None
    if zero_pending and current_digit is None:
        return None
    if current_digit is not None:
        if not zero_pending and last_unit >= 100:
            return None
        total += current_digit
    return total


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _visible_width(text: str) -> int:
    """Count characters as a creator counts them, not as bytes."""

    return sum(1 for character in text if not unicodedata.combining(character))


def find_heading_lines(lines: list[str]) -> tuple[list[dict[str, Any]], int]:
    headings: list[dict[str, Any]] = []
    long_lines = 0
    for offset, line in enumerate(lines):
        candidate = line.removeprefix("\ufeff") if offset == 0 else line
        match = CHAPTER_RE.match(candidate)
        if match is None:
            continue
        stripped_heading = MD_HEADING_PREFIX_RE.sub("", candidate).strip()
        if _visible_width(stripped_heading) > MAX_HEADING_LINE_WIDTH:
            long_lines += 1
            continue
        headings.append(
            {
                "line_index": offset,
                "raw": candidate.strip(),
                "number": chinese_to_int(match.group(1)),
                "unit": match.group(2),
                "title": match.group(3).strip(),
            }
        )
    return headings, long_lines


# Two headings are the least that can be a numbering run. One 第三回 inside a
# chapter of dialogue is a character speaking, not a book changing its unit.
MINIMUM_NUMBERING_RUN = 2


def select_chapter_unit(
    headings: list[dict[str, Any]], forced: str | None = None
) -> tuple[str | None, dict[str, int]]:
    """Keep one numbering unit and report what the other units cost.

    A book that writes chapters as 第N章 and subsections as 第N节 has two
    interleaved numbering runs. Accepting both produces duplicate numbers, and a
    duplicate used to switch off every numbering check at once — so the very
    file that needed reporting came back clean.

    The unit is chosen by depth, not by frequency. Choosing the most frequent
    unit inverted every such book, because subsections always outnumber the
    chapters that contain them: a book of 4 章 with 3 节 each was indexed as 12
    chapters of 节, `problems` empty, and every later stage then cut episodes on
    subsection boundaries. `CHAPTER_UNITS` is ordered coarse to fine, so the
    coarsest unit that forms a real numbering run wins, and a book that numbers
    its chapters 第N节 with nothing coarser still works.
    """

    counts = {unit: 0 for unit in CHAPTER_UNITS}
    for heading in headings:
        counts[heading["unit"]] += 1
    if not headings:
        return None, counts
    if forced is not None:
        return forced, {
            unit: count for unit, count in counts.items() if unit != forced and count
        }
    chosen = next(
        (unit for unit in CHAPTER_UNITS if counts[unit] >= MINIMUM_NUMBERING_RUN),
        None,
    )
    if chosen is None:
        # No unit forms a run. Fall back to the most frequent, resolving ties by
        # the declared order so the choice never depends on which heading came
        # first.
        chosen = max(
            CHAPTER_UNITS, key=lambda unit: (counts[unit], -CHAPTER_UNITS.index(unit))
        )
    ignored = {unit: count for unit, count in counts.items() if unit != chosen and count}
    return chosen, ignored


# A contents entry is one line; the next follows immediately or after a blank.
# Chapter prose never packs headings this tightly, so the gap is an absolute
# signal and does not need calibrating against the rest of the file.
CONTENTS_MAX_GAP = 3
CONTENTS_MIN_ENTRIES = 3
# A volume shorter than this is not a volume. Treating every restart as a legal
# multi-volume structure is what let a single stray duplicated heading disable
# numbering validation for an entire book.
MIN_VOLUME_CHAPTERS = 3


def drop_leading_table_of_contents(
    headings: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """Discard a leading contents block, which repeats every chapter heading.

    Density alone is not enough to decide. A median-based threshold breaks
    exactly when the contents block is a large share of all headings, because
    the block then drags the median into its own range and survives the test.

    So the rule is density plus corroboration: a leading run of headings packed
    within `CONTENTS_MAX_GAP` lines is dropped only if the chapter numbers it
    lists reappear among the headings that follow. A contents block always
    duplicates the chapters it indexes; a genuinely dense opening does not.
    Without this the index carries two "第一章" rows and every later stage
    slices at the contents entry, which holds no prose at all.
    """

    if len(headings) < CONTENTS_MIN_ENTRIES * 2:
        return headings, 0
    numbers = [heading["number"] for heading in headings]
    if numbers[0] is None:
        return headings, 0
    # The cut is where numbering restarts: a contents block is followed by the
    # same chapters again. Anchoring on the gap instead is off by one, because
    # the step from the last contents entry to chapter one is itself small.
    cut = 0
    for index in range(1, len(headings)):
        if numbers[index] is not None and numbers[index] <= numbers[0]:
            cut = index
            break
    if cut < CONTENTS_MIN_ENTRIES or cut > len(headings) - cut:
        return headings, 0
    internal_gaps = [
        headings[index + 1]["line_index"] - headings[index]["line_index"]
        for index in range(cut - 1)
    ]
    if any(gap > CONTENTS_MAX_GAP for gap in internal_gaps):
        # Numbering restarts, but the prefix holds real prose between headings.
        # That is a multi-volume book, not a contents block.
        return headings, 0
    dropped = {number for number in numbers[:cut] if number is not None}
    remaining = {number for number in numbers[cut:] if number is not None}
    if not dropped or not dropped <= remaining:
        # The packed prefix indexes chapters that never appear. It is part of
        # the story, not a contents list, so keep it.
        return headings, 0
    return headings[cut:], cut


# Text ahead of the first chapter belongs to no span. A blurb or an author's
# note there is normal and stays under this; a prologue written as prose does
# not, and dropping it silently is how a story's opening went unanalysed.
MAX_TEXT_BEFORE_FIRST_CHAPTER = 500


def text_before_first_chapter(lines: list[str], first_line: int) -> int:
    """Count the characters ahead of `first_line`, minus heading-shaped lines.

    Heading-shaped lines are excluded so a dropped contents block, which sits
    exactly here, does not count as unclaimed prose.
    """

    prefix = lines[: max(first_line - 1, 0)]
    headings, _ = find_heading_lines(prefix)
    heading_lines = {heading["line_index"] for heading in headings}
    return sum(
        _visible_width(line.strip())
        for offset, line in enumerate(prefix)
        if offset not in heading_lines
    )


def text_before_first_chapter_problem(count: int, first_line: int) -> str | None:
    if count <= MAX_TEXT_BEFORE_FIRST_CHAPTER:
        return None
    return (
        f"{count} characters before line {first_line} belong to no chapter; "
        "if this is a prologue, cover it with a leading row starting at line 1"
    )


def build_chapters(
    lines: list[str], headings: list[dict[str, Any]], text: str
) -> list[dict[str, Any]]:
    line_offsets = _line_offsets(lines)
    chapters: list[dict[str, Any]] = []
    for position, heading in enumerate(headings):
        start_line = heading["line_index"]
        end_line = (
            headings[position + 1]["line_index"]
            if position + 1 < len(headings)
            else len(lines)
        )
        body = text[
            line_offsets[start_line] : (
                line_offsets[end_line] if end_line < len(line_offsets) else len(text)
            )
        ]
        chapters.append(
            {
                "sequence": position + 1,
                "source_number": heading["number"],
                "unit": heading["unit"],
                "title": heading["title"],
                "heading": heading["raw"],
                "line_start": start_line + 1,
                "line_end": end_line,
                "char_count": _visible_width(body),
            }
        )
    return chapters


def _line_offsets(lines: list[str]) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line) + 1
    return offsets


def segment_by_restart(chapters: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Split the chapter list wherever source numbering restarts downward.

    Each segment is a candidate volume. Validation then runs *inside* every
    segment, so a book whose volumes restart at 第一章 stays legal while a
    missing or duplicated chapter inside any one volume is still surfaced as a
    warning.
    """

    segments: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    previous: int | None = None
    for chapter in chapters:
        number = chapter["source_number"]
        if number is not None and previous is not None and number < previous:
            segments.append(current)
            current = []
        if number is not None:
            previous = number
        current.append(chapter)
    if current:
        segments.append(current)
    return segments


def _collect_chapter_warnings(
    chapters: list[dict[str, Any]], segments: list[list[dict[str, Any]]]
) -> list[str]:
    warnings: list[str] = []
    for position, segment in enumerate(segments, start=1):
        label = "" if len(segments) == 1 else f" in volume {position}"
        if len(segments) > 1 and len(segment) < MIN_VOLUME_CHAPTERS:
            # Too short to be a volume, so the restart is far more likely to be
            # a duplicated or stray heading than a legal structure.
            warnings.append(
                f"numbering restarts after only {len(segment)} chapter(s) at "
                f"sequence {segment[0]['sequence']}; expected a volume boundary, "
                "check for a stray or duplicated heading"
            )
        numbers = [
            chapter["source_number"]
            for chapter in segment
            if chapter["source_number"] is not None
        ]
        reported_duplicate = False
        reported_gap = False
        for previous, current in zip(numbers, numbers[1:]):
            if current == previous:
                if not reported_duplicate:
                    warnings.append(f"duplicate chapter number {current}{label}")
                    reported_duplicate = True
            elif current != previous + 1:
                if not reported_gap:
                    warnings.append(
                        f"chapter numbering jumps from {previous} to {current}{label}"
                    )
                    reported_gap = True
    empty = [chapter["sequence"] for chapter in chapters if chapter["char_count"] < 50]
    if empty:
        warnings.append(
            "chapters with almost no body text at sequence "
            + ", ".join(str(item) for item in empty[:5])
        )
    return warnings


def validate_chapters(
    chapters: list[dict[str, Any]], segments: list[list[dict[str, Any]]]
) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    if not chapters:
        problems.append("no chapter heading matched; the source may need manual spans")
        return problems, []
    unreadable = [
        chapter["heading"] for chapter in chapters if chapter["source_number"] is None
    ]
    if unreadable:
        problems.append("unreadable chapter numbers: " + ", ".join(unreadable[:5]))
    warnings = _collect_chapter_warnings(chapters, segments)
    return problems, warnings


def _decode_utf8(raw: bytes, path: Path) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        safe_name = str(path).encode("ascii", "backslashreplace").decode("ascii")
        raise UnicodeDecodeError(
            exc.encoding,
            exc.object,
            exc.start,
            exc.end,
            f"{safe_name} is not valid UTF-8 ({exc.reason}); convert the file to UTF-8 "
            "(for example: iconv -f GB18030 -t UTF-8 input.txt > output.txt) before indexing",
        ) from exc


def build_index(source: Path, unit_override: str | None = None) -> dict[str, Any]:
    raw = source.read_bytes()
    text = _decode_utf8(raw, source)
    lines = text.split("\n")
    headings, long_heading_lines = find_heading_lines(lines)
    unit, ignored_units = select_chapter_unit(headings, unit_override)
    headings = [heading for heading in headings if heading["unit"] == unit]
    headings, dropped = drop_leading_table_of_contents(headings)
    chapters = build_chapters(lines, headings, text)
    segments = segment_by_restart(chapters)
    problems, warnings = validate_chapters(chapters, segments)
    first_line = chapters[0]["line_start"] if chapters else 1
    unclaimed = text_before_first_chapter(lines, first_line)
    unclaimed_problem = text_before_first_chapter_problem(unclaimed, first_line)
    if unclaimed_problem:
        problems.append(unclaimed_problem)
    if unit is not None:
        coarser = [
            other
            for other in CHAPTER_UNITS[: CHAPTER_UNITS.index(unit)]
            if ignored_units.get(other)
        ]
        if coarser:
            warnings.append(
                "chapters were indexed as 第N{} while coarser headings were skipped: {}"
                "; pass --unit to choose the unit yourself".format(
                    unit,
                    ", ".join(
                        "第N{} x{}".format(other, ignored_units[other])
                        for other in coarser
                    ),
                )
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "novel_chapter_index",
        "source": {
            "artifact": source.name,
            "char_count": _visible_width(text),
            "line_count": len(lines),
        },
        "chapter_unit": unit,
        # Kept in the record rather than only warned about: a creator whose book
        # numbers chapters as 第N节 needs to see that 章 headings were skipped.
        "ignored_heading_units": ignored_units,
        # Body paragraphs that merely open with a chapter number. Reported rather
        # than silently dropped: if a book genuinely titles its chapters this
        # long, the count is how a creator finds out why chapters went missing.
        "long_heading_lines_skipped": long_heading_lines,
        "contents_entries_dropped": dropped,
        "text_before_first_chapter": unclaimed,
        "volume_numbering_restarts": len(segments) > 1,
        "volume_count": len(segments),
        "chapter_count": len(chapters),
        "chapters": chapters,
        "problems": problems,
        "warnings": warnings,
    }


REQUIRED_CHAPTER_FIELDS = ("sequence", "line_start", "line_end")


def verify_index(index_path: Path, source: Path) -> dict[str, Any]:
    """Re-check an index against its source without trusting either.

    The workflow tells creators to write spans by hand when a source carries no
    headings at all, so this must report a malformed row rather than raise on
    it: an exception here reads as a broken tool, not as a fixable index.
    """

    index = json.loads(_decode_utf8(index_path.read_bytes(), index_path))
    raw = source.read_bytes()
    problems: list[str] = []
    if not isinstance(index, dict):
        return {"verified": False, "problems": ["index must be a JSON object"], "warnings": []}
    source_record = index.get("source")
    if not isinstance(source_record, dict):
        return {
            "verified": False,
            "problems": [
                "index is missing its source record"
            ],
            "warnings": [],
        }
    text = _decode_utf8(raw, source)
    lines = text.split("\n")
    line_offsets = _line_offsets(lines)
    expected_lines = source_record.get("line_count")
    if (
        isinstance(expected_lines, int)
        and not isinstance(expected_lines, bool)
        and expected_lines != len(lines)
    ):
        problems.append(
            f"source line_count is {expected_lines}; current source has {len(lines)} lines"
        )
    expected_chars = source_record.get("char_count")
    actual_total_chars = _visible_width(text)
    if (
        isinstance(expected_chars, int)
        and not isinstance(expected_chars, bool)
        and expected_chars != actual_total_chars
    ):
        problems.append(
            f"source char_count is {expected_chars}; "
            f"current source has {actual_total_chars} characters"
        )
    chapters = index.get("chapters", [])
    if not isinstance(chapters, list) or not chapters:
        return {"verified": False, "problems": ["index carries no chapters"], "warnings": []}
    chapter_count = index.get("chapter_count")
    if (
        isinstance(chapter_count, bool)
        or not isinstance(chapter_count, int)
        or chapter_count != len(chapters)
    ):
        problems.append("chapter_count does not match the chapter rows")
    previous_end: int | None = None
    normalized_chapters: list[dict[str, Any]] = []
    for position, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            problems.append(f"chapter row {position} is not an object")
            continue
        missing = [field for field in REQUIRED_CHAPTER_FIELDS if field not in chapter]
        if missing:
            problems.append(
                f"chapter row {position} is missing {', '.join(missing)}; "
                "a hand-written span must carry the same fields the script writes"
            )
            continue
        sequence = chapter["sequence"]
        start_line, end_line = chapter["line_start"], chapter["line_end"]
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence != position
        ):
            problems.append(
                f"chapter row {position} sequence must be the contiguous value {position}"
            )
            continue
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in (start_line, end_line)
        ):
            problems.append(f"chapter {sequence} line span must use integer line numbers")
            continue
        if not (1 <= start_line <= len(lines)) or not (
            start_line <= end_line <= len(lines)
        ):
            problems.append(
                f"chapter {chapter['sequence']} spans lines "
                f"{start_line}-{end_line}, outside the source's {len(lines)} lines"
            )
            continue
        if previous_end is None:
            unclaimed_problem = text_before_first_chapter_problem(
                text_before_first_chapter(lines, start_line), start_line
            )
            if unclaimed_problem:
                problems.append(unclaimed_problem)
        elif start_line != previous_end + 1:
            problems.append(
                f"chapter {sequence} must start at line {previous_end + 1}; "
                f"found {start_line}"
            )
            continue
        previous_end = end_line
        span_body = text[
            line_offsets[start_line - 1] : (
                line_offsets[end_line] if end_line < len(line_offsets) else len(text)
            )
        ]
        actual_span_chars = _visible_width(span_body)
        first_line = (
            lines[0].removeprefix("\ufeff")
            if start_line == 1
            else lines[start_line - 1]
        )
        actual_heading = first_line.strip()
        raw_heading = chapter.get("heading")
        if isinstance(raw_heading, str) and raw_heading and raw_heading != actual_heading:
            problems.append(
                f"chapter {sequence} heading is {raw_heading!r}; "
                f"line {start_line} now reads {actual_heading!r}"
            )
        raw_number = chapter.get("source_number")
        source_number = (
            raw_number
            if isinstance(raw_number, int) and not isinstance(raw_number, bool)
            else None
        )
        raw_chars = chapter.get("char_count")
        has_int_chars = isinstance(raw_chars, int) and not isinstance(raw_chars, bool)
        if has_int_chars and raw_chars != actual_span_chars:
            problems.append(
                f"chapter {sequence} char_count is {raw_chars}; "
                f"lines {start_line}-{end_line} now have {actual_span_chars} characters"
            )
        char_count = raw_chars if has_int_chars else actual_span_chars
        normalized_chapters.append(
            {
                "sequence": sequence,
                "source_number": source_number,
                "char_count": char_count,
            }
        )
    if previous_end is not None and previous_end != len(lines):
        problems.append(
            f"chapter spans end at line {previous_end}; source ends at line {len(lines)}"
        )
    warnings = (
        _collect_chapter_warnings(
            normalized_chapters, segment_by_restart(normalized_chapters)
        )
        if normalized_chapters
        else []
    )
    recorded_problems = index.get("problems")
    if recorded_problems is not None and not isinstance(recorded_problems, list):
        problems.append("index problems field must be a list")
    elif recorded_problems:
        warnings.append(
            "index still carries non-empty top-level problems from an earlier build; "
            'clear "problems": [] once the spans are resolved'
        )
    return {"verified": not problems, "problems": problems, "warnings": warnings}


# The triage stage reads a fraction of the book. A fixed, explainable count beats
# a formula nobody can predict, and the reported ratio is what stops a triage
# from being mistaken for a full pass.
DEFAULT_SAMPLE_COUNT = 12
# One literal for the stage marker, shared by the function default and the CLI
# flag. Spelling it twice is how the two drift apart, and a drifted default
# reports every chapter as missing while the files sit right there.
DEFAULT_COVERAGE_STAGE = "extract"
KNOWN_COVERAGE_STAGES = ("extract", "triage")


def sample_chapters(index_path: Path, count: int = DEFAULT_SAMPLE_COUNT) -> dict[str, Any]:
    """Choose a reproducible spread of chapters for the adaptation triage.

    Evenly spaced and always including the first and last chapter: the triage
    asks whether a book is worth adapting, and that question is answered by how
    the whole spine behaves, not by how well the opening performs. The selection
    is deterministic so a second run cites the same chapters as the first.
    """

    index = json.loads(_decode_utf8(index_path.read_bytes(), index_path))
    chapters = index.get("chapters", [])
    total = len(chapters)
    if total == 0:
        return {"total_chapters": 0, "sampled": [], "coverage_ratio": 0.0}
    count = max(1, min(count, total))
    if count == 1:
        positions = [0]
    else:
        positions = sorted(
            {round(step * (total - 1) / (count - 1)) for step in range(count)}
        )
    sampled = [
        {
            "sequence": chapters[position]["sequence"],
            "source_number": chapters[position].get("source_number"),
            "title": chapters[position].get("title", ""),
            "line_start": chapters[position]["line_start"],
            "line_end": chapters[position]["line_end"],
        }
        for position in positions
    ]
    return {
        "total_chapters": total,
        "sampled_count": len(sampled),
        "coverage_ratio": round(len(sampled) / total, 4),
        "sampled": sampled,
    }


def coverage(
    index_path: Path,
    analysis_dir: Path,
    stage: str = DEFAULT_COVERAGE_STAGE,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> dict[str, Any]:
    """Report which chapters have no analysis file for one named stage.

    The stage marker is required, not cosmetic. Chapter files for different
    stages live in the same directory, so matching any file that merely contains
    a chapter number lets one stage's output satisfy another stage's gate — and
    the gate that exists to stop a silently skipped chapter then reports a book
    as complete.
    """

    if start is not None and end is not None and start > end:
        raise ValueError(
            f"invalid chapter range: start ({start}) must not exceed end ({end})"
        )
    index = json.loads(_decode_utf8(index_path.read_bytes(), index_path))
    all_sequences = {chapter["sequence"] for chapter in index.get("chapters", [])}
    expected = {
        sequence
        for sequence in all_sequences
        if (start is None or sequence >= start) and (end is None or sequence <= end)
    }
    pattern = re.compile(rf"^ch-(\d+)-{re.escape(stage)}$")
    sibling_stages = tuple(item for item in KNOWN_COVERAGE_STAGES if item != stage)
    sibling_pattern = (
        re.compile(r"^ch-(\d+)-(?:" + "|".join(re.escape(item) for item in sibling_stages) + r")$")
        if sibling_stages
        else None
    )
    found: set[int] = set()
    unmatched: list[str] = []
    dir_exists = analysis_dir.is_dir()
    if dir_exists:
        for path in sorted(analysis_dir.glob("*.md")):
            match = pattern.fullmatch(path.stem)
            if match is not None:
                found.add(int(match.group(1)))
                continue
            if sibling_pattern is not None and sibling_pattern.fullmatch(path.stem) is not None:
                continue
            unmatched.append(path.name)
    missing = sorted(expected - found)
    has_range = start is not None or end is not None
    result: dict[str, Any] = {
        "stage": stage,
        "expected": len(expected),
        "present": len(expected & found),
        "missing": missing,
        "unexpected": sorted(found - (all_sequences if has_range else expected)),
        # Named rather than counted: a file whose name drifted by one character
        # is invisible to the gate, and looks identical to a missing chapter.
        "unmatched_files": unmatched,
        "complete": bool(expected) and dir_exists and not missing and not unmatched,
    }
    if has_range:
        result["range"] = [start, end]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("index", help="build the chapter index for one source")
    build.add_argument("source", type=Path)
    build.add_argument("--out", type=Path, default=None)
    build.add_argument(
        "--unit",
        choices=CHAPTER_UNITS,
        default=None,
        help="force the chapter unit instead of detecting it (章 / 回 / 集 / 话 / 話 / 幕 / 节)",
    )

    check = sub.add_parser("verify", help="re-check an index against its source")
    check.add_argument("index", type=Path)
    check.add_argument("source", type=Path)

    pick = sub.add_parser("sample", help="choose triage chapters spread across the book")
    pick.add_argument("index", type=Path)
    pick.add_argument("--count", type=int, default=DEFAULT_SAMPLE_COUNT)

    cover = sub.add_parser("coverage", help="report chapters with no analysis file")
    cover.add_argument("index", type=Path)
    cover.add_argument("analysis_dir", type=Path)
    cover.add_argument("--stage", default=DEFAULT_COVERAGE_STAGE)
    cover.add_argument("--start", type=int, default=None, help="first chapter sequence in range")
    cover.add_argument("--end", type=int, default=None, help="last chapter sequence in range")

    args = parser.parse_args(argv)

    try:
        if args.command == "index":
            document = build_index(args.source, args.unit)
            payload = json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True)
            if args.out is not None:
                _atomic_write_text(args.out, payload + "\n")
                print(
                    json.dumps(
                        {
                            "chapter_count": document["chapter_count"],
                            "chapter_unit": document["chapter_unit"],
                            "ignored_heading_units": document["ignored_heading_units"],
                            "problems": document["problems"],
                            "warnings": document["warnings"],
                            "out": str(args.out),
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                )
            else:
                print(payload)
            return 1 if document["problems"] else 0

        if args.command == "verify":
            result = verify_index(args.index, args.source)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 0 if result["verified"] else 1

        if args.command == "sample":
            result = sample_chapters(args.index, args.count)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 0 if result["sampled"] else 1

        result = coverage(
            args.index, args.analysis_dir, args.stage, start=args.start, end=args.end
        )
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["complete"] else 1
    except (UnicodeDecodeError, ValueError) as exc:
        reason = exc.reason if isinstance(exc, UnicodeDecodeError) else str(exc)
        message = f"error: {reason}"
        print(message.encode("ascii", "backslashreplace").decode("ascii"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
