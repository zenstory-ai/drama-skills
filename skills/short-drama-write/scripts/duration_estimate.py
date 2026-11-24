#!/usr/bin/env python3
"""Estimate how long a screenplay runs, using the project's own declared rates.

This reports a number; it never judges one. Without declared rates it still
counts dialogue characters/words and action paragraphs honestly. Parsing runs
directly in memory without any derived JSONL index file; speakers come from
``人物：`` declarations, ``--speaker`` / ``--extra-speaker`` flags, or a
structural-only fallback when neither cast nor ``--speaker`` is supplied.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "short-drama needs Python {}.{} or newer; this interpreter is {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )

VOICED_TAGS = {"VO", "OS"}
SUPPORTED_TAGS = ("VO", "OS", "SFX", "画面文字", "连续性", "转场")
VOICE_TAG_PREFIX = re.compile(r"^\[(?:VO|OS)\]\s*")
MAX_SPEAKER_LENGTH = 40
_EPISODE = r"EP(?:[0-9]{3}|[1-9][0-9]{3,})"
_SCENE = r"SC(?:[0-9]{3}|[1-9][0-9]{3,})"
_WS = r"[ \t\u3000]"

EPISODE_HEADING_RE = re.compile(
    rf"^#{_WS}+(?P<episode>{_EPISODE})(?![0-9])(?!{_WS}*(?:——|[·：:–—-])?{_WS}*SC[0-9])"
    rf"(?:{_WS}*(?:——|[·：:–—-])(?:{_WS}*.+)?|{_WS}+.+)?$"
)
SCENE_HEADING_RE = re.compile(
    rf"^##{_WS}+(?P<scene>(?:[A-Za-z0-9]+-)*?(?P<episode>{_EPISODE})-{_SCENE})"
    rf"(?:{_WS}+|{_WS}*·{_WS}*)(?P<space>内外|内|外){_WS}*·{_WS}*"
    rf"(?P<location>[^\s·](?:.*?[^\s·])?){_WS}*·{_WS}*(?P<time>[^\s·](?:.*[^\s·])?)$"
)
CAST_LINE_RE = re.compile(
    rf"^{_WS}*(?:[-*+]{_WS}+)?(?:人物{_WS}*[：:]|"
    rf"(?P<m>\*\*\*|___|\*\*|__|\*|_)人物(?:{_WS}*(?P=m){_WS}*[：:]|{_WS}*[：:]{_WS}*(?P=m))"
    rf"){_WS}*(?P<body>.*)$"
)
CAST_PLACEHOLDERS = frozenset(
    {
        "无", "暂无", "待定", "待补", "待确认", "待填", "填写", "未定", "略", "空", "未知",
        "tbd", "todo", "tba", "none", "null", "n/a", "na", "nil",
    }
)
_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_FENCE_OPEN_RE = re.compile(r"^[ \t\u3000]{0,3}(`{3,}|~{3,})([^\r\n]*)$")
CLOCK_PREFIX_RE = re.compile(r"^\d{1,2}[:：]\d{2}(?=\D|$)")
_NOT_PREFIX = (
    r"(?!\d{1,2}[:：]\d{2}(?:\D|$))"
    r"(?![A-Za-z][A-Za-z0-9+.-]*://)"
    r"(?!(?:https?|ftp|mailto|file|ws|wss):(?://|\s|$))"
)
URL_SCHEME_NON_SPEAKER_RE = re.compile(r"^(?:https?|ftp|mailto|file|ws|wss)$", re.IGNORECASE)
BARE_INTEGER_RE = re.compile(r"^(?:[0０]+|[1-9１-９]\d*)$")
DISQUALIFYING_SPEAKER_PUNCT_RE = re.compile(r"[，。！？；、,;!?”“’‘\"—…《》<>\[\]【】]")
_SPEAKER_TOKEN = r"[^\s：:（）()\[\]#，。！？；,!?;—]+"
_SPEAKER_LABEL = rf"(?=.{{1,{MAX_SPEAKER_LENGTH}}}(?:{_WS}*[（(]|：|:)){_SPEAKER_TOKEN}(?: {_SPEAKER_TOKEN}){{0,3}}"
_OPTIONAL_CUE = rf"(?:{_WS}*(?:（(?P<cue_fw>[^（）\r\n]+)）|\((?P<cue_hw>[^()\r\n]+)\)))?"
_OPTIONAL_CUE_UNNAMED = rf"(?:{_WS}*(?:（[^（）\r\n]+）|\([^()\r\n]+\)))?"

DIALOGUE_RE = re.compile(
    rf"^{_NOT_PREFIX}(?P<speaker>{_SPEAKER_LABEL}){_OPTIONAL_CUE}：{_WS}*(?P<text>\S[\s\S]*)$"
)
KNOWN_SPEAKER_DIALOGUE_RE = re.compile(
    rf"^{_NOT_PREFIX}(?P<speaker>{_SPEAKER_LABEL}){_OPTIONAL_CUE}[：:]{_WS}*(?P<text>\S[\s\S]*)$"
)
VOICE_TAG_BODY_RE = KNOWN_SPEAKER_DIALOGUE_RE
ASCII_DIALOGUE_RE = re.compile(rf"^{_NOT_PREFIX}{_SPEAKER_LABEL}{_OPTIONAL_CUE_UNNAMED}:{_WS}*\S")
DIALOGUE = re.compile(
    rf"^{_NOT_PREFIX}(?P<who>{_SPEAKER_LABEL})"
    rf"(?:{_WS}*(?:（[^（）\r\n]*）|\([^()\r\n]*\)))?(?P<colon>[：:]){_WS}*(?P<line>\S[\s\S]*)$"
)
TAG_RE = re.compile(r"^\[(?P<tag>VO|OS|SFX|画面文字|连续性|转场)\]\s*(?P<body>\S[\s\S]*)$")
ANY_TAG_RE = re.compile(r"^\[(?P<tag>[^\]\r\n]+)\]")
FULLWIDTH_TAG_RE = re.compile(r"^【(?P<tag>[^】\r\n]+)】(?!\s*(?:（[^（）\r\n]*）|\([^()\r\n]*\))?\s*[：:])")
MALFORMED_TAG_RE = re.compile(r"^\[(?:VO|OS|SFX|画面文字|连续性|转场)(?:\s|：|:)")


# ---------------------------------------------------------------------------
# In-memory screenplay parser
# ---------------------------------------------------------------------------


def _decode_lines(data: bytes) -> list[str]:
    if not data:
        return []
    data.decode("utf-8")
    lines = [raw.decode("utf-8") for raw in data.splitlines()]
    lines[0] = lines[0].removeprefix("\ufeff")
    return lines


def _clean_names(names: Iterable[str] | None) -> frozenset[str]:
    return frozenset(
        " ".join(name.split())
        for name in (names or ())
        if isinstance(name, str) and name.strip()
    )


def _extract_cue(match: re.Match[str]) -> str | None:
    return match.group("cue_fw") or match.group("cue_hw")


def _fence_open(line_text: str) -> tuple[str, int] | None:
    match = _FENCE_OPEN_RE.match(line_text)
    if match is None or (match.group(1)[0] == "`" and "`" in match.group(2)):
        return None
    return match.group(1)[0], len(match.group(1))


def _fence_close(line_text: str, fence_char: str, min_length: int) -> bool:
    return (
        re.match(
            rf"^[ \t\u3000]{{0,3}}{re.escape(fence_char)}{{{min_length},}}[ \t\u3000]*$",
            line_text,
        )
        is not None
    )


def _scan_comment_end(lines: list[str], start_index: int) -> int | None:
    chunks: list[str] = []
    for cursor in range(start_index, len(lines)):
        chunks.append(lines[cursor])
        if "<!--" not in _HTML_COMMENT_RE.sub("", "\n".join(chunks)):
            return cursor
    return None


def _is_placeholder_cast_token(token: str) -> bool:
    return (
        not token
        or token.lower() in CAST_PLACEHOLDERS
        or token.startswith(("【", "[", "<", "〈", "《", "{"))
        or token.endswith(("】", "]", ">", "〉", "》", "}"))
        or (token.startswith("__") and token.endswith("__"))
        or re.fullmatch(r"[-–—.~…？?＊*＿_]+", token) is not None
    )


def _parse_cast_speakers(raw_body: str) -> set[str]:
    """Extract valid speaker names from a ``人物：`` declaration body."""
    cleaned = _HTML_COMMENT_RE.sub("", raw_body).strip()
    previous: str | None = None
    while previous != cleaned:
        previous = cleaned
        cleaned = re.sub(r"（[^（）]*）|\([^()]*\)", "", cleaned)
    cleaned = re.sub(r"[。．；;，,、\s]+$", "", re.sub(r"(?i)\bn\s*/\s*a\b", "", cleaned)).strip()
    if not cleaned or _is_placeholder_cast_token(cleaned):
        return set()
    speakers: set[str] = set()
    for raw_item in re.split(r"[、，,；;｜|/]+|(?<![A-Za-z.\-])\s+(?![A-Za-z])", cleaned):
        normalized = " ".join(re.sub(r"[。．]+$", "", raw_item.strip()).strip().split())
        if (
            not _is_placeholder_cast_token(normalized)
            and len(normalized) <= MAX_SPEAKER_LENGTH
            and DIALOGUE_RE.fullmatch(f"{normalized}：占位") is not None
        ):
            speakers.add(normalized)
    return speakers


def _issue(line_start: int, line_end: int, code: str, message: str) -> dict[str, Any]:
    return {
        "line_start": line_start,
        "line_end": line_end,
        "issue_code": code,
        "severity": "review_required",
        "message": message,
    }


def _looks_like_markdown(text: str) -> bool:
    stripped = text.lstrip()
    return bool(
        stripped.startswith(("#", "```", "~~~", ">", "- ", "* ", "+ "))
        or re.match(r"\d+[.)]\s", stripped)
        or re.fullmatch(r"[-*_]{3,}", stripped)
    )


def _scan_paragraph_end(
    lines: list[str], start_index: int, seen_scene_heading: bool
) -> tuple[int, bool]:
    end_index = start_index
    while True:
        chunk = "\n".join(lines[start_index : end_index + 1])
        if "<!--" in _HTML_COMMENT_RE.sub("", chunk):
            if end_index + 1 >= len(lines):
                return end_index, True
            end_index += 1
            continue
        if end_index + 1 >= len(lines):
            return end_index, False
        next_text = lines[end_index + 1]
        next_stripped = next_text.strip()
        if not next_stripped or next_stripped.startswith("<!--") or _fence_open(next_text) is not None:
            return end_index, False
        next_after = _HTML_COMMENT_RE.sub("", next_text)
        if next_after.strip().startswith("#") or (
            not seen_scene_heading and "<!--" not in next_after and CAST_LINE_RE.match(next_after) is not None
        ):
            return end_index, False
        end_index += 1


_Item = tuple[str, int, int, str, dict[str, Any]]


def _scan_structure(
    lines: list[str], *, cast_as_speaker: bool = False
) -> tuple[list[_Item], list[dict[str, Any]], set[str]]:
    """Scan lines once into non-paragraph blocks, pending paragraphs, structural issues, and cast."""
    items: list[_Item] = []
    issues: list[dict[str, Any]] = []
    declared_cast: set[str] = set()
    episode_id: str | None = None
    scene_id: str | None = None
    seen_scene_heading = False
    at_scene_head = False
    index = 0

    def add_item(kind: str, start: int, end: int, meta: dict[str, Any]) -> None:
        items.append((kind, start + 1, end + 1, "\n".join(lines[start : end + 1]), meta))

    while index < len(lines):
        text = lines[index]
        stripped = text.strip()
        if not stripped:
            index += 1
            continue

        if stripped.startswith("<!--"):
            end_index = _scan_comment_end(lines, index)
            if end_index is None:
                issues.append(_issue(index + 1, len(lines), "malformed_comment", "Markdown 注释缺少闭合的 -->。"))
                break
            raw_text = "\n".join(lines[index : end_index + 1])
            if _HTML_COMMENT_RE.sub("", raw_text).strip():
                at_scene_head = False
                issues.append(_issue(index + 1, end_index + 1, "mixed_comment_content", "注释与正文混写在同一段落，不能机械分块。"))
            else:
                add_item("comment", index, end_index, {"episode_id": episode_id, "scene_id": scene_id, "production": False})
            index = end_index + 1
            continue

        fence = _fence_open(text)
        if fence is not None:
            fence_char, fence_len = fence
            end_index = index + 1
            while end_index < len(lines) and not _fence_close(lines[end_index], fence_char, fence_len):
                end_index += 1
            if end_index >= len(lines):
                issues.append(_issue(index + 1, len(lines), "unsupported_markdown", "代码块缺少闭合围栏。"))
                break
            add_item("code_fence", index, end_index, {"episode_id": episode_id, "scene_id": scene_id, "production": False})
            index = end_index + 1
            continue

        after_closed = _HTML_COMMENT_RE.sub("", text)
        clean_stripped = after_closed.strip()
        if not clean_stripped:
            index += 1
            continue

        if clean_stripped.startswith("#"):
            is_scene = clean_stripped.startswith("##")
            if is_scene:
                seen_scene_heading = True
            if "<!--" in after_closed:
                close_index = _scan_comment_end(lines, index)
                if close_index is None:
                    issues.append(_issue(index + 1, len(lines), "malformed_comment", "Markdown 注释缺少闭合的 -->。"))
                    break
                scene_id = None
                seen_scene_heading = True
                at_scene_head = False
                label = "场景标题" if is_scene else "集标题"
                issues.append(_issue(index + 1, close_index + 1, "mixed_comment_content", f"{label}中混有多行注释，不能机械分块。"))
                index = close_index + 1
                continue
            if is_scene:
                match = SCENE_HEADING_RE.fullmatch(clean_stripped)
                if not match:
                    scene_id, at_scene_head = None, False
                    issues.append(_issue(index + 1, index + 1, "invalid_scene_heading", "场景标题必须为 ## <EP001-SC001> <内|外|内外> · <地点> · <时间/天气>。"))
                elif episode_id and episode_id != match.group("episode"):
                    scene_id, at_scene_head = None, False
                    issues.append(_issue(index + 1, index + 1, "episode_scene_mismatch", "场景 ID 与当前集标题的集 ID 不一致。"))
                else:
                    episode_id, scene_id, at_scene_head = match.group("episode"), match.group("scene"), True
                    add_item(
                        "scene_heading",
                        index,
                        index,
                        {
                            "episode_id": episode_id,
                            "scene_id": scene_id,
                            "space": match.group("space"),
                            "location": match.group("location"),
                            "time_weather": match.group("time"),
                        },
                    )
            else:
                match = EPISODE_HEADING_RE.fullmatch(clean_stripped)
                if match:
                    episode_id, scene_id, seen_scene_heading, at_scene_head = match.group("episode"), None, False, False
                else:
                    scene_id, seen_scene_heading, at_scene_head = None, True, False
                    issues.append(_issue(index + 1, index + 1, "invalid_episode_heading", "集标题必须以 # EP001 开头（EP 加三位数字，超过 EP999 后不补零）。"))
            index += 1
            continue

        if (
            (not seen_scene_heading or (at_scene_head and scene_id is not None))
            and (scene_id is None or not cast_as_speaker)
            and "<!--" not in after_closed
        ):
            cast_match = CAST_LINE_RE.match(after_closed)
            if cast_match is not None:
                declared_cast.update(_parse_cast_speakers(cast_match.group("body")))
                index += 1
                continue

        end_index, unclosed_comment = _scan_paragraph_end(lines, index, seen_scene_heading)
        if unclosed_comment:
            issues.append(_issue(index + 1, len(lines), "malformed_comment", "Markdown 注释缺少闭合的 -->。"))
            break
        at_scene_head = False
        add_item("paragraph", index, end_index, {"episode_id": episode_id, "scene_id": scene_id})
        index = end_index + 1

    return items, issues, declared_cast


def _classify_items(
    items: list[_Item],
    structural_issues: list[dict[str, Any]],
    active_speakers: frozenset[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blocks: list[dict[str, Any]] = []
    issues = list(structural_issues)

    def add_block(kind: str, raw_text: str, meta: Mapping[str, Any], **fields: Any) -> None:
        blocks.append(
            {"kind": kind, "episode_id": meta["episode_id"], "scene_id": meta["scene_id"], "_text": raw_text, **fields}
        )

    for kind, line_start, line_end, raw_text, meta in items:
        if kind != "paragraph":
            blocks.append({"kind": kind, "_text": raw_text, **meta})
            continue
        paragraph = _HTML_COMMENT_RE.sub("", raw_text).strip()
        if meta["scene_id"] is None:
            issues.append(_issue(line_start, line_end, "content_outside_scene", "动作、对白和生产标签只能位于合法场景标题之后。"))
            continue

        p_lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if len(p_lines) > 1:
            later_fw = [m for line in p_lines[1:] if (m := DIALOGUE_RE.fullmatch(line)) is not None]
            later_any = [m for line in p_lines[1:] if (m := KNOWN_SPEAKER_DIALOGUE_RE.fullmatch(line)) is not None]
            if any(m.group("speaker") in active_speakers for m in later_any) or any(
                ASCII_DIALOGUE_RE.match(line) or TAG_RE.fullmatch(line) or ANY_TAG_RE.match(line) or MALFORMED_TAG_RE.match(line)
                for line in p_lines[1:]
            ):
                issues.append(_issue(line_start, line_end, "missing_block_separator", "动作、对白与生产标签之间需要空行，不能把不同语法块合成动作段落。"))
                continue
            if later_fw:
                issues.append(_issue(line_start, line_end, "ambiguous_dialogue_or_action", "冒号前缀不在本次说话者清单中；由 write owner 判断是动作、画面文字还是对白。"))
                continue

        tag_match = TAG_RE.fullmatch(paragraph)
        if tag_match:
            tag, body = tag_match.group("tag"), tag_match.group("body")
            fields: dict[str, Any] = {"tag": tag, "production": True}
            if tag in VOICED_TAGS:
                voice_match = VOICE_TAG_BODY_RE.fullmatch(body)
                if not voice_match:
                    issues.append(_issue(line_start, line_end, "invalid_voice_tag_syntax", f"[{tag}] 写成「[{tag}] 角色（可选提示）：台词」：要有说话者与冒号，提示可用全角或半角括号。"))
                    continue
                fields["speaker"] = voice_match.group("speaker")
                cue = _extract_cue(voice_match)
                if cue:
                    fields["performance_cue"] = cue
            add_block("production_tag", raw_text, meta, **fields)
            continue

        any_tag = ANY_TAG_RE.match(paragraph)
        if any_tag:
            issues.append(_issue(line_start, line_end, "unsupported_production_tag", f"不支持生产标签 [{any_tag.group('tag')}]；仅支持 {', '.join(SUPPORTED_TAGS)}。"))
            continue
        if MALFORMED_TAG_RE.match(paragraph):
            issues.append(_issue(line_start, line_end, "malformed_production_tag", "生产标签缺少闭合的 ]。"))
            continue

        known_dialogue = KNOWN_SPEAKER_DIALOGUE_RE.fullmatch(paragraph)
        if known_dialogue and known_dialogue.group("speaker") in active_speakers:
            add_block("dialogue", raw_text, meta, speaker=known_dialogue.group("speaker"), performance_cue=_extract_cue(known_dialogue), production=False)
            continue
        if DIALOGUE_RE.fullmatch(paragraph):
            issues.append(_issue(line_start, line_end, "ambiguous_dialogue_or_action", "冒号前缀不在本次说话者清单中；由 write owner 判断是动作、画面文字还是对白。"))
            continue
        if ASCII_DIALOGUE_RE.match(paragraph):
            issues.append(_issue(line_start, line_end, "invalid_dialogue_syntax", "未知说话者后不能使用半角冒号 :；请改用全角冒号 ： 或声明说话者。"))
            continue
        if _looks_like_markdown(paragraph):
            issues.append(_issue(line_start, line_end, "unsupported_markdown", "该 Markdown 结构不属于受支持的剧本块。"))
            continue

        fullwidth_tag = FULLWIDTH_TAG_RE.match(paragraph)
        if fullwidth_tag:
            issues.append(_issue(line_start, line_end, "unsupported_production_tag", f"【{fullwidth_tag.group('tag')}】 是生产方言写法，不是本套件的生产标签；受支持的标签是半角 [ ] 加 {', '.join(SUPPORTED_TAGS)}。"))
        add_block("action", raw_text, meta, production=False)

    return blocks, issues


def parse_screenplay(
    data: bytes, speaker_names: Iterable[str] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse UTF-8 screenplay bytes into classified blocks and structural issues."""
    explicit = _clean_names(speaker_names)
    cast_as_speaker = "人物" in explicit
    items, issues, cast_speakers = _scan_structure(_decode_lines(data), cast_as_speaker=cast_as_speaker)
    active = explicit if cast_as_speaker else (explicit | frozenset(cast_speakers))
    return _classify_items(items, issues, active)


def _is_latin_speaker_phrase(name: str) -> bool:
    tokens = name.split()
    if not (1 <= len(tokens) <= 4 and len(name) <= MAX_SPEAKER_LENGTH):
        return False
    has_latin = False
    for ch in name:
        if ch.isspace() or ch in ".-'’" or (ch.isascii() and ch.isdigit()):
            continue
        if ch.isalpha() and "LATIN" in unicodedata.name(ch, ""):
            has_latin = True
            continue
        return False
    return has_latin


def _is_plausible_auto_speaker(candidate: str, occurrences: int) -> bool:
    """Structural-only speaker filter when neither ``人物：`` nor ``--speaker`` is set."""
    name = " ".join(candidate.split())
    if (
        not name
        or len(name) > MAX_SPEAKER_LENGTH
        or name.startswith(("[", "【"))
        or CLOCK_PREFIX_RE.match(name) is not None
        or URL_SCHEME_NON_SPEAKER_RE.fullmatch(name) is not None
        or BARE_INTEGER_RE.fullmatch(name) is not None
        or DISQUALIFYING_SPEAKER_PUNCT_RE.search(name) is not None
    ):
        return False
    if occurrences >= 2 or _is_latin_speaker_phrase(name):
        return True
    return 1 <= len(re.sub(r"[\s.\-·・]", "", name)) <= 6


def _discover_script_speakers(items: list[_Item]) -> frozenset[str]:
    counts: dict[str, int] = {}
    strong: dict[str, int] = {}

    def record(raw: str, is_strong: bool) -> None:
        name = " ".join(raw.split())
        counts[name] = counts.get(name, 0) + 1
        if is_strong:
            strong[name] = strong.get(name, 0) + 1

    for kind, _start, _end, raw_text, meta in items:
        if kind != "paragraph" or meta["scene_id"] is None:
            continue
        paragraph = _HTML_COMMENT_RE.sub("", raw_text).strip()
        p_lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if len(p_lines) > 1 and any(
            KNOWN_SPEAKER_DIALOGUE_RE.fullmatch(line) or ASCII_DIALOGUE_RE.match(line)
            or TAG_RE.fullmatch(line) or ANY_TAG_RE.match(line) or MALFORMED_TAG_RE.match(line)
            for line in p_lines[1:]
        ):
            continue
        tag_match = TAG_RE.fullmatch(paragraph)
        if tag_match and tag_match.group("tag") in VOICED_TAGS:
            voice_match = VOICE_TAG_BODY_RE.fullmatch(tag_match.group("body"))
            if voice_match:
                record(voice_match.group("speaker"), True)
        elif not (tag_match or ANY_TAG_RE.match(paragraph) or MALFORMED_TAG_RE.match(paragraph)):
            if (m := DIALOGUE_RE.fullmatch(paragraph)) is not None:
                record(m.group("speaker"), True)
            elif (m := KNOWN_SPEAKER_DIALOGUE_RE.fullmatch(paragraph)) is not None:
                record(m.group("speaker"), False)

    return frozenset(
        name
        for name, count in counts.items()
        if (strong.get(name, 0) >= 1 or count >= 2) and _is_plausible_auto_speaker(name, count)
    )


def parse_script_blocks(
    screenplay: bytes,
    speakers: Iterable[str] | None = None,
    extra_speakers: Iterable[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse ``screenplay`` directly in memory and return blocks plus review info."""
    explicit, extra = _clean_names(speakers), _clean_names(extra_speakers)
    items, structural_issues, cast_speakers = _scan_structure(
        _decode_lines(screenplay), cast_as_speaker="人物" in (explicit | extra)
    )
    base = frozenset(cast_speakers | explicit) if (speakers is not None or cast_speakers) else _discover_script_speakers(items)
    blocks, issues = _classify_items(items, structural_issues, base | extra)
    review = {
        "review_status": "review_required" if issues else "clean",
        "source_issue_count": len(issues),
        "needs_human_review": bool(issues),
        "issue_codes": sorted({str(issue["issue_code"]) for issue in issues if "issue_code" in issue}),
    }
    return blocks, review


# ---------------------------------------------------------------------------
# Speech counting and duration estimation
# ---------------------------------------------------------------------------

ON_SCREEN_TEXT_TAG = "画面文字"
UNTIMED_TAGS = (ON_SCREEN_TEXT_TAG, "SFX", "转场")
TAG_PREFIX = re.compile(r"^\[[^\]]+\]\s*")
MIN_RATE = 1e-3
_CJK_PUNCT_RE = re.compile(r"[，。！？、；：「」『』《》【】￥…]")
_ASCII_NUMERIC_TOKEN_CUE_RE = re.compile(r"[$€£¢%/!?.]")
WORD_SCRIPTS = ("LATIN", "CYRILLIC", "GREEK")
WORD_JOINERS = frozenset("'’-")


def _strip_comments_and_format_chars(text: str) -> str:
    return "".join(ch for ch in _HTML_COMMENT_RE.sub("", text) if unicodedata.category(ch) != "Cf")


def _spoken_characters(line: str) -> int:
    """Count what is actually voiced: no whitespace, comments, Cf, or directions."""
    return len(re.sub(r"\s", "", re.sub(r"（[^）]*）|\([^)]*\)", "", _strip_comments_and_format_chars(line))))


def _is_word_letter(character: str) -> bool:
    return character.isalpha() and any(script in unicodedata.name(character, "") for script in WORD_SCRIPTS)


def _voiced_units(line: str, *, prefer_words: bool = False) -> tuple[int, int]:
    """What a speaker actually pronounces, as (characters, words)."""
    cleaned = _strip_comments_and_format_chars(line)
    text = "".join(
        ch for ch in unicodedata.normalize("NFC", re.sub(r"（[^）]*）|\([^)]*\)", "", cleaned))
        if unicodedata.category(ch) != "Cf"
    )
    characters = words = 0
    digit_runs: list[int] = []
    position, length = 0, len(text)
    while position < length:
        character = text[position]
        if _is_word_letter(character) or character.isdigit():
            end, has_letter, digits = position, False, 0
            while end < length:
                current = text[end]
                if _is_word_letter(current):
                    has_letter = True
                elif unicodedata.category(current).startswith("M"):
                    pass
                elif current.isdigit():
                    digits += 1
                elif not has_letter and digits > 0 and current in ".," and end + 1 < length and text[end + 1].isdigit():
                    pass
                elif not (current in WORD_JOINERS and end + 1 < length and (_is_word_letter(text[end + 1]) or text[end + 1].isdigit())):
                    break
                end += 1
            if has_letter:
                words += 1
            else:
                digit_runs.append(digits)
            position = end
            continue
        if not character.isspace() and unicodedata.category(character)[0] not in "PMSC":
            characters += 1
        position += 1
    if (words and not characters) or (
        not words and not characters and digit_runs
        and _CJK_PUNCT_RE.search(text) is None
        and (prefer_words or _ASCII_NUMERIC_TOKEN_CUE_RE.search(text) is not None)
    ):
        words += len(digit_runs)
    else:
        characters += sum(digit_runs)
    return characters, words


def _readable_characters(body: str) -> int:
    return sum(1 for ch in re.sub(r"\s", "", _strip_comments_and_format_chars(body)) if unicodedata.category(ch)[0] not in "PC")


def _is_voiced(block: Mapping[str, Any]) -> bool:
    kind = block.get("kind")
    return kind == "dialogue" or (kind == "production_tag" and block.get("tag") in VOICED_TAGS)


def _block_text(screenplay: bytes, block: Mapping[str, Any]) -> str | None:
    """Return the block's text directly, or slice legacy byte spans when present."""
    if "byte_start" in block or "byte_end" in block:
        start, end = block.get("byte_start"), block.get("byte_end")
        if (
            isinstance(start, bool) or isinstance(end, bool)
            or not isinstance(start, int) or not isinstance(end, int)
            or not 0 <= start < end <= len(screenplay)
        ):
            return None
        try:
            return screenplay[start:end].decode("utf-8").removeprefix("\ufeff").strip()
        except UnicodeDecodeError:
            return None
    raw = block.get("_text") if isinstance(block.get("_text"), str) else block.get("text")
    return raw.removeprefix("\ufeff").strip() if isinstance(raw, str) else None


def measure(screenplay: bytes, blocks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Count the timed material from classified screenplay blocks."""
    dialogue_lines = dialogue_characters = voiced_characters = voiced_words = 0
    voiceover_characters = action_paragraphs = tag_lines = on_screen_text_characters = 0
    untimed_lines = dict.fromkeys(UNTIMED_TAGS, 0)
    unreadable_blocks: list[str] = []

    for block in blocks:
        if "record_type" in block and block.get("record_type") != "block":
            continue
        kind = block.get("kind")
        if kind == "action":
            action_paragraphs += 1
            continue
        if not _is_voiced(block):
            if kind == "production_tag":
                tag_lines += 1
                tag = block.get("tag")
                if tag in untimed_lines:
                    untimed_lines[tag] += 1
                if tag == ON_SCREEN_TEXT_TAG:
                    text = _block_text(screenplay, block)
                    if text is None:
                        unreadable_blocks.append(str(block.get("block_id")))
                    else:
                        on_screen_text_characters += _readable_characters(TAG_PREFIX.sub("", _strip_comments_and_format_chars(text).strip()))
            continue

        text = _block_text(screenplay, block)
        if text is None:
            unreadable_blocks.append(str(block.get("block_id")))
            continue
        spoken = DIALOGUE.match(VOICE_TAG_PREFIX.sub("", _strip_comments_and_format_chars(text).strip()))
        if spoken is None:
            unreadable_blocks.append(str(block.get("block_id")))
            continue
        spoken_line, speaker_label = spoken.group("line"), spoken.group("who")
        prefer_words = spoken.group("colon") == ":" or any(_is_word_letter(ch) for ch in speaker_label)
        dialogue_lines += 1
        characters = _spoken_characters(spoken_line)
        dialogue_characters += characters
        chars_v, words_v = _voiced_units(spoken_line, prefer_words=prefer_words)
        voiced_characters += chars_v
        voiced_words += words_v
        if block.get("tag") == "VO":
            voiceover_characters += characters

    counts: dict[str, Any] = {
        "dialogue_lines": dialogue_lines,
        "dialogue_characters": dialogue_characters,
        "voiced_characters": voiced_characters,
        "voiced_words": voiced_words,
        "voiceover_characters": voiceover_characters,
        "action_paragraphs": action_paragraphs,
        "production_tag_lines": tag_lines,
    }
    if any(untimed_lines.values()):
        counts["untimed_tag_lines"] = {tag: num for tag, num in untimed_lines.items() if num}
    if untimed_lines[ON_SCREEN_TEXT_TAG]:
        counts["on_screen_text_characters"] = on_screen_text_characters
    if unreadable_blocks:
        counts["unreadable_blocks"] = sorted(unreadable_blocks)
    return counts


def _rate(value: Any, allow_zero: bool = False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    return 0.0 if (allow_zero and numeric == 0.0) else (numeric if numeric >= MIN_RATE else None)


def declared_rates(project: Mapping[str, Any] | None) -> dict[str, Any]:
    fmt = project.get("format") if isinstance(project, Mapping) else None
    raw_pacing = fmt.get("pacing") if isinstance(fmt, Mapping) else None
    pacing: Mapping[str, Any] = raw_pacing if isinstance(raw_pacing, Mapping) else {}
    per_char = _rate(pacing.get("spoken_characters_per_second"))
    per_word = _rate(pacing.get("spoken_words_per_second"))
    per_action = _rate(pacing.get("seconds_per_action_paragraph"), allow_zero=True)
    usable = (per_char is not None or per_word is not None) and per_action is not None
    return {
        "declared": usable,
        "spoken_characters_per_second": per_char if usable else None,
        "spoken_words_per_second": per_word if usable else None,
        "seconds_per_action_paragraph": per_action if usable else None,
        "on_screen_text_characters_per_second": _rate(pacing.get("on_screen_text_characters_per_second")),
    }


def accepted_vo_share(counts: Mapping[str, Any], project: Mapping[str, Any] | None) -> dict[str, Any] | None:
    authority = project.get("creator_authority") if isinstance(project, Mapping) else None
    profile = authority.get("rhythm_profile") if isinstance(authority, Mapping) else None
    if not isinstance(profile, Mapping) or profile.get("status") != "accepted":
        return None
    ceiling = profile.get("vo_share_max")
    if isinstance(ceiling, bool) or not isinstance(ceiling, (int, float)):
        return None
    ceiling_val = float(ceiling)
    if not (math.isfinite(ceiling_val) and 0.0 <= ceiling_val <= 1.0) or not counts["dialogue_characters"]:
        return None
    share = counts["voiceover_characters"] / counts["dialogue_characters"]
    return {"share": round(share, 3), "vo_share_max": ceiling_val, "over_max": share > ceiling_val} if math.isfinite(share) else None


def estimate(
    screenplay: bytes,
    blocks: Iterable[Mapping[str, Any]],
    project: Mapping[str, Any] | None = None,
    review: Mapping[str, Any] | None = None,
    target_seconds: float | None = None,
) -> dict[str, Any]:
    counts = measure(screenplay, blocks)
    rates = declared_rates(project)
    target: Any = target_seconds
    if target is None and isinstance(project, Mapping) and isinstance(project.get("format"), Mapping):
        target = project["format"].get("target_seconds_per_episode")

    result: dict[str, Any] = {"counts": counts, "rates": rates, "seconds": None, "target_seconds": _rate(target)}
    if (vo_share := accepted_vo_share(counts, project)) is not None:
        result["vo_share"] = vo_share

    issues = (review or {}).get("source_issue_count")
    has_issues = not isinstance(issues, bool) and isinstance(issues, int) and issues > 0
    unreadable = counts.get("unreadable_blocks") or []
    if has_issues or unreadable:
        entry: dict[str, Any] = {
            "index_review_status": (review or {}).get("review_status"),
            "source_issue_count": issues,
            "needs_human_review": True,
            "unreadable_blocks": unreadable,
            "note": "some of this screenplay could not be classified cleanly, so the counts below cover less than the whole text; resolve the parser issues before reading these seconds as the episode's length",
        }
        if (review or {}).get("issue_codes"):
            entry["issue_codes"] = (review or {})["issue_codes"]
        result["incomplete"] = entry

    untimed = dict(counts.get("untimed_tag_lines") or {})
    if rates["declared"] and rates["on_screen_text_characters_per_second"] is not None:
        untimed.pop(ON_SCREEN_TEXT_TAG, None)
        if untimed:
            counts["untimed_tag_lines"] = dict(untimed)
        else:
            counts.pop("untimed_tag_lines", None)
    if untimed:
        untimed_note = (
            "these production tags take screen time that is not in the seconds; declare format.pacing.on_screen_text_characters_per_second to time on-screen text by its readable characters"
            if ON_SCREEN_TEXT_TAG in untimed
            else "these production tags take screen time that is not in the seconds"
        )
        result["untimed"] = {
            "tag_lines": untimed,
            "note": untimed_note,
        }

    if not rates["declared"]:
        suffix = "the counts above are exact for the classified blocks, which is not all of this screenplay" if "incomplete" in result else "the counts above are still exact"
        result["note"] = f"the project declares no format.pacing rates, so seconds cannot be derived; {suffix}"
        return result

    seconds = counts["action_paragraphs"] * rates["seconds_per_action_paragraph"]
    speech = 0.0
    unpriced: dict[str, int] = {}
    for unit, rate_name in (("voiced_characters", "spoken_characters_per_second"), ("voiced_words", "spoken_words_per_second")):
        if not counts[unit]:
            continue
        if rates[rate_name] is None:
            unpriced[unit] = counts[unit]
        else:
            speech += counts[unit] / rates[rate_name]
    seconds += speech
    if unpriced:
        speech_note = (
            "the project declares no rate for this speech, so seconds, speech_seconds and speech_share cover only the priced speech (speech_partial); declare format.pacing.spoken_words_per_second for words and spoken_characters_per_second for characters"
            if speech > 0
            else "the project declares no rate for this speech, so the seconds leave it out; declare format.pacing.spoken_words_per_second for words and spoken_characters_per_second for characters"
        )
        result["untimed_speech"] = {
            "counts": unpriced,
            "note": speech_note,
        }
    reading = rates["on_screen_text_characters_per_second"]
    reading_seconds = counts["on_screen_text_characters"] / reading if (reading is not None and counts.get("on_screen_text_characters")) else None
    if reading_seconds is not None:
        seconds += reading_seconds

    if not math.isfinite(seconds) or not math.isfinite(speech) or (reading_seconds is not None and not math.isfinite(reading_seconds)):
        result["note"] = "declared format.pacing rates overflowed finite duration calculation; check the project's pacing numbers"
        return result

    if reading_seconds is not None:
        result["on_screen_text_seconds"] = round(reading_seconds, 1)
    result["seconds"] = round(seconds, 1)
    if seconds > 0 and (not unpriced or speech > 0) and math.isfinite(share_ratio := speech / seconds):
        result["speech_seconds"] = round(speech, 1)
        result["speech_share"] = round(share_ratio, 2)
        if unpriced:
            result["speech_partial"] = True
    target_val = result["target_seconds"]
    if target_val:
        delta, delta_ratio = seconds - target_val, (seconds - target_val) / target_val
        if math.isfinite(delta) and math.isfinite(delta_ratio):
            result["delta_seconds"] = round(delta, 1)
            result["delta_ratio"] = round(delta_ratio, 3)
            result["note"] = "informational only: the suite sets no tolerance band, because the right spread depends on the project's own scenes"
        else:
            result["note"] = "declared target_seconds overflowed finite delta calculation; check the episode target length"
    else:
        result["note"] = "no format.target_seconds_per_episode is declared, so there is nothing to compare the estimate against; pass --target-seconds for an episode the episode map gives its own length"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Estimate screenplay duration from the project's declared rates.")
    parser.add_argument("screenplay", nargs="?", type=Path, default=None, help="screenplay Markdown path (alternative to --script)")
    parser.add_argument("--script", type=Path, default=None, help="screenplay Markdown path to parse and estimate directly in memory")
    parser.add_argument("--speaker", action="append", default=None, help="explicit speaker whitelist override (repeatable)")
    parser.add_argument("--extra-speaker", action="append", default=None, help="additional speaker label unioned onto declared or discovered speakers (repeatable)")
    parser.add_argument("--project", type=Path, default=None, help="short-drama.json carrying format.pacing, target_seconds_per_episode and, when accepted, creator_authority.rhythm_profile.vo_share_max")
    parser.add_argument("--target-seconds", type=float, default=None, help="this episode's own target length from the episode map; overrides format.target_seconds_per_episode")
    args = parser.parse_args(argv)
    if args.target_seconds is not None and _rate(args.target_seconds) is None:
        raise SystemExit("--target-seconds must be a finite number >= 0.001")
    if args.script is not None and args.screenplay is not None:
        parser.error("pass either --script or positional screenplay, not both")
    source_path = args.script if args.script is not None else args.screenplay
    if source_path is None:
        parser.error("pass --script <剧本.md> or a positional screenplay path")
    if not source_path.is_file():
        raise SystemExit(f"screenplay not found: {source_path}")

    project: dict[str, Any] | None = None
    if args.project is not None:
        if not args.project.is_file():
            raise SystemExit(f"project file not found: {args.project}")
        try:
            loaded_project = json.loads(args.project.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise SystemExit(f"{args.project}: {error}") from error
        if not isinstance(loaded_project, dict):
            raise SystemExit(f"{args.project}: project file must be a JSON object")
        project = loaded_project

    try:
        screenplay = source_path.read_bytes()
        blocks, review = parse_script_blocks(screenplay, speakers=args.speaker, extra_speakers=args.extra_speaker)
    except (OSError, UnicodeDecodeError) as error:
        raise SystemExit(f"{source_path}: {error}") from error

    report = estimate(screenplay, blocks, project, review, args.target_seconds)
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
