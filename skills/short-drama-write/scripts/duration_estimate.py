#!/usr/bin/env python3
"""Estimate how long a screenplay runs, using the project's own declared rates.

This reports a number; it never judges one. The suite carries no cross-project
speech rate and no tolerance band, because a 90-second episode of dense argument
and a 90-second episode of silent work do not convert at the same ratio. The
creator declares the two rates their project actually uses, and this script
applies them.

Without declared rates the script still counts dialogue characters and action
paragraphs -- those counts are facts about the text -- and says the seconds
cannot be derived yet. That is the honest output, not a guess from a default.

What counts as a line and what counts as a paragraph is decided by the
``screenplay_index`` parser, never by a separate ad-hoc grammar here. In
``--script`` mode this script parses ``剧本.md`` directly in memory through
``screenplay_index`` (auto-discovering speakers or honoring ``人物：`` /
``--extra-speaker`` / ``--speaker``), and in ``--index`` mode it reads a prebuilt
``screenplay-index.jsonl`` (and also honors ``--speaker`` / ``--extra-speaker``
speaker overrides after verifying the index matches the screenplay bytes).
Sharing the single parser keeps ``[VO]``/``[OS]`` lines, Markdown comments,
fenced code blocks, colon-bearing action prose, and multi-line action paragraphs
classified identically across estimation and indexing.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping


# Creators run these scripts on whatever interpreter their machine provides, so
# an unsupported version must say so instead of failing inside an import.
MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "short-drama needs Python {}.{} or newer; this interpreter is {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )


# [VO] and [OS] are spoken off-camera. The format contract writes them as
# ``[VO] 角色：台词`` -- a real line. Timing them at zero silently shortens every
# episode that carries its interiority in voice-over, and the estimate then reads
# as a deficit the writer pads to fill.
VOICED_TAGS = {"VO", "OS"}
VOICE_TAG_PREFIX = re.compile(r"^\[(?:VO|OS)\]\s*")
MAX_SPEAKER_LENGTH = 40
_WS = r"[ \t\u3000]"
_SPEAKER_TOKEN = r"[^\s：:（）()\[\]#，。！？；,!?;—]+"
_SPEAKER_LABEL = (
    rf"(?=.{{1,{MAX_SPEAKER_LENGTH}}}(?:{_WS}*[（(]|：|:))"
    rf"{_SPEAKER_TOKEN}(?: {_SPEAKER_TOKEN}){{0,3}}"
)
# ``角色（提示）：台词`` or ``Dr. Lin (quietly): ...`` -- the speaker label may
# carry a parenthesised direction in full-width or ASCII parens. Only the
# spoken half is timed; the direction is a note to the performer.
_NOT_CLOCK_PREFIX = r"(?!\d{1,2}[:：]\d{2}(?:\D|$))"
_NOT_URL_PREFIX = r"(?![A-Za-z][A-Za-z0-9+.-]*://)(?!(?:https?|ftp|mailto|file|ws|wss):(?://|\s|$))"
_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
DIALOGUE = re.compile(
    rf"^{_NOT_CLOCK_PREFIX}{_NOT_URL_PREFIX}(?P<who>{_SPEAKER_LABEL})"
    rf"(?:{_WS}*(?:（[^（）\r\n]*）|\([^()\r\n]*\)))?(?P<colon>[：:]){_WS}*(?P<line>\S[\s\S]*)$"
)

_SCREENPLAY_INDEX_MODULE: ModuleType | None = None


def _load_screenplay_index() -> ModuleType:
    global _SCREENPLAY_INDEX_MODULE
    if _SCREENPLAY_INDEX_MODULE is not None:
        return _SCREENPLAY_INDEX_MODULE
    script_path = Path(__file__).resolve().with_name("screenplay_index.py")
    spec = importlib.util.spec_from_file_location(
        "_short_drama_write_screenplay_index", script_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load screenplay_index.py from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _SCREENPLAY_INDEX_MODULE = module
    return module


CAST_LINE_RE = re.compile(
    rf"^{_WS}*(?:[-*+]{_WS}+)?(?:"
    rf"人物{_WS}*[：:]"
    rf"|\*\*\*人物(?:{_WS}*\*\*\*{_WS}*[：:]|{_WS}*[：:]{_WS}*\*\*\*)"
    rf"|___人物(?:{_WS}*___{_WS}*[：:]|{_WS}*[：:]{_WS}*___)"
    rf"|\*\*人物(?:{_WS}*\*\*{_WS}*[：:]|{_WS}*[：:]{_WS}*\*\*)"
    rf"|__人物(?:{_WS}*__{_WS}*[：:]|{_WS}*[：:]{_WS}*__)"
    rf"|\*人物(?:{_WS}*\*{_WS}*[：:]|{_WS}*[：:]{_WS}*\*)"
    rf"|_人物(?:{_WS}*_{_WS}*[：:]|{_WS}*[：:]{_WS}*_)"
    rf"){_WS}*(?P<body>.*)$"
)
CLOCK_PREFIX_RE = re.compile(r"^\d{1,2}[:：]\d{2}(?=\D|$)")
URL_SCHEME_NON_SPEAKER_RE = re.compile(
    r"^(?:https?|ftp|mailto|file|ws|wss)$", re.IGNORECASE
)
PANEL_OR_UNIT_LABEL_RE = re.compile(
    r"^第[一二三四五六七八九十百千万零〇两\d]+[格幕场镜回章集节拍]$"
)
ACTION_PROSE_MARKER_RE = re.compile(
    r"^(?:[他她它](?:们)?|[我你]们|这(?:里|边|儿|个|行|张|份|句|段|块|台|扇|道|声|下|时|一刻)?|"
    r"那(?:里|边|儿|个|头|行|张|份|句|段|块|台|扇|道|声|下|时|一刻)).+"
    r"|(?:写下|写着|写道|写有|写明|印着|印有|刻着|刻有|贴着|标着|标明|"
    r"显示|弹出|跳出|浮现|亮起|亮出|映出|注明|"
    r"看到|看见|看清|看向|盯着|望着|瞥见|瞧见|"
    r"听到|听见|传来|响起|"
    r"走到|走向|走近|转身|转头|回头|抬头|低头|伸手|抬手|"
    r"拿起|拿出|握住|按下|推开|拉开|打开|翻开|掀开|"
    r"意思是|内容是|内容为|如下所示)"
)
NUMERIC_NON_SPEAKER_RE = re.compile(
    r"^(?:[0０]+|[1-9１-９]\d*)$"
    r"|\d+\s*(?:年|月|日|点|时|分|秒|分钟|小时|天|周|星期|礼拜|个|名|位|条|行|句|页|张|份|次|遍|轮|集|场|幕|镜|格|拍|步|章|节|元|块|万|亿|%|％)"
)
DISQUALIFYING_SPEAKER_PUNCT_RE = re.compile(
    r"[，。！？；、,;!?”“’‘\"—…《》<>\[\]【】]"
)
SPEAKER_PARTICLE_RE = re.compile(r"[的了着过]")


def _declared_script_speakers(
    lines: list[dict[str, Any]],
) -> tuple[bool, set[str]]:
    idx = _load_screenplay_index()
    declared: tuple[bool, set[str]] = idx._declared_script_speakers(lines)
    return declared


def _is_latin_speaker_phrase(name: str) -> bool:
    tokens = name.split()
    if not (1 <= len(tokens) <= 4 and len(name) <= MAX_SPEAKER_LENGTH):
        return False
    has_latin = False
    for character in name:
        if character.isspace() or character in ".-'’" or (
            character.isascii() and character.isdigit()
        ):
            continue
        if character.isalpha() and "LATIN" in unicodedata.name(character, ""):
            has_latin = True
            continue
        return False
    return has_latin


def _is_plausible_auto_speaker(candidate: str, occurrences: int) -> bool:
    name = " ".join(candidate.split())
    if not name or len(name) > MAX_SPEAKER_LENGTH or name.startswith(("[", "【")):
        return False
    if URL_SCHEME_NON_SPEAKER_RE.fullmatch(name) is not None:
        return False
    if PANEL_OR_UNIT_LABEL_RE.fullmatch(name) is not None:
        return False
    if NUMERIC_NON_SPEAKER_RE.search(name) is not None:
        return False
    if DISQUALIFYING_SPEAKER_PUNCT_RE.search(name) is not None:
        return False
    if ACTION_PROSE_MARKER_RE.search(name) is not None:
        return False
    if occurrences >= 2:
        return True
    if _is_latin_speaker_phrase(name):
        return True
    clean_chars = re.sub(r"[\s.\-·・]", "", name)
    return (
        1 <= len(clean_chars) <= 6
        and SPEAKER_PARTICLE_RE.search(name) is None
    )


def _discover_script_speakers(idx: ModuleType, screenplay: bytes) -> frozenset[str]:
    screenplay.decode("utf-8")
    lines = idx._line_table(screenplay)
    has_cast_line, cast_speakers = _declared_script_speakers(lines)
    if has_cast_line:
        return frozenset(cast_speakers)
    counts: dict[str, int] = {}
    fw_or_voice_counts: dict[str, int] = {}
    episode_id: str | None = None
    scene_id: str | None = None
    seen_scene_heading = False
    at_scene_head = False
    cursor = 0
    while cursor < len(lines):
        raw_text = lines[cursor]["text"]
        stripped = raw_text.strip()
        if not stripped:
            cursor += 1
            continue
        if stripped.startswith("<!--"):
            end_comment = idx._scan_comment_end(lines, cursor)
            if end_comment is None:
                break
            chunk = "\n".join(lines[i]["text"] for i in range(cursor, end_comment + 1))
            if _HTML_COMMENT_RE.sub("", chunk).strip():
                at_scene_head = False
            cursor = end_comment + 1
            continue
        fence = idx._fence_open(raw_text)
        if fence is not None:
            fence_char, fence_len = fence
            end_fence = cursor + 1
            while end_fence < len(lines) and not idx._fence_close(
                lines[end_fence]["text"], fence_char, fence_len
            ):
                end_fence += 1
            if end_fence >= len(lines):
                break
            cursor = end_fence + 1
            continue
        after_closed = _HTML_COMMENT_RE.sub("", raw_text)
        clean_stripped = after_closed.strip()
        if not clean_stripped:
            cursor += 1
            continue
        if clean_stripped.startswith("##"):
            seen_scene_heading = True
            if "<!--" in after_closed:
                end_comment = idx._scan_comment_end(lines, cursor)
                if end_comment is None:
                    break
                scene_id = None
                at_scene_head = False
                cursor = end_comment + 1
                continue
            match = idx.SCENE_HEADING_RE.fullmatch(clean_stripped)
            if not match:
                scene_id = None
                at_scene_head = False
            else:
                heading_episode = match.group("episode")
                if episode_id and episode_id != heading_episode:
                    scene_id = None
                    at_scene_head = False
                else:
                    episode_id = heading_episode
                    scene_id = match.group("scene")
                    at_scene_head = True
            cursor += 1
            continue
        if clean_stripped.startswith("#"):
            if "<!--" in after_closed:
                end_comment = idx._scan_comment_end(lines, cursor)
                if end_comment is None:
                    break
                scene_id = None
                seen_scene_heading = True
                at_scene_head = False
                cursor = end_comment + 1
                continue
            match = idx.EPISODE_HEADING_RE.fullmatch(clean_stripped)
            episode_id = match.group("episode") if match else episode_id
            scene_id = None
            seen_scene_heading = not bool(match)
            at_scene_head = False
            cursor += 1
            continue
        if (
            (not seen_scene_heading or at_scene_head)
            and "<!--" not in after_closed
            and CAST_LINE_RE.match(after_closed) is not None
        ):
            cursor += 1
            continue
        end_cursor = cursor
        unclosed_comment = False
        while True:
            chunk = "\n".join(lines[i]["text"] for i in range(cursor, end_cursor + 1))
            if "<!--" in _HTML_COMMENT_RE.sub("", chunk):
                if end_cursor + 1 >= len(lines):
                    unclosed_comment = True
                    break
                end_cursor += 1
                continue
            if end_cursor + 1 >= len(lines):
                break
            next_raw = lines[end_cursor + 1]["text"]
            next_stripped = next_raw.strip()
            if (
                not next_stripped
                or next_stripped.startswith("<!--")
                or idx._fence_open(next_raw) is not None
            ):
                break
            next_after_closed = _HTML_COMMENT_RE.sub("", next_raw)
            next_clean = next_after_closed.strip()
            if next_clean.startswith("#") or (
                not seen_scene_heading
                and "<!--" not in next_after_closed
                and CAST_LINE_RE.match(next_after_closed) is not None
            ):
                break
            end_cursor += 1
        if unclosed_comment:
            break
        at_scene_head = False
        if scene_id is not None:
            span = idx._span(screenplay, lines, cursor, end_cursor)
            paragraph = _HTML_COMMENT_RE.sub("", span["_text"]).strip()
            paragraph_lines = [
                line.strip() for line in paragraph.splitlines() if line.strip()
            ]
            has_unseparated_tail = len(paragraph_lines) > 1 and any(
                idx.KNOWN_SPEAKER_DIALOGUE_RE.fullmatch(line)
                or idx.ASCII_DIALOGUE_RE.match(line)
                or idx.TAG_RE.fullmatch(line)
                or idx.ANY_TAG_RE.match(line)
                or idx.MALFORMED_TAG_RE.match(line)
                for line in paragraph_lines[1:]
            )
            if not has_unseparated_tail:
                tag_match = idx.TAG_RE.fullmatch(paragraph)
                if tag_match and tag_match.group("tag") in VOICED_TAGS:
                    voice_match = idx.VOICE_TAG_BODY_RE.fullmatch(
                        tag_match.group("body")
                    )
                    if voice_match:
                        candidate = " ".join(voice_match.group("speaker").split())
                        counts[candidate] = counts.get(candidate, 0) + 1
                        fw_or_voice_counts[candidate] = (
                            fw_or_voice_counts.get(candidate, 0) + 1
                        )
                elif not (
                    tag_match
                    or idx.ANY_TAG_RE.match(paragraph)
                    or idx.MALFORMED_TAG_RE.match(paragraph)
                ):
                    dialogue_match = idx.DIALOGUE_RE.fullmatch(paragraph)
                    if dialogue_match:
                        candidate = " ".join(dialogue_match.group("speaker").split())
                        counts[candidate] = counts.get(candidate, 0) + 1
                        fw_or_voice_counts[candidate] = (
                            fw_or_voice_counts.get(candidate, 0) + 1
                        )
                    else:
                        any_dialogue = idx.KNOWN_SPEAKER_DIALOGUE_RE.fullmatch(
                            paragraph
                        )
                        if any_dialogue:
                            candidate = " ".join(any_dialogue.group("speaker").split())
                            counts[candidate] = counts.get(candidate, 0) + 1
        cursor = end_cursor + 1
    return frozenset(
        name
        for name, count in counts.items()
        if (fw_or_voice_counts.get(name, 0) >= 1 or count >= 2)
        and _is_plausible_auto_speaker(name, count)
    )


def parse_script_blocks(
    screenplay: bytes,
    speakers: Iterable[str] | None = None,
    extra_speakers: Iterable[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse ``screenplay`` directly in memory without writing an index file."""
    idx = _load_screenplay_index()
    screenplay.decode("utf-8")
    has_cast_line, cast_speakers = _declared_script_speakers(
        idx._line_table(screenplay)
    )
    if speakers is not None or has_cast_line:
        explicit_speakers = {
            " ".join(name.split())
            for name in (speakers or ())
            if isinstance(name, str) and name.strip()
        }
        base_speakers = frozenset(cast_speakers | explicit_speakers)
    else:
        base_speakers = _discover_script_speakers(idx, screenplay)
    appended_speakers = {
        " ".join(name.split())
        for name in (extra_speakers or ())
        if isinstance(name, str) and name.strip()
    }
    speaker_names = frozenset(base_speakers | appended_speakers)
    raw_blocks, raw_issues = idx._parse_screenplay(screenplay, speaker_names)
    issues = list(raw_issues)
    blocks = [
        {
            "record_type": "block",
            "block_id": f"BLK-{number:04d}",
            **{key: value for key in block if not key.startswith("_") for value in (block[key],)},
        }
        for number, block in enumerate(raw_blocks, 1)
    ]
    review = {
        "review_status": "review_required" if issues else "clean",
        "source_issue_count": len(issues),
        "needs_human_review": bool(issues),
        "issue_codes": sorted(
            {str(issue["issue_code"]) for issue in issues if "issue_code" in issue}
        ),
    }
    return blocks, review


# Tags that occupy screen time without being spoken. Their seconds depend on how
# the cut holds them, so they are counted and named rather than timed -- unless
# the project declares how fast its audience reads on-screen text.
ON_SCREEN_TEXT_TAG = "画面文字"
UNTIMED_TAGS = (ON_SCREEN_TEXT_TAG, "SFX", "转场")
TAG_PREFIX = re.compile(r"^\[[^\]]+\]\s*")
MIN_RATE = 1e-3
_CJK_PUNCT_RE = re.compile(r"[，。！？、；：「」『』《》【】￥…]")
_ASCII_NUMERIC_TOKEN_CUE_RE = re.compile(r"[$€£¢%/!?.]")


class StaleIndex(Exception):
    """The index does not describe the screenplay it was handed."""


def _strip_comments_and_format_chars(text: str) -> str:
    without_comments = _HTML_COMMENT_RE.sub("", text)
    return "".join(
        character
        for character in without_comments
        if unicodedata.category(character) != "Cf"
    )


def _spoken_characters(line: str) -> int:
    """Count what is actually voiced: no whitespace, comments, Cf, or directions."""
    cleaned = _strip_comments_and_format_chars(line)
    stripped = re.sub(r"（[^）]*）|\([^)]*\)", "", cleaned)
    return len(re.sub(r"\s", "", stripped))


# Scripts written with spaces between words. Their speech unit is the word: an
# English line timed letter by letter at a per-character rate came out about
# three times too long. Characters of every other script stay one unit each.
WORD_SCRIPTS = ("LATIN", "CYRILLIC", "GREEK")
# Inside a word only: don't, well-known, it’s.
WORD_JOINERS = frozenset("'’-")


def _is_word_letter(character: str) -> bool:
    if not character.isalpha():
        return False
    name = unicodedata.name(character, "")
    return any(script in name for script in WORD_SCRIPTS)


def _voiced_units(line: str, *, prefer_words: bool = False) -> tuple[int, int]:
    """What a speaker actually pronounces, as (characters, words).

    Punctuation is not pronounced, so neither count includes it; the
    punctuation-inclusive count stays for the VO share, whose ceiling is
    defined on it. A run of word-script letters (digits and inner apostrophes
    or hyphens included) is one word, and every other pronounced character is
    one character, so ``OK，走吧`` is one word and two characters. A run of
    digits is read in the language around it: one word per numeric token in a
    word-script or ASCII-numeric line (such as ``$100!`` or ``24/7``), one unit
    per digit wherever character-script text is spoken.
    """
    # Strip closed HTML comments, directions, and invisible format characters,
    # then NFC-normalize so decomposed accents count as one precomposed letter.
    cleaned = _strip_comments_and_format_chars(line)
    text = unicodedata.normalize(
        "NFC", re.sub(r"（[^）]*）|\([^)]*\)", "", cleaned)
    )
    text = "".join(
        character for character in text if unicodedata.category(character) != "Cf"
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
                    pass  # a mark NFC could not fold still belongs to its letter
                elif current.isdigit():
                    digits += 1
                elif (
                    not has_letter
                    and digits > 0
                    and current in ".,"
                    and end + 1 < length
                    and text[end + 1].isdigit()
                ):
                    pass  # formatted numeric separator inside a number: 1,000.50
                elif not (
                    current in WORD_JOINERS
                    and end + 1 < length
                    and (_is_word_letter(text[end + 1]) or text[end + 1].isdigit())
                ):
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
    if words and not characters:
        words += len(digit_runs)
    elif (
        not words
        and not characters
        and digit_runs
        and _CJK_PUNCT_RE.search(text) is None
        and (prefer_words or _ASCII_NUMERIC_TOKEN_CUE_RE.search(text) is not None)
    ):
        words += len(digit_runs)
    else:
        characters += sum(digit_runs)
    return characters, words


def _readable_characters(body: str) -> int:
    """Characters a viewer reads in an on-screen text line.

    The whole tag body counts, brackets and any text before a colon included.
    ``已授予：演唱`` puts displayed words before its colon and ``暂停营业（东门）``
    displays its parentheses, so neither can be stripped as a carrier name or a
    performer's note; a line that does name its carrier is over-read by a few
    characters rather than having visible words silently dropped.
    """
    cleaned = _strip_comments_and_format_chars(body)
    return sum(
        1
        for character in re.sub(r"\s", "", cleaned)
        if unicodedata.category(character)[0] not in "PC"
    )


def _is_voiced(block: Mapping[str, Any]) -> bool:
    """Speech is a dialogue block, or a production tag that is spoken aloud."""
    kind = block.get("kind")
    if kind == "dialogue":
        return True
    return kind == "production_tag" and block.get("tag") in VOICED_TAGS


def _block_text(screenplay: bytes, block: Mapping[str, Any]) -> str | None:
    """Return the block's own bytes, or None when its span does not fit."""
    start, end = block.get("byte_start"), block.get("byte_end")
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or not 0 <= start < end <= len(screenplay)
    ):
        return None
    try:
        return screenplay[start:end].decode("utf-8").removeprefix("\ufeff").strip()
    except UnicodeDecodeError:
        # A span that begins or ends mid-character is a stale offset, not a
        # crash: report it the same way as any other span that does not fit.
        return None


def measure(screenplay: bytes, blocks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Count the timed material, taking every classification from the index."""
    dialogue_lines = 0
    dialogue_characters = 0
    voiced_characters = 0
    voiced_words = 0
    voiceover_characters = 0
    action_paragraphs = 0
    tag_lines = 0
    untimed_lines = {tag: 0 for tag in UNTIMED_TAGS}
    on_screen_text_characters = 0
    unreadable_blocks: list[str] = []

    for block in blocks:
        if block.get("record_type") != "block":
            continue
        kind = block.get("kind")

        if kind == "action":
            # One paragraph is one block however many lines it occupies. The
            # format contract lets an action paragraph run several lines.
            action_paragraphs += 1
            continue

        if not _is_voiced(block):
            # Scene headings, comments, fenced code blocks, and instruction-only
            # tags carry no performed duration.
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
                        clean_tag_text = _strip_comments_and_format_chars(text).strip()
                        on_screen_text_characters += _readable_characters(
                            TAG_PREFIX.sub("", clean_tag_text)
                        )
            continue

        text = _block_text(screenplay, block)
        if text is None:
            unreadable_blocks.append(str(block.get("block_id")))
            continue
        clean_text = _strip_comments_and_format_chars(text).strip()
        spoken = DIALOGUE.match(VOICE_TAG_PREFIX.sub("", clean_text))
        if spoken is None:
            # The index recorded it as speech but it does not use the documented
            # line grammar. Guessing a duration here is how a wrong number gets
            # reported as a fact; the block is named instead.
            unreadable_blocks.append(str(block.get("block_id")))
            continue
        spoken_line = spoken.group("line")
        speaker_label = spoken.group("who")
        prefer_words = spoken.group("colon") == ":" or any(
            _is_word_letter(ch) for ch in speaker_label
        )
        dialogue_lines += 1
        characters = _spoken_characters(spoken_line)
        dialogue_characters += characters
        characters_voiced, words_voiced = _voiced_units(
            spoken_line, prefer_words=prefer_words
        )
        voiced_characters += characters_voiced
        voiced_words += words_voiced
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
        counts["untimed_tag_lines"] = {
            tag: number for tag, number in untimed_lines.items() if number
        }
    if untimed_lines[ON_SCREEN_TEXT_TAG]:
        counts["on_screen_text_characters"] = on_screen_text_characters
    if unreadable_blocks:
        counts["unreadable_blocks"] = sorted(unreadable_blocks)
    return counts


def index_blocks(
    index: list[dict[str, Any]], screenplay: bytes
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return the index's blocks and its own review state.

    An index built from other bytes is refused rather than measured: its spans
    would land on text it never classified.
    """
    meta = next(
        (row for row in index if row.get("record_type") == "screenplay_index_meta"),
        None,
    )
    if meta is None:
        raise StaleIndex("the index carries no screenplay_index_meta record")
    declared = meta.get("source_byte_length")
    if isinstance(declared, bool) or not isinstance(declared, int):
        raise StaleIndex("the index declares no source_byte_length")
    if declared != len(screenplay):
        raise StaleIndex(
            "the index was built from {} bytes but this screenplay is {}; "
            "rebuild it with screenplay_index.py before estimating".format(
                declared, len(screenplay)
            )
        )
    issue_codes = sorted(
        {
            str(row["issue_code"])
            for row in index
            if row.get("record_type") == "source_issue" and "issue_code" in row
        }
    )
    source_issue_count = meta.get("source_issue_count")
    has_positive_issue_count = (
        not isinstance(source_issue_count, bool)
        and isinstance(source_issue_count, int)
        and source_issue_count > 0
    )
    review = {
        "review_status": meta.get("review_status"),
        "source_issue_count": source_issue_count,
        "needs_human_review": (
            meta.get("review_status") == "review_required" or has_positive_issue_count
        ),
        "issue_codes": issue_codes,
    }
    return [row for row in index if row.get("record_type") == "block"], review


def declared_rates(project: Mapping[str, Any] | None) -> dict[str, Any]:
    """Read the project's own pacing rates, or report that it declared none."""
    fmt = project.get("format") if isinstance(project, Mapping) else None
    raw_pacing = fmt.get("pacing") if isinstance(fmt, Mapping) else None
    pacing: Mapping[str, Any] = raw_pacing if isinstance(raw_pacing, Mapping) else {}
    per_character = _rate(pacing.get("spoken_characters_per_second"))
    # Words for scripts written with spaces; a project in one language declares
    # only the speech rate it uses, a bilingual one declares both.
    per_word = _rate(pacing.get("spoken_words_per_second"))
    per_action = _rate(pacing.get("seconds_per_action_paragraph"), allow_zero=True)
    usable = (per_character is not None or per_word is not None) and per_action is not None
    reading = _rate(pacing.get("on_screen_text_characters_per_second"))
    return {
        "declared": usable,
        "spoken_characters_per_second": per_character if usable else None,
        "spoken_words_per_second": per_word if usable else None,
        "seconds_per_action_paragraph": per_action if usable else None,
        # Optional: a project that holds text on screen as its own beat can
        # declare how fast it is read. Without it the text stays untimed.
        "on_screen_text_characters_per_second": reading,
    }


def _rate(value: Any, allow_zero: bool = False) -> float | None:
    """A declared rate, or None when the value is not a finite usable number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    if allow_zero and numeric == 0.0:
        return 0.0
    if numeric < MIN_RATE:
        return None
    return numeric


def accepted_vo_share(
    counts: Mapping[str, Any], project: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    """The [VO] share of spoken characters against an accepted ceiling.

    [OS] is off-screen dialogue inside the scene, not narration or inner
    voice, so it counts as spoken but not as voice-over.

    Only a rhythm profile the creator accepted carries a ceiling; a missing or
    proposed one declares nothing, so nothing is compared. The comparison is
    reported, never enforced: the creator may keep an episode over its own cap.
    """
    authority = project.get("creator_authority") if isinstance(project, Mapping) else None
    profile = authority.get("rhythm_profile") if isinstance(authority, Mapping) else None
    if not isinstance(profile, Mapping) or profile.get("status") != "accepted":
        return None
    ceiling = profile.get("vo_share_max")
    if isinstance(ceiling, bool) or not isinstance(ceiling, (int, float)):
        return None
    ceiling_val = float(ceiling)
    if not (math.isfinite(ceiling_val) and 0.0 <= ceiling_val <= 1.0):
        # A hand-edited ceiling outside a share is no ceiling: comparing
        # against NaN or 5 reports a verdict nobody accepted.
        return None
    spoken = counts["dialogue_characters"]
    if not spoken:
        return None
    share = counts["voiceover_characters"] / spoken
    if not math.isfinite(share):
        return None
    return {
        "share": round(share, 3),
        "vo_share_max": ceiling_val,
        "over_max": share > ceiling_val,
    }


def estimate(
    screenplay: bytes,
    blocks: Iterable[Mapping[str, Any]],
    project: Mapping[str, Any] | None = None,
    review: Mapping[str, Any] | None = None,
    target_seconds: float | None = None,
) -> dict[str, Any]:
    counts = measure(screenplay, blocks)
    rates = declared_rates(project)
    # An episode the episode map gives its own length (a longer first episode)
    # is compared against that, not against the project-wide default.
    target: Any = target_seconds
    if target is None:
        fmt = project.get("format") if isinstance(project, Mapping) else None
        if isinstance(fmt, Mapping):
            target = fmt.get("target_seconds_per_episode")

    result: dict[str, Any] = {"counts": counts, "rates": rates, "seconds": None}
    result["target_seconds"] = _rate(target)
    vo_share = accepted_vo_share(counts, project)
    if vo_share is not None:
        result["vo_share"] = vo_share

    # Material the index could not classify is material this estimate did not
    # time. Reporting the seconds without that fact is how an incomplete number
    # gets read as a complete one.
    issues = (review or {}).get("source_issue_count")
    has_issues = not isinstance(issues, bool) and isinstance(issues, int) and issues > 0
    unreadable = counts.get("unreadable_blocks") or []
    if has_issues or unreadable:
        incomplete_entry: dict[str, Any] = {
            "index_review_status": (review or {}).get("review_status"),
            "source_issue_count": issues,
            "needs_human_review": True,
            "unreadable_blocks": unreadable,
            "note": (
                "the index left some of this screenplay unclassified, so the "
                "counts below cover less than the whole text; resolve the index "
                "issues before reading these seconds as the episode's length"
            ),
        }
        issue_codes = (review or {}).get("issue_codes")
        if issue_codes:
            incomplete_entry["issue_codes"] = issue_codes
        result["incomplete"] = incomplete_entry

    untimed = dict(counts.get("untimed_tag_lines") or {})
    if rates["on_screen_text_characters_per_second"] is not None:
        untimed.pop(ON_SCREEN_TEXT_TAG, None)
    if untimed:
        # These lines take screen time this estimate cannot see. A storyboard
        # that holds each one long enough to read lands well above the number
        # below, so the gap is named here instead of surfacing two stages later.
        result["untimed"] = {
            "tag_lines": untimed,
            "note": (
                "these production tags take screen time that is not in the "
                "seconds; declare format.pacing.on_screen_text_characters_per_second "
                "to time on-screen text by its readable characters"
            ),
        }

    if not rates["declared"]:
        result["note"] = (
            "the project declares no format.pacing rates, so seconds cannot be "
            "derived; the counts above are still exact"
            if "incomplete" not in result
            else "the project declares no format.pacing rates, so seconds "
            "cannot be derived; the counts above are exact for the blocks the "
            "index classified, which is not all of this screenplay"
        )
        return result

    seconds = counts["action_paragraphs"] * rates["seconds_per_action_paragraph"]
    speech = 0.0
    unpriced: dict[str, int] = {}
    for unit, rate_name in (
        ("voiced_characters", "spoken_characters_per_second"),
        ("voiced_words", "spoken_words_per_second"),
    ):
        if not counts[unit]:
            continue
        if rates[rate_name] is None:
            unpriced[unit] = counts[unit]
        else:
            speech += counts[unit] / rates[rate_name]
    seconds += speech
    if unpriced:
        # Speech in a unit the project has no rate for. Borrowing the other
        # rate is the letter-by-letter error this split exists to stop, so the
        # count is named next to seconds that leave it out.
        result["untimed_speech"] = {
            "counts": unpriced,
            "note": (
                "the project declares no rate for this speech, so the seconds "
                "leave it out; declare format.pacing.spoken_words_per_second "
                "for words and spoken_characters_per_second for characters"
            ),
        }
    reading = rates["on_screen_text_characters_per_second"]
    reading_seconds: float | None = None
    if reading is not None and counts.get("on_screen_text_characters"):
        reading_seconds = counts["on_screen_text_characters"] / reading
        seconds += reading_seconds

    if (
        not math.isfinite(seconds)
        or not math.isfinite(speech)
        or (reading_seconds is not None and not math.isfinite(reading_seconds))
    ):
        result["note"] = (
            "declared format.pacing rates overflowed finite duration calculation; "
            "check the project's pacing numbers"
        )
        return result

    if reading_seconds is not None:
        result["on_screen_text_seconds"] = round(reading_seconds, 1)
    result["seconds"] = round(seconds, 1)
    if seconds > 0 and not unpriced:
        share_ratio = speech / seconds
        if math.isfinite(share_ratio):
            # How much of the estimated runtime someone is speaking. Silent action,
            # on-screen text and untimed tags make up the rest.
            result["speech_seconds"] = round(speech, 1)
            result["speech_share"] = round(share_ratio, 2)
    target_val = result["target_seconds"]
    if target_val:
        delta = seconds - target_val
        delta_ratio = delta / target_val
        if math.isfinite(delta) and math.isfinite(delta_ratio):
            result["delta_seconds"] = round(delta, 1)
            result["delta_ratio"] = round(delta_ratio, 3)
            result["note"] = (
                "informational only: the suite sets no tolerance band, because the "
                "right spread depends on the project's own scenes"
            )
        else:
            result["note"] = (
                "declared target_seconds overflowed finite delta calculation; "
                "check the episode target length"
            )
    else:
        result["note"] = (
            "no format.target_seconds_per_episode is declared, so there is "
            "nothing to compare the estimate against; pass --target-seconds "
            "for an episode the episode map gives its own length"
        )
    return result


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SystemExit("{}: {}".format(path, error))
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(raw_text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise SystemExit("{}:{}: {}".format(path, number, error))
        if isinstance(row, dict):
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Estimate screenplay duration from the project's declared rates."
    )
    parser.add_argument(
        "screenplay",
        nargs="?",
        type=Path,
        default=None,
        help="screenplay Markdown path (paired with --index)",
    )
    parser.add_argument(
        "--script",
        type=Path,
        default=None,
        help="screenplay Markdown path to parse and estimate directly in memory",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help="screenplay-index.jsonl built from this screenplay by screenplay_index.py",
    )
    parser.add_argument(
        "--speaker",
        action="append",
        default=None,
        help="explicit speaker whitelist override (repeatable; supported with --script and --index)",
    )
    parser.add_argument(
        "--extra-speaker",
        action="append",
        default=None,
        help=(
            "additional speaker label unioned onto auto-discovered, declared, or "
            "indexed speakers (repeatable; supported with --script and --index)"
        ),
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=None,
        help=(
            "short-drama.json carrying format.pacing, target_seconds_per_episode "
            "and, when accepted, creator_authority.rhythm_profile.vo_share_max"
        ),
    )
    parser.add_argument(
        "--target-seconds",
        type=float,
        default=None,
        help=(
            "this episode's own target length from the episode map; overrides "
            "format.target_seconds_per_episode for the comparison"
        ),
    )
    args = parser.parse_args(argv)
    if args.target_seconds is not None and _rate(args.target_seconds) is None:
        raise SystemExit("--target-seconds must be a finite number >= 0.001")

    if args.script is not None and args.screenplay is not None:
        parser.error("pass either --script or positional screenplay, not both")
    if args.script is not None and args.index is not None:
        parser.error("--script parses in memory; omit --index")
    if args.script is None and args.screenplay is None:
        parser.error(
            "pass --script <剧本.md> or positional screenplay --index <index.jsonl>"
        )
    if args.script is None and args.index is None:
        parser.error(
            "positional screenplay mode requires --index; use --script <剧本.md> for direct estimation"
        )

    source_path = args.script if args.script is not None else args.screenplay
    assert source_path is not None
    if not source_path.is_file():
        raise SystemExit("screenplay not found: {}".format(source_path))
    if args.index is not None and not args.index.is_file():
        raise SystemExit("screenplay index not found: {}".format(args.index))

    project: dict[str, Any] | None = None
    if args.project is not None:
        if not args.project.is_file():
            raise SystemExit("project file not found: {}".format(args.project))
        try:
            loaded_project = json.loads(args.project.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise SystemExit("{}: {}".format(args.project, error))
        if not isinstance(loaded_project, dict):
            raise SystemExit("{}: project file must be a JSON object".format(args.project))
        project = loaded_project

    try:
        screenplay = source_path.read_bytes()
    except OSError as error:
        raise SystemExit("{}: {}".format(source_path, error))
    if args.script is not None:
        try:
            blocks, review = parse_script_blocks(
                screenplay,
                speakers=args.speaker,
                extra_speakers=args.extra_speaker,
            )
        except UnicodeDecodeError as error:
            raise SystemExit("{}: {}".format(source_path, error))
    else:
        assert args.index is not None
        try:
            blocks, review = index_blocks(_load_jsonl(args.index), screenplay)
        except StaleIndex as error:
            raise SystemExit("{}: {}".format(args.index, error))
        if args.speaker is not None or args.extra_speaker is not None:
            indexed_speakers = {
                str(row["speaker"])
                for row in blocks
                if _is_voiced(row)
                and isinstance(row.get("speaker"), str)
                and row["speaker"].strip()
            }
            try:
                blocks, review = parse_script_blocks(
                    screenplay,
                    speakers=(
                        args.speaker
                        if args.speaker is not None
                        else (indexed_speakers or None)
                    ),
                    extra_speakers=args.extra_speaker,
                )
            except UnicodeDecodeError as error:
                raise SystemExit("{}: {}".format(source_path, error))

    report = estimate(screenplay, blocks, project, review, args.target_seconds)
    print(
        json.dumps(
            report,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )
    # An estimate is never a verdict, so this exits successfully even when the
    # episode lands far from its target. Blocking here would turn a reported
    # number into the cross-project threshold this suite refuses to carry.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
