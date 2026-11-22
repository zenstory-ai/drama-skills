#!/usr/bin/env python3
"""Validate the executable cross-document contract of one creator-first episode."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from collections.abc import Iterable, Mapping
from typing import Any, NamedTuple, Optional


MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "creator_markdown_check.py requires Python {}.{}, running {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )


REQUIRED_DOCUMENTS = (
    "剧本.md",
    "视觉设定.md",
    "图片提示词.md",
    "分镜.md",
    "视频提示词.md",
)
SECTION_RE = re.compile(
    r"^##[ \t\u3000]+((?:IMG|SHOT|MOTION|GROUP|MUSIC)-[A-Z0-9-]+)\b", re.MULTILINE
)
ANY_SECTION_RE = re.compile(r"^##[ \t\u3000]+", re.MULTILINE)
IMG_RE = re.compile(r"\b(IMG-[A-Z0-9-]+)《([^》]+)》（控制：([^）]+)）")
REF_SLOT_ID_PATTERN = r"REF-[A-Z0-9][A-Z0-9-]{0,79}"
PLAN_SLOT_ID_PATTERN = r"PLAN-[A-Z0-9][A-Z0-9-]{0,79}"
# 用途 is optional in the pattern on purpose: a declaration written before this
# field existed still parses, so the creator gets "REF 缺少用途" instead of the
# generic syntax error that gives no hint about what to add.
REF_RE = re.compile(
    r"(" + REF_SLOT_ID_PATTERN + r")（顺序：([1-9]\d*)）· "
    r"([^；\n]+?\.(?i:png|jpe?g|webp))《([^》\n]+)》"
    r"（(?:用途：([^；）\n]+)；)?控制：([^；）]+)；不得控制：([^）]+)）"
)
# The same slot grammar, but the locator is a document entry instead of a file.
# A creator who generates in an external tool never has the file inside the
# project, and the copyable body only ever needed 顺序 and 用途 -- the path is a
# production input, not a prompt input. PLAN says "this picture does not exist
# here; attach it yourself in this order", which is a different claim from
# 「已有图片」 and from 「待补」.
PLAN_RE = re.compile(
    r"(" + PLAN_SLOT_ID_PATTERN + r")（顺序：([1-9]\d*)）· "
    r"((?:IMG|SHOT)-[A-Z0-9-]+)《([^》\n]+)》"
    r"（(?:用途：([^；）\n]+)；)?控制：([^；）]+)；不得控制：([^）]+)）"
)
MALFORMED_SLOT_ID_RE = re.compile(
    r"(?:(?i:ref|plan)-[A-Za-z0-9-]*[a-z][A-Za-z0-9-]*|(?:REF|PLAN)-[A-Z0-9-]{81,})（顺序："
)
# One picture takes one slot, and its 用途 names the slot's main job (a second
# job goes in 控制, per references/reference-roles.md). That single purpose is
# what makes a slot translatable into a provider role, so the vocabulary is
# closed rather than free prose.
REF_PURPOSES = (
    "外貌",
    "造型状态",
    "空间布局",
    "构图",
    "尺度",
    "效果",
    "起始帧",
    "结束帧",
    "主体",
    "风格",
)
# A character's voice travels on its own line, `- 参考音频：`, never inside
# 输入参考图: the picture slots number `@图片N`/`<Picture N>`/`图N` and the audio
# slots number `@音频N`/`<Audio N>`/`音频N`, each from 1, so mixing them in one
# field would renumber every picture after the first voice.
def _normalize_text(text: str) -> str:
    """Strip a leading UTF-8 BOM and normalize CRLF/CR line endings to LF."""
    if text.startswith("\ufeff"):
        text = text[1:]
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def _emph_key(label: str) -> str:
    escaped = re.escape(label)
    return (
        rf"(?:\*\*\*{escaped}\*\*\*|___{escaped}___"
        rf"|\*\*{escaped}\*\*|__{escaped}__"
        rf"|\*{escaped}\*|_{escaped}_|{escaped})"
    )


def _emph_field_head(label: str) -> str:
    escaped = re.escape(label)
    ws = r"[ \t\u3000]*"
    return (
        rf"(?:{_emph_key(label)}{ws}[：:]"
        rf"|\*\*\*{escaped}{ws}[：:]{ws}\*\*\*"
        rf"|___{escaped}{ws}[：:]{ws}___"
        rf"|\*\*{escaped}{ws}[：:]{ws}\*\*"
        rf"|__{escaped}{ws}[：:]{ws}__"
        rf"|\*{escaped}{ws}[：:]{ws}\*"
        rf"|_{escaped}{ws}[：:]{ws}_)"
    )


_EMPH_MARKERS = ("***", "___", "**", "__", "*", "_")


def _strip_key_emphasis(key: str) -> str:
    stripped = re.sub(r"[ \t\u3000]*[：:]$", "", key.strip()).strip()
    peeled = False
    changed = True
    while changed:
        changed = False
        for marker in _EMPH_MARKERS:
            if (
                len(stripped) > 2 * len(marker)
                and stripped.startswith(marker)
                and stripped.endswith(marker)
            ):
                inner = stripped[len(marker) : -len(marker)]
                if marker[0] not in inner:
                    stripped = inner.strip()
                    peeled = True
                    changed = True
                    break
    if peeled:
        stripped = re.sub(r"[ \t\u3000]*[：:]$", "", stripped).strip()
    return stripped


_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})([^\r\n]*)\r?$", re.MULTILINE)
_COPYABLE_BLOCK_RE = re.compile(
    r"^###[ \t\u3000]+(?:可复制提示词|首帧提示词|尾帧提示词)[ \t\u3000]*\r?$",
    re.MULTILINE,
)
_COPYABLE_END_RE = re.compile(r"^#{1,6}[ \t\u3000]+", re.MULTILINE)
_INLINE_TICK_RE = re.compile(r"`+")


def _line_opens_multiline_comment(line: str) -> bool:
    idx = 0
    while True:
        open_at = line.find("<!--", idx)
        if open_at == -1:
            return False
        close_at = line.find("-->", open_at + 4)
        if close_at == -1:
            return True
        idx = close_at + 3


def _copyable_protected_end(text: str, heading_end: int) -> int:
    length = len(text)
    cursor = heading_end
    if cursor < length and text[cursor] == "\r":
        cursor += 1
    if cursor < length and text[cursor] == "\n":
        cursor += 1
    last_quote_end: Optional[int] = None
    while cursor < length:
        nl = text.find("\n", cursor)
        line_end = length if nl == -1 else nl + 1
        raw_line = text[cursor:line_end].rstrip("\r\n")
        if _COPYABLE_END_RE.match(raw_line):
            break
        if raw_line.lstrip(" \t\u3000").startswith(">"):
            last_quote_end = line_end
        elif _line_opens_multiline_comment(raw_line):
            break
        cursor = line_end
    return last_quote_end if last_quote_end is not None else heading_end


def _scan_html_comments(
    text: str, *, preserve_copyable: bool = False
) -> tuple[str, bool]:
    """Strip HTML comments outside protected Markdown spans while keeping line numbers.

    Returns ``(stripped_text, has_unclosed_comment)``. Single-line backtick code
    spans, fenced code blocks, and (when ``preserve_copyable`` is True) copyable
    prompt blocks protect literal ``<!--`` from starting a comment.
    """
    text = _normalize_text(text)
    if "<!--" not in text:
        return text, False
    out: list[str] = []
    pos = 0
    length = len(text)
    unclosed = False
    while pos < length:
        comment_idx = text.find("<!--", pos)
        if comment_idx == -1:
            out.append(text[pos:])
            break
        candidates: list[tuple[int, str, object]] = []
        fence = _FENCE_OPEN_RE.search(text, pos)
        while (
            fence is not None
            and fence.start() <= comment_idx
            and fence.group(1)[0] == "`"
            and "`" in fence.group(2)
        ):
            fence = _FENCE_OPEN_RE.search(text, fence.end())
        if fence is not None and fence.start() <= comment_idx:
            candidates.append((fence.start(), "fence", fence))
        if preserve_copyable:
            copy_block = _COPYABLE_BLOCK_RE.search(text, pos)
            if copy_block is not None and copy_block.start() <= comment_idx:
                candidates.append((copy_block.start(), "copy", copy_block))
        tick = _INLINE_TICK_RE.search(text, pos)
        if tick is not None and tick.start() <= comment_idx:
            candidates.append((tick.start(), "tick", tick))
        if candidates:
            # At identical start offsets, block fences beat inline backtick runs.
            priority = {"fence": 0, "copy": 1, "tick": 2}
            candidates.sort(key=lambda item: (item[0], priority[item[1]]))
            kind = candidates[0][1]
            token = candidates[0][2]
            if kind == "fence":
                assert isinstance(token, re.Match)
                marker = token.group(1)
                after_open = text.find("\n", token.end())
                if after_open == -1:
                    protected_end = length
                else:
                    close_re = re.compile(
                        rf"^[ \t]{{0,3}}{re.escape(marker[0])}{{{len(marker)},}}[ \t]*\r?$",
                        re.MULTILINE,
                    )
                    close = close_re.search(text, after_open + 1)
                    protected_end = length if close is None else close.end()
                out.append(text[pos:protected_end])
                pos = protected_end
                continue
            if kind == "copy":
                assert isinstance(token, re.Match)
                protected_end = _copyable_protected_end(text, token.end())
                out.append(text[pos:protected_end])
                pos = protected_end
                continue
            assert isinstance(token, re.Match)
            run_len = len(token.group(0))
            line_end = text.find("\n", token.end())
            if line_end == -1:
                line_end = length
            close_tick_re = re.compile(rf"(?<!`){'`' * run_len}(?!`)")
            close_tick = close_tick_re.search(text, token.end(), line_end)
            if close_tick is not None:
                out.append(text[pos : close_tick.end()])
                pos = close_tick.end()
            else:
                out.append(text[pos : token.end()])
                pos = token.end()
            continue
        out.append(text[pos:comment_idx])
        close_comment = text.find("-->", comment_idx + 4)
        if close_comment == -1:
            out.append("\n" * text[comment_idx:].count("\n"))
            unclosed = True
            pos = length
            break
        comment_end = close_comment + 3
        out.append("\n" * text[comment_idx:comment_end].count("\n"))
        pos = comment_end
    return "".join(out), unclosed


def _strip_html_comments(text: str, *, preserve_copyable: bool = False) -> str:
    """Strip HTML comments outside Markdown fences while keeping line numbers."""
    stripped, _ = _scan_html_comments(text, preserve_copyable=preserve_copyable)
    return stripped


AUDIO_SUFFIXES = ("wav", "mp3", "m4a", "aac", "flac", "opus")
AUDIO_REF_RE = re.compile(
    r"(" + REF_SLOT_ID_PATTERN + r")（顺序：([1-9]\d*)）· "
    r"([^；\n]+?\.(?i:" + "|".join(AUDIO_SUFFIXES) + r"))《([^》\n]+)》"
    r"（用途：([^；）\n]+)；角色：([^；）\n]+)；控制：([^；）]+)；不得控制：([^）]+)）"
)
AUDIO_PURPOSE = "音色"
AUDIO_SYNTAX = (
    "REF-<槽位>（顺序：<n>）· <音频路径>《<名称>》"
    "（用途：音色；角色：<人物名>；控制：<范围>；不得控制：<范围>）"
)
# An audio file or 用途：音色 in a picture field is a voice binding written in
# the wrong place; the generic "broken REF syntax" would not say where it goes.
AUDIO_IN_IMAGE_FIELD_RE = re.compile(
    r"\.(?:" + "|".join(AUDIO_SUFFIXES) + r")《|用途：音色", re.IGNORECASE
)
# Where 《视觉设定.md》 records a character's accepted voice reference: one
# line under that 人物 entry, path first.
VOICE_RECORD_RE = re.compile(
    rf"^[ \t\u3000]*[-*+][ \t\u3000]*{_emph_field_head('声音参考')}[ \t\u3000]*(.*)$",
    re.MULTILINE,
)
# Same filename rule as the binding's locator (`[^；\n]+?`), so any path a
# 参考音频 slot may name can also be the recorded one -- spaces included.
VOICE_RECORD_PATH_RE = re.compile(
    r"([^（；\n]+?\.(?:" + "|".join(AUDIO_SUFFIXES) + r"))(?=（|$)", re.IGNORECASE
)
# The screenplay's dialogue grammar, mirrored from the write skill's
# screenplay_index.py (DIALOGUE_RE, and TAG_RE + VOICE_TAG_BODY_RE for [VO] and
# [OS]). Each is matched against a whole paragraph, so a line that wraps onto
# the next physical line is still one line of dialogue.
_NOT_CLOCK_PREFIX = r"(?!\d{1,2}[:：]\d{2}(?:\D|$))"
_MAX_SPEAKER_LENGTH = 40
_SPEAKER_TOKEN = r"[^\s：:（）()\[\]#，。！？；,!?;—]+"
_SPEAKER_LABEL = (
    rf"(?=.{{1,{_MAX_SPEAKER_LENGTH}}}(?:[ \t\u3000]*[（(]|：|:))"
    rf"{_SPEAKER_TOKEN}(?: {_SPEAKER_TOKEN}){{0,3}}"
)
_OPTIONAL_CUE = r"(?:[ \t\u3000]*(?:（[^（）\r\n]+）|\([^()\r\n]+\)))?"
SCREENPLAY_DIALOGUE_RE = re.compile(
    rf"^{_NOT_CLOCK_PREFIX}(?P<speaker>{_SPEAKER_LABEL}){_OPTIONAL_CUE}[：:][ \t\u3000]*(?P<text>\S[\s\S]*)$"
)
SCREENPLAY_VOICE_TAG_RE = re.compile(
    rf"^\[(?:VO|OS)\][ \t\u3000]*{_NOT_CLOCK_PREFIX}(?P<speaker>{_SPEAKER_LABEL}){_OPTIONAL_CUE}[：:][ \t\u3000]*(?P<text>\S[\s\S]*)$"
)
# A later line of a paragraph that starts another block (the index's
# ASCII_DIALOGUE_RE, ANY_TAG_RE and MALFORMED_TAG_RE): the paragraph is missing
# a separator and the index emits no dialogue for it.
SCREENPLAY_BLOCK_START_RE = re.compile(
    rf"^{_NOT_CLOCK_PREFIX}{_SPEAKER_LABEL}{_OPTIONAL_CUE}:\s*\S"
    r"|^\[[^\]\r\n]+\]"
    r"|^\[(?:VO|OS|SFX|画面文字|连续性|转场)(?:\s|：|:)"
)
CAST_LINE_RE = re.compile(
    r"^[ \t\u3000]*(?:[-*+][ \t\u3000]+)?(?:"
    r"人物[ \t\u3000]*[：:]"
    r"|\*\*\*人物(?:[ \t\u3000]*\*\*\*[ \t\u3000]*[：:]|[ \t\u3000]*[：:][ \t\u3000]*\*\*\*)"
    r"|___人物(?:[ \t\u3000]*___[ \t\u3000]*[：:]|[ \t\u3000]*[：:][ \t\u3000]*___)"
    r"|\*\*人物(?:[ \t\u3000]*\*\*[ \t\u3000]*[：:]|[ \t\u3000]*[：:][ \t\u3000]*\*\*)"
    r"|__人物(?:[ \t\u3000]*__[ \t\u3000]*[：:]|[ \t\u3000]*[：:][ \t\u3000]*__)"
    r"|\*人物(?:[ \t\u3000]*\*[ \t\u3000]*[：:]|[ \t\u3000]*[：:][ \t\u3000]*\*)"
    r"|_人物(?:[ \t\u3000]*_[ \t\u3000]*[：:]|[ \t\u3000]*[：:][ \t\u3000]*_)"
    r").*$"
)
# `EP001-SC001` is the documented shape, but a project that scopes ids by season
# writes `S01-EP001-SC001`. Both are one stable scene id, so the pattern takes
# any hyphenated prefix rather than exactly one segment.
SLOT_HEAD_RE = re.compile(
    r"(?:REF|PLAN)-[A-Za-z0-9][A-Za-z0-9-]*（顺序：", re.IGNORECASE
)
SCENE_ID_PATTERN = r"(?:[A-Za-z0-9]+-)+SC[0-9]+"
SCENE_HEADING_RE = re.compile(
    r"^##[ \t\u3000]+(" + SCENE_ID_PATTERN + r")\b", re.MULTILINE
)
FULL_SCENE_HEADING_RE = re.compile(
    r"^##[ \t\u3000]+(?P<scene>(?:[A-Za-z0-9]+-)*?EP(?:[0-9]{3}|[1-9][0-9]{3,})-SC(?:[0-9]{3}|[1-9][0-9]{3,}))"
    r"(?:[ \t\u3000]+|[ \t\u3000]*·[ \t\u3000]*)(?P<space>内外|内|外)"
    r"[ \t\u3000]*·[ \t\u3000]*(?P<location>[^·\r\n]+?)"
    r"[ \t\u3000]*·[ \t\u3000]*(?P<time>[^·\r\n]+?)[ \t\u3000]*\r?$",
    re.MULTILINE,
)
SCENE_LINE_CANDIDATE_RE = re.compile(
    r"^##(?![#])[^\r\n]*$", re.MULTILINE
)
BLOCKING_LINE_RE = re.compile(
    r"^#{2,4}[ \t\u3000]*场景站位(?![ \t\u3000]*$)[^\r\n]*$", re.MULTILINE
)
BLOCKING_HEADING_RE = re.compile(
    r"^##[ \t\u3000]+场景站位[ \t\u3000]*·[ \t\u3000]*("
    + SCENE_ID_PATTERN
    + r")[ \t\u3000]*·[ \t\u3000]*([^\r\n]+?)[ \t\u3000]*\r?$",
    re.MULTILINE,
)
SCENE_ID_RE = re.compile(SCENE_ID_PATTERN)
# A quoted span of the source line, 「…」, 『…』, “…” or "...".
QUOTE_RE = re.compile(r"「[^」]*」|『[^』]*』|“[^”]*”|\"[^\"]*\"")
# A scene the storyboard decided not to film. SHT-01 has always allowed the
# omission and always required a reason; without a place to write it the
# omission and an oversight look identical in the finished document.
UNFILMED_LINE_RE = re.compile(
    rf"^[ \t\u3000]*[-*+][ \t\u3000]*{_emph_field_head('未拍场次')}[ \t\u3000]*(.*)$",
    re.MULTILINE,
)
UNFILMED_ENTRY_RE = re.compile(
    r"(" + SCENE_ID_PATTERN + r")（理由：([^）\n]+)）"
)
EXPLICIT_TEXT_TO_VIDEO = "无（文生视频）"
PENDING_REFERENCE_SUFFIX_RE = re.compile(r"；待补参考图：[^；。\n]+。?$")
VISUAL_CATEGORIES = ("人物", "造型", "地点", "道具")
# A malformed entry always tries to name something; a heading that is only the
# category word is a section divider ("## 人物"), and rejecting it left the
# document with no way to group entries at all.
VISUAL_SETTING_LINE_RE = re.compile(
    r"^#{2,4}[ \t　]*(?:"
    + "|".join(VISUAL_CATEGORIES)
    + r")(?![ \t　]*$)[^\n]*$",
    re.MULTILINE,
)
VISUAL_SETTING_HEADING_RE = re.compile(
    r"^##[ \t\u3000]+(" + "|".join(VISUAL_CATEGORIES) + r") · (.+?)[ \t\u3000]*\r?$",
    re.MULTILINE,
)
# Any other `## <word> · <name>` heading, so an 出场设定 entry that fails to
# resolve can say "the entry is there, the section word is not one of the four"
# instead of blaming the storyboard for a `视觉设定.md` problem.
OTHER_SETTING_HEADING_RE = re.compile(
    r"^##[ \t\u3000]+([^\r\n·]+?) · (.+?)[ \t\u3000]*\r?$", re.MULTILINE
)
# 提示词名称 is the one field the coverage check depends on, so — like a
# continuity lock — anything that looks like it has to parse rather than
# silently drop out.
# Anchored at the start of the line so a sentence that merely mentions the
# field is prose, not a malformed declaration.
SCREEN_NAME_LINE_RE = re.compile(
    r"^[ \t\u3000]*(?:[-+][ \t\u3000]*|\*[ \t\u3000]+)?[*_]*提示词名称[*_]*[ \t\u3000]*[：:][^\r\n]*$",
    re.MULTILINE,
)
SCREEN_NAME_RE = re.compile(
    rf"^[ \t\u3000]*[-*+][ \t\u3000]*{_emph_field_head('提示词名称')}[ \t\u3000]*(.+)$",
    re.MULTILINE,
)
ROLE_VOICE_LINE_RE = re.compile(
    r"^[ \t\u3000]*(?:[-+][ \t\u3000]*|\*[ \t\u3000]+)?[*_]*角色声线[*_]*[ \t\u3000]*[：:][^\r\n]*$",
    re.MULTILINE,
)
ROLE_VOICE_RE = re.compile(
    rf"^[ \t\u3000]*[-*+][ \t\u3000]*{_emph_field_head('角色声线')}[ \t\u3000]*(.+)$",
    re.MULTILINE,
)
VISUAL_BASIS_PREFIX = "《视觉设定.md》·"
VISUAL_BASIS_ENTRY_RE = re.compile(
    r"(" + "|".join(VISUAL_CATEGORIES) + r")「([^」\n]+)」（控制：([^）\n]+)）"
)
# A subject a keyframe names but does not show — an owner's abandoned bag, a
# name on a screen, a homonym of an entry name. SHT-22 excludes these from
# coverage, so the field needs a way to say so instead of forcing the creator
# to declare an absent subject as present.
OFFSCREEN_PREFIX = "；画外："
OFFSCREEN_ENTRY_RE = re.compile(
    r"(" + "|".join(VISUAL_CATEGORIES) + r")「([^」\n]+)」"
)
# A declared lock must never become a no-op. Anything that *looks* like a lock
# line -- any list marker, any leading whitespace -- is captured here and then
# has to parse, so a creator who indents the bullet under 外观特征 gets an error
# instead of silent non-enforcement.
IN_FRAME_SCOPE = "入画"
LOCK_LINE_RE = re.compile(
    r"^[ \t\u3000]*(?:[-+][ \t\u3000]*|\*[ \t\u3000]+|\*(?![ \t\u3000]))[*_]*连戏锁[*_]*[ \t\u3000]*[：:][^\r\n]*$",
    re.MULTILINE,
)
LOCK_RE = re.compile(
    rf"^[ \t\u3000]*[-*+][ \t\u3000]*{_emph_field_head('连戏锁')}[ \t\u3000]*(LOCK-[A-Z0-9-]+)《([^》\n]+)》"
    r"（镜头：([^；）\n]+)"
    r"(?:；图片提示词项：([^；）\n]+))?）"
    r"· 锁定词：(.+)$"
)


def _sections(document: str, kind: str) -> dict[str, str]:
    """Each `## <kind>-...` entry, running up to the next second-level heading.

    The entry stops at *any* `## ` heading, not only the next entry of its own
    kind: a report or a delivery group written after the last shot would
    otherwise be read as that shot's fields.
    """
    document = _normalize_text(document)
    headings = [match.start() for match in ANY_SECTION_RE.finditer(document)]
    sections: dict[str, str] = {}
    for match in SECTION_RE.finditer(document):
        if not match.group(1).startswith(f"{kind}-"):
            continue
        end = next((start for start in headings if start > match.start()), None)
        sections.setdefault(match.group(1), document[match.start() : end])
    return sections


_PLAIN_KEY_CHARS = r"[^：:（()），,。；;\r\n]+?"
_STAR_KEY_CHARS = r"[^*：:（()），,。；;\r\n]+?"
_UNDER_KEY_CHARS = r"[^_：:（()），,。；;\r\n]+?"
_NOT_EMPH_CLOCK_PREFIX = (
    r"(?!\*{0,3}\d{1,2}[：:]\d{2}(?:\D|$)|_{0,3}\d{1,2}[：:]\d{2}(?:\D|$))"
)
FIELD_LINE_RE = re.compile(
    rf"^[ \t\u3000]*[-*+][ \t\u3000]+"
    rf"((?:"
    rf"\*\*\*{_NOT_CLOCK_PREFIX}{_STAR_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*\*\*\*"
    rf"|___{_NOT_CLOCK_PREFIX}{_UNDER_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*___"
    rf"|\*\*{_NOT_CLOCK_PREFIX}{_STAR_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*\*\*"
    rf"|__{_NOT_CLOCK_PREFIX}{_UNDER_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*__"
    rf"|\*{_NOT_CLOCK_PREFIX}{_STAR_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*\*"
    rf"|_{_NOT_CLOCK_PREFIX}{_UNDER_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*_"
    rf"|{_NOT_EMPH_CLOCK_PREFIX}{_PLAIN_KEY_CHARS}[ \t\u3000]*[：:]"
    rf"))[ \t\u3000]*(.+)$",
    re.MULTILINE,
)


def _fields(section: str, *, owner: str, errors: list[str]) -> dict[str, str]:
    section = _normalize_text(section)
    pairs = FIELD_LINE_RE.findall(section)
    fields: dict[str, str] = {}
    for key, value in pairs:
        # `- **参考**：…` is ordinary Markdown and reads as the same field to a
        # human. Taking the emphasis literally turned it into a different key,
        # so the author got "缺少参考字段" while looking straight at 参考.
        key = _strip_key_emphasis(key)
        if key in fields:
            errors.append(f"{owner}: 字段重复: {key}")
        fields[key] = value
    return fields


def _plain(value: str) -> str:
    return value.strip().rstrip("。")


def _contains_ref_token(value: str) -> bool:
    return "ref-" in value.casefold()


def _contains_plan_token(value: str) -> bool:
    return "plan-" in value.casefold()


def _contains_slot_token(value: str) -> bool:
    return _contains_ref_token(value) or _contains_plan_token(value)


def _is_none(value: str) -> bool:
    # `[^）]+` would stop at the first closing bracket, so a gap list that names
    # an entry in brackets -- 「许棠人物图（IMG-...）」 -- fell through to the REF
    # syntax error, whose obvious repair is deleting the gap record. That is the
    # silent downgrade this contract exists to prevent, so the note takes any
    # content as long as it is bracketed.
    return not _contains_slot_token(value) and bool(
        re.fullmatch(r"无(?:（.+）)?", _plain(value), re.DOTALL)
    )


def _is_explicit_text_to_video(value: str) -> bool:
    return _plain(value) in {"无", EXPLICIT_TEXT_TO_VIDEO}


def _has_pending_references(value: str) -> bool:
    plain = _plain(value)
    return plain.startswith("无（待补参考图") or bool(
        re.search(r"[；;]\s*待补参考图[：:][^；;。\n]+。?$", value.strip())
    )


def _is_no_external_reference(value: str) -> bool:
    stripped = value.strip()
    return (
        not _contains_slot_token(stripped)
        and not _has_pending_references(stripped)
        and "待补参考图" not in stripped
        and bool(
            re.fullmatch(
                r"无(?:外部参考)?(?:（[^）\n]+）|\([^)\n]+\))?(?:[；;][^\n]*)?。?",
                stripped,
            )
        )
    )


def _copyable_prompt(
    section: str, heading: str = "可复制提示词"
) -> Optional[str]:
    section = _normalize_text(section)
    markers = list(
        re.finditer(rf"^###[ \t\u3000]+{heading}[ \t\u3000]*\r?$", section, re.MULTILINE)
    )
    if len(markers) != 1:
        return None
    body = section[markers[0].end() :]
    following = _COPYABLE_END_RE.search(body)
    if following is not None:
        body = body[: following.start()]
    lines = [line for line in body.splitlines() if line.strip()]
    if not lines or any(not line.startswith(">") for line in lines):
        return None
    prompt = "\n".join(line[1:].lstrip() for line in lines).strip()
    return prompt or None


def _copyable_prompt_cause(
    section: str, heading: str = "可复制提示词"
) -> str:
    """Why `_copyable_prompt` returned None, as a suffix for the error.

    "缺少唯一且非空的可复制提示词" is true of four different documents and tells
    the author nothing about which one they wrote. The expensive case is a
    single stray line -- a separator, an HTML comment, a note -- inside an
    otherwise complete block: the prompt is visibly right there, so the message
    reads as a checker bug and the real line goes unlooked at.
    """

    section = _normalize_text(section)
    # Name the heading the author actually has to write, not this one's default:
    # the keyframe caller passes a different one, and pointing at the wrong
    # heading is worse than saying nothing.
    label = "### " + re.sub(r"\(\?:([^)]*)\)\?", "", heading).replace("\\", "")
    markers = list(
        re.finditer(rf"^###[ \t\u3000]+{heading}[ \t\u3000]*\r?$", section, re.MULTILINE)
    )
    if not markers:
        return f"：没有 `{label}` 小节标题"
    if len(markers) > 1:
        return f"：`{label}` 出现了 {len(markers)} 次，只能有一个"
    body = section[markers[0].end() :]
    following = _COPYABLE_END_RE.search(body)
    if following is not None:
        body = body[: following.start()]
    lines = [line for line in body.splitlines() if line.strip()]
    if not lines:
        return f"：`{label}` 下面是空的"
    intruders = [line for line in lines if not line.startswith(">")]
    if intruders:
        return (
            "：小节内有不以 `>` 开头的行，整块因此不算引用块——"
            f"把它移到小节外，或删掉：{_excerpt(intruders[0])}"
        )
    return "：引用块里只有空白"


def _portable_path(value: str) -> bool:
    if not value or "\\" in value or re.match(r"^[A-Za-z]:", value):
        return False
    parts = value.split("/")
    return not PurePosixPath(value).is_absolute() and not any(
        part in {"", ".", ".."} for part in parts
    )


def _inside(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    resolved_root = root.resolve()
    return resolved == resolved_root or resolved_root in resolved.parents


class EntryIndex(NamedTuple):
    """The document entries a `PLAN-...` locator is allowed to name."""

    # None when that document is not part of a partial check: its locators
    # cannot be resolved, so they are not reported as missing either.
    images: Optional[dict[str, str]]
    shots: Optional[frozenset[str]]


def _slot_matches(value: str) -> list[tuple[int, int, str, tuple[Any, ...]]]:
    """Every `REF-...` and `PLAN-...` slot in `value`, in written order.

    The two patterns cannot match the same span: a REF locator has to be an
    image path and a PLAN locator has to be an `IMG-`/`SHOT-` id.
    """
    found: list[tuple[int, int, str, tuple[Any, ...]]] = []
    for kind, pattern in (("REF", REF_RE), ("PLAN", PLAN_RE)):
        for match in pattern.finditer(value):
            found.append((match.start(), match.end(), kind, match.groups()))
    found.sort(key=lambda item: item[0])
    return found


def _references(
    value: str,
    owner: str,
    project_root: Optional[Path],
    errors: list[str],
    entries: Optional[EntryIndex] = None,
) -> frozenset[str]:
    """Validate one 输入参考图/参考 declaration; return the slot kinds it uses."""
    if _is_none(value):
        return frozenset()
    if AUDIO_IN_IMAGE_FIELD_RE.search(value):
        errors.append(
            f"{owner}: 输入参考图只收图片；角色音色参考写在《视频提示词.md》"
            "该 MOTION 的「- 参考音频：」行"
        )
        return frozenset()
    reference_value = PENDING_REFERENCE_SUFFIX_RE.sub("", value.strip())
    matches = _slot_matches(reference_value)
    cursor = 0
    separators_are_valid = True
    for index, (start, end, _kind, _groups) in enumerate(matches):
        if reference_value[cursor:start] != ("" if index == 0 else "；"):
            separators_are_valid = False
        cursor = end
    trailing = reference_value[cursor:]
    # Counted as slot heads on the same text the slots were matched in. A bare
    # token count would read the `ref-` in a real path like
    # `输入/参考图/ref-许棠.png` as a second slot and reject a correct declaration.
    declared = len(SLOT_HEAD_RE.findall(reference_value))
    kinds = frozenset(item[2] for item in matches)
    if (
        len(matches) != declared
        or not matches
        or not separators_are_valid
        or trailing not in {"", "。"}
    ):
        # A gap list joined with ； reads as a fourth REF slot and would otherwise
        # be reported as broken REF syntax, whose obvious repair is deleting the
        # gap record -- the silent downgrade this contract exists to prevent.
        if "待补参考图" in value and not _has_pending_references(value):
            errors.append(
                f"{owner}: 待补参考图必须写在最后一个 REF 槽位之后，"
                "缺口之间只用、分隔"
            )
        elif MALFORMED_SLOT_ID_RE.search(reference_value):
            errors.append(
                f"{owner}: 槽位 ID 必须使用大写字母、数字与连字符且不超过 80 字符"
                "（REF-[A-Z0-9][A-Z0-9-]{0,79}）"
            )
        elif _contains_plan_token(value) and not _contains_ref_token(value):
            errors.append(f"{owner}: 输入参考图必须使用完整 PLAN 语法")
        else:
            errors.append(f"{owner}: 输入参考图必须使用完整 REF 语法")
        return kinds
    groups = [item[3] for item in matches]
    slot_kinds = [item[2] for item in matches]
    slots = [group[0] for group in groups]
    orders = [int(group[1]) for group in groups]
    locators = [group[2] for group in groups]
    purposes = [(group[4] or "").strip() for group in groups]
    # A declaration made only of PLAN slots is not a REF declaration, so its
    # diagnostics must not send the creator looking for a REF line.
    noun = "PLAN" if kinds == frozenset({"PLAN"}) else "REF"
    if len(slots) != len(set(slots)):
        errors.append(f"{owner}: {noun} 槽位重复")
    if len(orders) != len(set(orders)) or sorted(orders) != list(
        range(1, len(orders) + 1)
    ):
        errors.append(f"{owner}: {noun} 顺序必须唯一且从 1 连续编号")
    # One picture occupies one slot, except when a loop shot binds the exact
    # same frame as both 起始帧 and 结束帧.
    for locator in sorted(set(locators)):
        indices = [i for i, item in enumerate(locators) if item == locator]
        if len(indices) <= 1:
            continue
        if len(indices) == 2 and {purposes[i] for i in indices} == {"起始帧", "结束帧"}:
            continue
        item_noun = "PLAN" if all(slot_kinds[i] == "PLAN" for i in indices) else "REF"
        errors.append(
            f"{owner}: {item_noun} 同一张图只能占一个槽位: {locator}；"
            "保留它的主要用途作为该槽位的用途，把第二个作用写进「控制」"
        )
    for slot, purpose in zip(slots, purposes):
        if not purpose:
            errors.append(
                f"{owner}: {noun} 缺少用途: {slot}；用途只能是"
                f"{'、'.join(REF_PURPOSES)}其中一个"
            )
        elif purpose not in REF_PURPOSES:
            errors.append(
                f"{owner}: {noun} 用途不在允许集合内: {slot}（{purpose}）；"
                f"只能是{'、'.join(REF_PURPOSES)}"
            )
    for role in ("起始帧", "结束帧"):
        if purposes.count(role) > 1:
            errors.append(f"{owner}: 同一条目只能有一张{role}参考图")
    if "结束帧" in purposes and "起始帧" not in purposes:
        errors.append(f"{owner}: 绑定结束帧参考图时必须同时绑定起始帧")
    for index, (kind, group) in enumerate(zip(slot_kinds, groups)):
        slot, raw_locator, label = group[0], group[2], group[3]
        may_control, must_not_control = group[5], group[6]
        if kind == "REF":
            _check_project_file(raw_locator, owner, project_root, errors)
        else:
            _plan_locator(
                raw_locator, label, owner, slot, purposes[index], entries, errors
            )
        if not label.strip():
            errors.append(f"{owner}: {kind} 缺少名称: {slot}")
        if not may_control.strip() or not must_not_control.strip():
            errors.append(f"{owner}: {kind} 必须同时声明控制与不得控制: {slot}")
        allowed = {item.strip() for item in re.split(r"[、,，]", may_control)}
        prohibited = {item.strip() for item in re.split(r"[、,，]", must_not_control)}
        if "" in allowed or "" in prohibited or allowed & prohibited:
            errors.append(f"{owner}: {kind} 控制与不得控制范围冲突: {slot}")
    return kinds


def _check_project_file(
    locator: str, owner: str, project_root: Optional[Path], errors: list[str]
) -> None:
    """A REF locator names a readable file inside the project, or it is a defect.

    Without a project root (a reader that only has the documents' text) the
    path's shape is still checked; whether the file exists is not.
    """
    if not _portable_path(locator):
        errors.append(f"{owner}: REF 路径不是安全的项目相对路径: {locator}")
        return
    if project_root is None:
        return
    reference_path = project_root / locator
    if not _inside(reference_path, project_root):
        errors.append(f"{owner}: REF 路径越出项目根目录: {locator}")
    elif not reference_path.is_file():
        errors.append(f"{owner}: REF 文件不存在: {locator}")


def _valid_scene_heading_id(line: str) -> Optional[str]:
    match = FULL_SCENE_HEADING_RE.fullmatch(line)
    if match is None:
        return None
    if not match.group("location").strip() or not match.group("time").strip():
        return None
    return match.group("scene")


def _screenplay_dialogue(screenplay: str) -> set[str]:
    """Every speaking character in 剧本.md, read the way screenplay_index.py reads it.

    Mirrors `_parse_screenplay` block by block: closed comments are stripped with
    line preservation, and an unclosed comment ends the parse; a heading sets or
    clears the scene (scene ids use FULL_SCENE_HEADING_RE); a paragraph runs
    until a blank line, a heading or a comment and counts only inside a scene; a
    later line that starts another block means a missing separator, so the
    paragraph is not dialogue.
    """
    screenplay = _strip_html_comments(screenplay)
    speakers: set[str] = set()
    scene: Optional[str] = None
    seen_first_scene = False
    at_scene_head = False
    lines = screenplay.splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("<!--"):
            end = index
            while end < len(lines) and "-->" not in lines[end]:
                end += 1
            if end >= len(lines):
                break
            index = end + 1
            continue
        if stripped.startswith("#"):
            if re.match(r"^##(?![#])", stripped):
                seen_first_scene = True
                scene = _valid_scene_heading_id(stripped)
                at_scene_head = scene is not None
            else:
                if seen_first_scene:
                    scene = None
                    at_scene_head = False
            index += 1
            continue
        if (not seen_first_scene or at_scene_head) and CAST_LINE_RE.match(raw_line):
            index += 1
            continue
        was_before_first_scene = not seen_first_scene
        at_scene_head = False
        end = index
        while end + 1 < len(lines):
            next_raw = lines[end + 1]
            following = next_raw.strip()
            if not following or following.startswith(("#", "<!--")):
                break
            if was_before_first_scene and CAST_LINE_RE.match(next_raw):
                break
            end += 1
        paragraph = [line.strip() for line in lines[index : end + 1]]
        index = end + 1
        if scene is None or any(
            SCREENPLAY_DIALOGUE_RE.fullmatch(line) or SCREENPLAY_BLOCK_START_RE.match(line)
            for line in paragraph[1:]
        ):
            continue
        text = "\n".join(paragraph)
        match = SCREENPLAY_VOICE_TAG_RE.fullmatch(text) or SCREENPLAY_DIALOGUE_RE.fullmatch(
            text
        )
        if match is not None and match.group("text").strip():
            speakers.add(match.group("speaker"))
    return speakers


def _voice_records(visual: str, errors: list[str]) -> dict[str, str]:
    """Each 人物 entry's `- 声音参考：` value, keyed by the entry name."""
    visual = _normalize_text(visual)
    headings = list(re.finditer(r"^##[ \t\u3000]+[^\n]*$", visual, re.MULTILINE))
    records: dict[str, str] = {}
    for index, heading in enumerate(headings):
        entry = VISUAL_SETTING_HEADING_RE.match(heading.group(0))
        if entry is None or entry.group(1) != "人物":
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else None
        declared = VOICE_RECORD_RE.findall(visual[heading.end() : end])
        if len(declared) > 1:
            errors.append(f"视觉设定.md: 人物「{entry.group(2).strip()}」的声音参考重复，只能登记一条")
        elif declared:
            records[entry.group(2).strip()] = _plain(declared[0])
    return records


def _role_voices(visual: str, errors: list[str]) -> dict[str, str]:
    """Each 人物 entry's `- 角色声线：` value, keyed by the entry name."""
    visual = _normalize_text(visual)
    for line in ROLE_VOICE_LINE_RE.findall(visual):
        match = ROLE_VOICE_RE.match(line)
        if match is None or not _plain(match.group(1)):
            errors.append(
                "视觉设定.md: 角色声线必须写成 `- 角色声线：<声线说明>`: " + _excerpt(line)
            )
    headings = list(re.finditer(r"^##[ \t\u3000]+[^\n]*$", visual, re.MULTILINE))
    voices: dict[str, str] = {}
    for index, heading in enumerate(headings):
        entry = VISUAL_SETTING_HEADING_RE.match(heading.group(0))
        if entry is None or entry.group(1) != "人物":
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else None
        declared = ROLE_VOICE_RE.findall(visual[heading.end() : end])
        if len(declared) > 1:
            errors.append(f"视觉设定.md: 人物「{entry.group(2).strip()}」的角色声线重复，只能登记一条")
        elif declared:
            value = _plain(declared[0])
            if value:
                voices[entry.group(2).strip()] = value
    return voices


def _check_role_voices(
    visual_entries: list[VisualEntry],
    role_voices: dict[str, str],
    voices: "VoiceContext",
    errors: list[str],
) -> None:
    """When voice direction is declared, require it only on speaking characters."""
    if not (voices.has_visual and voices.has_screenplay) or not role_voices:
        return
    speaking = voices.dialogue
    for entry in visual_entries:
        if entry.category != "人物" or entry.name not in speaking:
            continue
        declared = role_voices.get(entry.name, "")
        if not declared or _is_none(declared):
            errors.append(
                f"视觉设定.md: 人物「{entry.name}」在《剧本.md》中有发声台词，缺少角色声线字段"
            )


class VoiceContext(NamedTuple):
    """What a MOTION's 参考音频 line is checked against."""

    characters: frozenset[str]
    records: dict[str, str]
    dialogue: set[str]
    # False when that document is not part of a partial check: the checks
    # that read it are skipped instead of reporting every name as unknown.
    has_visual: bool = True
    has_screenplay: bool = True


def _audio_references(
    value: str,
    owner: str,
    project_root: Optional[Path],
    errors: list[str],
    *,
    image_slots: list[str],
    voices: VoiceContext,
) -> None:
    """Validate one MOTION's 参考音频 line against the character it names."""
    if _is_none(value):
        return
    plain = value.strip()
    matches = list(AUDIO_REF_RE.finditer(plain))
    cursor = 0
    for index, match in enumerate(matches):
        if plain[cursor : match.start()] != ("" if index == 0 else "；"):
            matches = []
            break
        cursor = match.end()
    if not matches or plain[cursor:] not in {"", "。"}:
        if MALFORMED_SLOT_ID_RE.search(plain):
            errors.append(
                f"{owner}: 参考音频槽位 ID 必须使用大写字母、数字与连字符且不超过 80 字符"
                "（REF-[A-Z0-9][A-Z0-9-]{0,79}）"
            )
        else:
            errors.append(f"{owner}: 参考音频必须写成 {AUDIO_SYNTAX}，多条用；连接")
        return
    slots = [match.group(1) for match in matches]
    orders = sorted(int(match.group(2)) for match in matches)
    if len(set(slots)) != len(slots) or set(slots) & set(image_slots):
        errors.append(f"{owner}: 参考音频槽位重复，或与输入参考图的槽位重名")
    if orders != list(range(1, len(orders) + 1)):
        errors.append(f"{owner}: 参考音频顺序必须唯一且从 1 连续编号，与图片分开数")
    speakers = [match.group(6).strip() for match in matches]
    for name in sorted({name for name in speakers if speakers.count(name) > 1}):
        errors.append(f"{owner}: 人物「{name}」绑定了不止一条参考音频")
    for match in matches:
        slot, _, locator, label, purpose, _, may, must = match.groups()
        name = match.group(6).strip()
        _check_project_file(locator, owner, project_root, errors)
        if purpose.strip() != AUDIO_PURPOSE:
            errors.append(
                f"{owner}: 参考音频用途只能是{AUDIO_PURPOSE}: {slot}（{purpose.strip()}）"
            )
        if not label.strip():
            errors.append(f"{owner}: REF 缺少名称: {slot}")
        allowed = {item.strip() for item in re.split(r"[、,，]", may)}
        prohibited = {item.strip() for item in re.split(r"[、,，]", must)}
        if "" in allowed or "" in prohibited or allowed & prohibited:
            errors.append(f"{owner}: REF 控制与不得控制范围冲突: {slot}")
        if voices.has_visual and name not in voices.characters:
            errors.append(
                f"{owner}: 参考音频的角色不是《视觉设定.md》里的人物条目: {name}"
            )
            continue
        if not voices.has_visual:
            continue
        record = voices.records.get(name)
        recorded = VOICE_RECORD_PATH_RE.match(record.strip()) if record else None
        if record is None:
            errors.append(
                f"{owner}: 《视觉设定.md》人物「{name}」没有声音参考行；"
                "先在该人物条目下写「- 声音参考：<项目相对路径>（…）」"
            )
        elif recorded is None:
            errors.append(
                f"{owner}: 《视觉设定.md》人物「{name}」的声音参考还没有音频路径: "
                f"{_excerpt(record, 24)}"
            )
        elif recorded.group(1) != locator:
            errors.append(
                f"{owner}: 参考音频 {slot} 的路径 {locator} 与《视觉设定.md》"
                f"人物「{name}」登记的声音参考 {recorded.group(1)} 不一致"
            )


def _plan_locator(
    locator: str,
    label: str,
    owner: str,
    slot: str,
    purpose: str,
    entries: Optional[EntryIndex],
    errors: list[str],
) -> None:
    """A planned picture still has to name an entry that exists today.

    The picture itself is the creator's to supply, but what it depicts is
    already decided by an `IMG-...` board or a `SHOT-...` frozen keyframe. A
    locator that resolves to neither is a reference nobody can act on.
    """
    if entries is None:
        return
    if locator.startswith("IMG-"):
        if entries.images is None:
            return
        if locator not in entries.images:
            errors.append(f"{owner}: PLAN 指向不存在的 IMG 条目: {locator}")
        elif label != entries.images[locator]:
            errors.append(f"{owner}: PLAN 名称与 IMG 标题不一致: {slot}")
    elif locator.startswith("SHOT-"):
        if entries.shots is None:
            return
        if locator not in entries.shots:
            errors.append(f"{owner}: PLAN 指向不存在的 SHOT 条目: {locator}")
    else:
        errors.append(
            f"{owner}: PLAN 定位符只能是 IMG-... 或 SHOT-...: {locator}"
        )


def _excerpt(value: str, limit: int = 60) -> str:
    """A short, single-line quote of an offending line for a diagnostic."""
    collapsed = re.sub(r"\s+", " ", value).strip()
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def _unique(values: "Iterable[str]") -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


class VisualEntry(NamedTuple):
    """One `视觉设定.md` entry plus its declared screen-name designators."""

    category: str
    name: str
    designators: list[str]
    has_screen_name: bool = False

    @property
    def key(self) -> tuple[str, str]:
        return (self.category, self.name)


def _visual_entries(document: str, errors: list[str]) -> list[VisualEntry]:
    """Parse the 人物/造型/地点/道具 entries of one `视觉设定.md`.

    A heading that *looks* like an entry but does not parse would silently drop
    out of the coverage check and then reappear as "出场设定 names an entry that
    does not exist", so it is rejected here where the cause is visible.
    """
    document = _normalize_text(document)
    for line in VISUAL_SETTING_LINE_RE.findall(document):
        if VISUAL_SETTING_HEADING_RE.match(line) is None:
            errors.append(
                "视觉设定.md: 条目标题必须写成 `## <人物|造型|地点|道具> · <名称>`: "
                + _excerpt(line)
            )
    for line in SCREEN_NAME_LINE_RE.findall(document):
        if SCREEN_NAME_RE.match(line) is None:
            errors.append(
                "视觉设定.md: 提示词名称必须写成 `- 提示词名称：<正文里的拼写>`: "
                + _excerpt(line)
            )
    any_headings = [match.start() for match in ANY_SECTION_RE.finditer(document)]
    headings = list(VISUAL_SETTING_HEADING_RE.finditer(document))
    entries: list[VisualEntry] = []
    seen: set[tuple[str, str]] = set()
    for heading in headings:
        end = next(
            (at for at in any_headings if at > heading.start()),
            len(document),
        )
        category, name = heading.group(1), heading.group(2).strip()
        if not name:
            errors.append(f"视觉设定.md: {category}条目缺少名称")
            continue
        if (category, name) in seen:
            errors.append(f"视觉设定.md: 条目重复: {category}「{name}」")
            continue
        seen.add((category, name))
        section_body = document[heading.end() : end]
        declared = SCREEN_NAME_RE.findall(section_body)
        if not declared:
            # No declaration: the entry's own name is the designator, which is
            # what a prompt body written in the project's own language calls it.
            designators = [name]
        elif all(_is_none(_plain(raw)) for raw in declared):
            # `提示词名称：无` is the deliberate opt-out for a name too common to
            # match reliably in prose (道具「手机」 against 手机店). It removes the
            # derived name too, otherwise the opt-out would do nothing.
            designators = []
        else:
            designators = []
            for raw in declared:
                value = _plain(raw)
                if _is_none(value):
                    continue
                for item in re.split(r"[、,，]", value):
                    item = item.strip()
                    if item and item not in designators:
                        designators.append(item)
        # Only a *declared* designator earns this diagnostic: the creator chose a
        # spelling the matcher cannot honour and deserves to know. A one-character
        # entry name they never declared is simply not name-matched, the same as
        # any entry in a project whose prompt body is written in another language.
        if declared:
            for designator in designators:
                if len(designator.strip()) < 2:
                    errors.append(
                        f"视觉设定.md: {category}「{name}」的提示词名称「{designator}」"
                        "过短，无法在正文中可靠识别；请写成至少两个字符，或写「提示词名称：无」"
                    )
        entries.append(
            VisualEntry(
                category,
                name,
                designators,
                bool(declared),
            )
        )
    return entries


def _resolve_entry(
    key: tuple[str, str],
    known: set[tuple[str, str]],
    other_headings: dict[str, str],
    owner: str,
    errors: list[str],
) -> None:
    if key in known:
        return
    category, name = key
    section = other_headings.get(name)
    if section is not None:
        errors.append(
            f"{owner}: 《视觉设定.md》里有「{name}」，但它的分节词是「{section}」；"
            "条目标题必须写成 `## <人物|造型|地点|道具> · <名称>`"
        )
    else:
        errors.append(
            f"{owner}: 出场设定指向不存在的《视觉设定.md》条目: {category}「{name}」"
        )


def _visual_basis(
    value: str,
    owner: str,
    entries: list[VisualEntry],
    other_headings: dict[str, str],
    errors: list[str],
) -> None:
    """Validate one shot's 出场设定 and resolve it against `视觉设定.md`."""
    if _is_none(value):
        return
    plain = _plain(value)
    offscreen_raw = ""
    if OFFSCREEN_PREFIX in plain:
        plain, _, offscreen_raw = plain.partition(OFFSCREEN_PREFIX)
    prefixed = plain.startswith(VISUAL_BASIS_PREFIX)
    body = plain[len(VISUAL_BASIS_PREFIX) :] if prefixed else ""
    matches = list(VISUAL_BASIS_ENTRY_RE.finditer(body)) if prefixed else []
    cursor = 0
    separators_are_valid = True
    for index, match in enumerate(matches):
        # Repeating 《视觉设定.md》· before each entry says the same thing and
        # reads naturally; rejecting it would cost a round trip over nothing.
        separator = body[cursor : match.start()]
        allowed = (
            {""}
            if index == 0
            else {"；", "；" + VISUAL_BASIS_PREFIX}
        )
        if separator not in allowed:
            separators_are_valid = False
        cursor = match.end()
    if not prefixed or not matches or not separators_are_valid or body[cursor:]:
        errors.append(
            f"{owner}: 出场设定必须使用完整语法："
            "《视觉设定.md》·<人物|造型|地点|道具>「<名称>」（控制：<范围>），多项用；连接"
        )
        return
    known = {entry.key for entry in entries}
    declared: set[tuple[str, str]] = set()
    for match in matches:
        key = (match.group(1), match.group(2).strip())
        if key in declared:
            errors.append(f"{owner}: 出场设定条目重复: {key[0]}「{key[1]}」")
        declared.add(key)
        _resolve_entry(key, known, other_headings, owner, errors)
        if not match.group(3).strip():
            errors.append(f"{owner}: 出场设定缺少控制范围: {key[0]}「{key[1]}」")
    if offscreen_raw:
        offscreen_raw = offscreen_raw.replace(VISUAL_BASIS_PREFIX, "")
        remainder = OFFSCREEN_ENTRY_RE.sub("", offscreen_raw).strip("；、 ")
        offscreen_matches = list(OFFSCREEN_ENTRY_RE.finditer(offscreen_raw))
        if not offscreen_matches or remainder:
            errors.append(
                f"{owner}: 画外清单必须写成 `；画外：<人物|造型|地点|道具>「<名称>」`，多项用；连接"
            )
            return
        for match in offscreen_matches:
            key = (match.group(1), match.group(2).strip())
            if key in declared:
                errors.append(
                    f"{owner}: {key[0]}「{key[1]}」同时写进出场设定和画外清单"
                )
            _resolve_entry(key, known, other_headings, owner, errors)


class ContinuityLock(NamedTuple):
    """One declared cross-shot lock: the exact surface and where it applies."""

    lock_id: str
    surface: str
    shots: list[str]
    images: list[str]
    # The 人物/造型/地点/道具 entry the lock line sits under. `镜头：入画` scopes
    # the lock to every shot whose 出场设定 lists that entry, so the lock can
    # be written before any shot exists.
    entry: Optional[tuple[str, str]] = None


def _continuity_locks(document: str, errors: list[str]) -> list[ContinuityLock]:
    """Parse the declared continuity locks of one 视觉设定.md."""
    document = _normalize_text(document)
    locks: list[ContinuityLock] = []
    seen: set[str] = set()
    sections = [match.start() for match in ANY_SECTION_RE.finditer(document)]
    for found in LOCK_LINE_RE.finditer(document):
        line = found.group(0)
        # Only the section the line actually sits in owns it; a lock under a
        # report or note heading belongs to no entry.
        start = next((at for at in reversed(sections) if at < found.start()), None)
        owner = (
            VISUAL_SETTING_HEADING_RE.match(document, start) if start is not None else None
        )
        entry = (owner.group(1), owner.group(2).strip()) if owner else None
        match = LOCK_RE.match(line)
        if match is None:
            errors.append(
                "视觉设定.md: 连戏锁必须使用完整语法: " + _excerpt(line)
            )
            continue
        lock_id, label, scope, image_scope, surface = match.groups()
        if lock_id in seen:
            errors.append(f"{lock_id}: 连戏锁 ID 重复")
            continue
        seen.add(lock_id)
        if not label.strip():
            errors.append(f"{lock_id}: 连戏锁缺少名称")
        surface = _plain(surface)
        if not surface:
            errors.append(f"{lock_id}: 连戏锁缺少锁定词")
            continue
        shots = _unique(
            item.strip() for item in re.split(r"[、,，]", _plain(scope)) if item.strip()
        )
        if not shots:
            errors.append(f"{lock_id}: 连戏锁缺少镜头范围")
            continue
        malformed = [
            item
            for item in shots
            if item not in ("全集", IN_FRAME_SCOPE) and not re.fullmatch(r"SHOT-[A-Z0-9-]+", item)
        ]
        if malformed:
            errors.append(
                f"{lock_id}: 连戏锁的镜头范围只能写入画、全集或 SHOT-... 列表: {'、'.join(malformed)}"
            )
            continue
        if "全集" in shots and len(shots) != 1:
            errors.append(f"{lock_id}: 连戏锁的镜头范围不能把全集与具体镜头混写")
            continue
        if IN_FRAME_SCOPE in shots and len(shots) != 1:
            errors.append(f"{lock_id}: 连戏锁的镜头范围写「入画」时不能再列其他镜头")
            continue
        if shots == [IN_FRAME_SCOPE] and entry is None:
            errors.append(
                f"{lock_id}: 镜头范围写「入画」的锁必须写在某个人物、造型、地点或道具条目下"
            )
            continue
        images: list[str] = []
        if image_scope is not None and not _is_none(image_scope):
            images = _unique(
                item.strip()
                for item in re.split(r"[、,，]", _plain(image_scope))
                if item.strip()
            )
            if any(not item.startswith("IMG-") for item in images):
                errors.append(f"{lock_id}: 连戏锁的图片提示词项必须使用 IMG-  ID")
                continue
        locks.append(ContinuityLock(lock_id, surface, shots, images, entry))
    return locks


def _infer_prompt_language(
    copyable_prompts: Iterable[Optional[str]],
    fallback_texts: Iterable[str] = (),
) -> str:
    unquoted_prompts = [
        QUOTE_RE.sub("", re.sub(r"<d>[\s\S]*?</d>", "", prompt))
        for prompt in copyable_prompts
        if prompt is not None and prompt.strip()
    ]
    if unquoted_prompts:
        combined = "\n".join(unquoted_prompts)
        cjk_count = len(re.findall(r"[\u3400-\u9fff]", combined))
        ascii_alpha_count = len(re.findall(r"[A-Za-z]", combined))
        if cjk_count > 0 and cjk_count * 3 >= ascii_alpha_count:
            return "zh-CN"
        return "en"
    for text in fallback_texts:
        if text and re.search(r"[\u3400-\u9fff]", text):
            return "zh-CN"
    return "en"


def _load_manifest_dict(project_root: Optional[Path]) -> Optional[dict[str, Any]]:
    if project_root is None:
        return None
    configuration = project_root / "short-drama.json"
    if not configuration.is_file():
        return None
    try:
        project = json.loads(configuration.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return project if isinstance(project, dict) else None


def _prompt_language(
    project_root: Optional[Path],
    *,
    family: str = "image",
    copyable_prompts: Iterable[Optional[str]] = (),
    fallback_texts: Iterable[str] = (),
) -> str:
    """The language a copyable prompt body is written in for ``family``.

    Reads `short-drama.json` when present (`format.prompt_language` for image
    and keyframe prompts; accepted `video_prompt_language` falling back to
    `format.prompt_language` for video prompts); otherwise infers `zh-CN` vs
    `en` from actual unquoted prompt text (or present Chinese documents before
    prompts exist) instead of blindly forcing `en`.
    """
    if project_root is None:
        return ""
    project = _load_manifest_dict(project_root)
    if project is None:
        return _infer_prompt_language(copyable_prompts, fallback_texts)
    formats = project.get("format")
    general = formats.get("prompt_language") if isinstance(formats, dict) else None
    general_lang = general if isinstance(general, str) and general else "en"
    if family == "video":
        authority = project.get("creator_authority")
        profile = (
            authority.get("production_profile") if isinstance(authority, dict) else None
        )
        if isinstance(profile, dict) and profile.get("status") == "accepted":
            choices = profile.get("choices")
            if isinstance(choices, dict):
                declared = choices.get("video_prompt_language")
                if isinstance(declared, str) and declared:
                    return declared
    return general_lang


def _check_language_designators(
    project_root: Optional[Path],
    *,
    entries: list[VisualEntry],
    warnings: list[str],
    has_image_family: bool = False,
    has_video_family: bool = False,
    image_prompts: Iterable[Optional[str]] = (),
    video_prompts: Iterable[Optional[str]] = (),
    copyable_prompts: Iterable[Optional[str]] = (),
    fallback_texts: Iterable[str] = (),
) -> None:
    """Emit soft warnings when a character lacks a cross-language prompt designator."""
    if project_root is None:
        # Without a project root the prompt language is unknown; validate_documents
        # promises to skip what needs the disk rather than guess a language.
        return
    project = _load_manifest_dict(project_root)
    active_languages: list[str] = []
    if project is not None:
        img_lang = _prompt_language(project_root, family="image")
        vid_lang = _prompt_language(project_root, family="video")
        if has_image_family:
            active_languages.append(img_lang)
        if has_video_family:
            active_languages.append(vid_lang)
        if not active_languages:
            active_languages.extend([img_lang, vid_lang])
    else:
        img_texts = [p for p in image_prompts if p is not None and p.strip()]
        vid_texts = [p for p in video_prompts if p is not None and p.strip()]
        legacy_texts = [p for p in copyable_prompts if p is not None and p.strip()]
        if img_texts:
            active_languages.append(_infer_prompt_language(img_texts))
        if vid_texts:
            active_languages.append(_infer_prompt_language(vid_texts))
        if not active_languages and legacy_texts:
            active_languages.append(_infer_prompt_language(legacy_texts))
        if not active_languages:
            active_languages.append(_infer_prompt_language((), fallback_texts))
    has_zh_prompt = any(lang.casefold().startswith("zh") for lang in active_languages)
    has_non_zh_prompt = any(
        not lang.casefold().startswith("zh") for lang in active_languages
    )
    for entry in entries:
        if entry.category != "人物":
            continue
        if not entry.has_screen_name and entry.designators == [entry.name]:
            name_has_zh = bool(re.search(r"[\u3400-\u9fff]", entry.name))
            if name_has_zh and has_non_zh_prompt:
                warnings.append(
                    f"视觉设定.md: 人物「{entry.name}」缺少提示词名称；"
                    "提示词正文不是中文时，写「提示词名称：<正文里的拼写>」，"
                    "正文从不点名时写「提示词名称：无」"
                )
            elif not name_has_zh and has_zh_prompt:
                warnings.append(
                    f"视觉设定.md: 人物「{entry.name}」缺少提示词名称；"
                    "提示词正文是中文时，写「提示词名称：<正文里的拼写>」，"
                    "正文从不点名时写「提示词名称：无」"
                )


def _declared_seconds(value: str) -> Optional[float]:
    """The number of seconds a 时长 field declares, however it is spelled.

    `4s`, `4 秒` and `4秒` are the same duration. Returning None for anything
    else keeps an unparseable value out of the comparison instead of turning a
    formatting difference into a false duration conflict.
    """
    match = re.search(r"(\d+(?:\.\d+)?)", value or "")
    return float(match.group(1)) if match else None


def _check_continuity_locks(
    locks: list[ContinuityLock],
    *,
    shots: Optional[dict[str, str]],
    image_prompts: Optional[dict[str, Optional[str]]],
    errors: list[str],
) -> None:
    """Validate deterministic SHOT-/IMG- cross-references on declared locks.

    Whether free prompt prose semantically preserves a lock's visual detail
    belongs to semantic review (`short-drama-review`), not substring scanning.
    """
    for lock in locks:
        lock_id = lock.lock_id
        if shots is not None and lock.shots not in (["全集"], [IN_FRAME_SCOPE]):
            for shot_id in lock.shots:
                if shot_id not in shots:
                    errors.append(f"{lock_id}: 连戏锁指向不存在的镜头: {shot_id}")
        if image_prompts is not None:
            for image_id in lock.images:
                if image_id not in image_prompts:
                    errors.append(f"{lock_id}: 连戏锁指向不存在的 IMG 条目: {image_id}")


def _group_members(value: str) -> list[str]:
    """A GROUP's 成员 field exactly as written, repeats and typos included."""
    return [item.strip() for item in re.split(r"[、,，]", _plain(value)) if item.strip()]

def _check_delivery_groups(
    groups: dict[str, str],
    *,
    video: str,
    motions: dict[str, str],
    motion_duration: dict[str, str],
    shot_order: Optional[list[str]],
    shot_scenes: dict[str, list[str]],
    errors: list[str],
    project_root: Optional[Path] = None,
    entries: Optional[EntryIndex] = None,
    motion_fields_by_id: Optional[Mapping[str, Mapping[str, str]]] = None,
    partial: bool = False,
    voices: Optional[VoiceContext] = None,
) -> dict[str, tuple[list[str], Optional[str], str]]:
    """Check the multi-shot delivery groups of 视频提示词.md (VID-13, VID-15)."""
    result: dict[str, tuple[list[str], Optional[str], str]] = {}
    owner_of: dict[str, str] = {}
    titled = dict(
        re.findall(r"^##[ \t\u3000]+(GROUP-[A-Z0-9-]+) · ([^\r\n]+)\r?$", video, re.MULTILINE)
    )
    shot_of_motion = {
        motion_id: _plain(
            (
                motion_fields_by_id[motion_id]
                if motion_fields_by_id is not None and motion_id in motion_fields_by_id
                else _fields(body, owner=motion_id, errors=[])
            ).get("分镜", "")
        )
        for motion_id, body in motions.items()
    }
    for group_id, body in groups.items():
        if not titled.get(group_id, "").strip():
            errors.append(f"{group_id}: 合生分组标题必须写成 ## GROUP-... · <名称>")
        fields = _fields(body, owner=group_id, errors=errors)
        group_input = fields.get("输入参考图", "")
        if group_input:
            _references(group_input, group_id, project_root, errors, entries)
            if not partial and _has_pending_references(group_input):
                errors.append(f"{group_id}: 仍有待补参考图，不能生成最终视频提示词")
        listed = _group_members(fields.get("成员", ""))
        members = _unique(listed)
        if len(members) != len(listed):
            errors.append(f"{group_id}: 成员重复；一次合生里每个镜头只出现一次")
        prompt = _copyable_prompt(body)
        if prompt is None:
            errors.append(
                f"{group_id}: 缺少唯一且非空的可复制提示词" + _copyable_prompt_cause(body)
            )
        unknown = [item for item in members if item not in motions]
        if "参考音频" in fields and voices is not None:
            _audio_references(
                fields["参考音频"],
                group_id,
                project_root,
                errors,
                image_slots=[
                    item[3][0]
                    for item in _slot_matches(
                        PENDING_REFERENCE_SUFFIX_RE.sub("", group_input.strip())
                    )
                ],
                voices=voices,
            )
        if not members:
            errors.append(f"{group_id}: 缺少成员字段")
            continue
        for item in unknown:
            errors.append(f"{group_id}: 成员不是已有的 MOTION 条目: {item}")
        for item in members:
            if item in owner_of:
                errors.append(f"{group_id}: {item} 已属于 {owner_of[item]}，一个镜头只能进一个合生分组")
            owner_of.setdefault(item, group_id)
        if unknown:
            continue
        member_shots = [shot_of_motion[item] for item in members]
        result[group_id] = (member_shots, prompt, group_input)
        seconds = [_declared_seconds(motion_duration.get(shot, "")) for shot in member_shots]
        known = [value for value in seconds if value is not None]
        for shot, value in zip(member_shots, seconds):
            if value is None:
                errors.append(f"{group_id}: 成员 {shot} 没有可解析的时长，无法核对分组时长")
        declared = _declared_seconds(_plain(fields.get("时长", "")))
        if declared is None:
            errors.append(f"{group_id}: 缺少可解析的时长")
        elif len(known) == len(seconds) and abs(declared - sum(known)) > 1e-6:
            errors.append(
                f"{group_id}: 分组时长 {declared:g} 秒不等于成员时长之和 {sum(known):g} 秒"
            )
        if shot_order is not None:
            positions = [shot_order.index(shot) for shot in member_shots if shot in shot_order]
            if len(positions) == len(member_shots) and positions != list(
                range(positions[0], positions[0] + len(positions))
            ):
                errors.append(f"{group_id}: 成员必须是分镜里按顺序相邻的镜头")
            scenes = {scene for shot in member_shots for scene in shot_scenes.get(shot, [])}
            if len(scenes) > 1:
                errors.append(
                    f"{group_id}: 合生分组不能跨场次: {'、'.join(sorted(scenes))}"
                )
    return result


def _storyboard_head(storyboard: str) -> str:
    """The part of 分镜.md that belongs to the episode rather than to a shot."""
    match = re.search(r"^##[ \t\u3000]+SHOT-", storyboard, re.MULTILINE)
    return storyboard if match is None else storyboard[: match.start()]


def _shot_sources(
    value: str, owner: str, scenes: "Optional[frozenset[str]]", errors: list[str]
) -> list[str]:
    """Resolve one shot's 来源 against the scene ids that exist in 剧本.md.

    ``scenes`` is None when 剧本.md is not part of a partial check; the ids are
    then taken as written.
    """
    plain = _plain(value)
    if not plain:
        errors.append(f"{owner}: 缺少来源字段")
        return []
    # 《镜头手艺》 asks for the scene id plus a short quote of the source line,
    # and a quote contains commas of its own. So the ids are read out of the
    # field rather than by cutting it into pieces on punctuation.
    if SCENE_ID_RE.match(plain) is None:
        errors.append(
            f"{owner}: 来源必须以《剧本.md》的场景 ID 开头: {_excerpt(plain, 24)}"
        )
        return []
    resolved = []
    # A quote may itself mention another scene (「…与 EP001-SC001 同一客厅…」);
    # that id is quoted text, not a scene this shot carries.
    unquoted = QUOTE_RE.sub("", plain)
    for scene_id in _unique(SCENE_ID_RE.findall(unquoted)):
        if scenes is not None and scene_id not in scenes:
            errors.append(f"{owner}: 来源场景不在《剧本.md》中: {scene_id}")
        else:
            resolved.append(scene_id)
    return resolved


def _unfilmed_scenes(
    storyboard: str, scenes: "frozenset[str]", errors: list[str]
) -> dict[str, str]:
    """Scenes 分镜.md declares it deliberately does not film, with reasons."""
    head = _storyboard_head(storyboard)
    declared: dict[str, str] = {}
    # The line belongs to the episode, not to a shot. Placed inside a SHOT
    # section it would be read as that shot's field and quietly do nothing,
    # which looks exactly like forgetting to write it.
    if len(UNFILMED_LINE_RE.findall(storyboard)) != len(
        UNFILMED_LINE_RE.findall(head)
    ):
        errors.append("分镜.md: 未拍场次要写在第一个 SHOT 之前的正文开头")
    for value in UNFILMED_LINE_RE.findall(head):
        value = value.strip()
        entries = UNFILMED_ENTRY_RE.findall(value)
        remainder = UNFILMED_ENTRY_RE.sub("", value).strip("；;。 ")
        if not entries or remainder:
            errors.append(
                "分镜.md: 未拍场次必须写成 <场景 ID>（理由：……），多项用；分隔"
            )
            continue
        for scene_id, reason in entries:
            if not reason.strip():
                errors.append(f"分镜.md: 未拍场次缺少理由: {scene_id}")
            elif scene_id not in scenes:
                errors.append(f"分镜.md: 未拍场次不在《剧本.md》中: {scene_id}")
            else:
                declared[scene_id] = reason.strip()
    return declared


def missing_documents(episode: Path) -> list[str]:
    """The creator documents an episode directory does not have yet."""
    return [name for name in REQUIRED_DOCUMENTS if not (episode / name).is_file()]


class ValidationResult(NamedTuple):
    """Structured outcome of validating one episode: blocking errors + soft warnings."""

    errors: list[str]
    warnings: list[str]


def validate_episode_with_warnings(
    episode: Path, project_root: Optional[Path] = None, *, partial: bool = False
) -> ValidationResult:
    """Return blocking contract errors and soft warnings for ``episode``.

    By default all five documents are required. ``partial`` checks only the
    documents that exist: rules that need a missing document are skipped, never
    reported as passing or failing.
    """
    episode = episode.resolve()
    texts = {
        name: (episode / name).read_text(encoding="utf-8")
        for name in REQUIRED_DOCUMENTS
        if (episode / name).is_file()
    }
    return validate_documents_with_warnings(
        texts, (project_root or episode.parent.parent).resolve(), partial=partial
    )


def validate_episode(
    episode: Path, project_root: Optional[Path] = None, *, partial: bool = False
) -> list[str]:
    """Return all blocking deterministic contract errors for ``episode``."""
    return validate_episode_with_warnings(episode, project_root, partial=partial).errors


def collect_warnings(
    texts: "Mapping[str, Optional[str]]",
    project_root: Optional[Path],
    *,
    partial: bool = False,
) -> list[str]:
    """Return only the non-blocking soft warnings for ``texts``."""
    return validate_documents_with_warnings(texts, project_root, partial=partial).warnings


def validate_documents(
    texts: "Mapping[str, Optional[str]]",
    project_root: Optional[Path],
    *,
    partial: bool = False,
) -> list[str]:
    """Return only blocking deterministic contract errors for ``texts``."""
    return validate_documents_with_warnings(texts, project_root, partial=partial).errors


def validate_documents_with_warnings(
    texts: "Mapping[str, Optional[str]]",
    project_root: Optional[Path],
    *,
    partial: bool = False,
) -> ValidationResult:
    """Validate document text in hand, returning blocking errors and soft warnings.

    A missing or None entry is a missing document. ``project_root`` None skips
    only what needs the disk: whether a REF file exists, and the project's
    prompt language.
    """
    errors: list[str] = []
    warnings: list[str] = []
    missing = [name for name in REQUIRED_DOCUMENTS if texts.get(name) is None]
    if missing and not partial:
        return ValidationResult([f"缺少创作文档: {', '.join(missing)}"], [])
    present = frozenset(REQUIRED_DOCUMENTS) - frozenset(missing)
    if not present:
        # A partial check before any document exists has nothing to fail on;
        # the CLI says so instead of reporting an error the creator cannot fix.
        return ValidationResult([], [])

    def read(name: str, *, preserve_copyable: bool = False) -> str:
        raw = _normalize_text(texts.get(name) or "")
        stripped, has_unclosed = _scan_html_comments(
            raw, preserve_copyable=preserve_copyable
        )
        if name in present and has_unclosed:
            errors.append(f"{name}: 存在未闭合的 HTML 注释（缺少 `-->`）")
        return stripped

    has_screenplay = "剧本.md" in present
    has_visual = "视觉设定.md" in present
    has_images = "图片提示词.md" in present
    has_storyboard = "分镜.md" in present
    has_video = "视频提示词.md" in present
    images = read("图片提示词.md", preserve_copyable=True)
    storyboard = read("分镜.md", preserve_copyable=True)
    video = read("视频提示词.md", preserve_copyable=True)
    visual = read("视觉设定.md")
    screenplay = read("剧本.md")
    if has_screenplay:
        for candidate_line in SCENE_LINE_CANDIDATE_RE.findall(screenplay):
            if _valid_scene_heading_id(candidate_line) is None:
                errors.append(
                    "剧本.md: 场景标题必须写成 ## <场景 ID> 内|外|内外 · 地点 · 时间: "
                    + _excerpt(candidate_line)
                )
    scene_headings = [
        match.group("scene")
        for match in FULL_SCENE_HEADING_RE.finditer(screenplay)
        if match.group("location").strip() and match.group("time").strip()
    ]
    scenes = frozenset(scene_headings)
    known_scenes = scenes if has_screenplay else None
    if has_screenplay and not scenes:
        errors.append(
            "剧本.md: 没有可解析的场景标题；场景标题写成 ## <场景 ID> 内|外|内外 · 地点 · 时间"
        )
    if len(scene_headings) != len(scenes):
        errors.append("剧本.md: 场景 ID 重复")
    if has_storyboard:
        for blocking_line in BLOCKING_LINE_RE.findall(storyboard):
            matched_blocking = BLOCKING_HEADING_RE.fullmatch(blocking_line)
            if matched_blocking is None or not matched_blocking.group(2).strip():
                errors.append(
                    "分镜.md: 场景站位标题必须写成 ## 场景站位 · <场景 ID> · <地点名>: "
                    + _excerpt(blocking_line)
                )
            elif known_scenes is not None and matched_blocking.group(1) not in known_scenes:
                errors.append(
                    f"分镜.md: 场景站位场景不在《剧本.md》中: {matched_blocking.group(1)}"
                )
    unfilmed = (
        _unfilmed_scenes(storyboard, scenes, errors)
        if has_storyboard and has_screenplay
        else {}
    )
    claimed_scenes: set[str] = set()
    shot_scene_map: dict[str, list[str]] = {}
    locks = _continuity_locks(visual, errors)
    visual_entries = _visual_entries(visual, errors)
    role_voices = _role_voices(visual, errors)
    voices = VoiceContext(
        characters=frozenset(
            entry.name for entry in visual_entries if entry.category == "人物"
        ),
        records=_voice_records(visual, errors),
        dialogue=_screenplay_dialogue(screenplay),
        has_visual=has_visual,
        has_screenplay=has_screenplay,
    )
    _check_role_voices(visual_entries, role_voices, voices, errors)
    other_headings = {
        match.group(2).strip(): match.group(1).strip()
        for match in OTHER_SETTING_HEADING_RE.finditer(visual)
        if match.group(1).strip() not in VISUAL_CATEGORIES
        and not match.group(1).strip().startswith("MUSIC-")
    }
    shots = _sections(storyboard, "SHOT")
    image_pairs = re.findall(
        r"^##[ \t\u3000]+(IMG-[A-Z0-9-]+) · ([^\r\n]+)\r?$", images, re.MULTILINE
    )
    image_headings = dict(image_pairs)
    # A planned picture names the board or keyframe that already decides what it
    # depicts, so both indexes have to exist before any declaration is read.
    entries = EntryIndex(
        images=image_headings if has_images else None,
        shots=frozenset(shots) if has_storyboard else None,
    )
    all_image_headings = re.findall(
        r"^##[ \t\u3000]+(IMG-[A-Z0-9-]+)\b", images, re.MULTILINE
    )
    if len(image_pairs) != len(all_image_headings) or any(
        not label.strip() for _, label in image_pairs
    ):
        errors.append("图片提示词.md: IMG 标题必须写成 ## IMG-... · <名称>")
    if len(image_pairs) != len(image_headings) or len(all_image_headings) != len(
        set(all_image_headings)
    ):
        errors.append("图片提示词.md: IMG 标题 ID 重复")
    image_prompts: dict[str, Optional[str]] = {}
    for image_id, body in _sections(images, "IMG").items():
        reference_value = _fields(body, owner=image_id, errors=errors).get(
            "参考", ""
        )
        if not reference_value:
            errors.append(f"{image_id}: 缺少参考字段")
        elif _has_pending_references(reference_value) or "待补参考图" in reference_value:
            errors.append(f"{image_id}: 图片提示词参考不能留有待补参考图")
        elif _contains_plan_token(reference_value):
            errors.append(
                f"{image_id}: 图片提示词参考只能使用真实图片 REF 槽位或无外部参考，不能使用 PLAN 槽位"
            )
        elif _is_no_external_reference(reference_value):
            pass
        elif _contains_ref_token(reference_value):
            _references(
                reference_value, image_id, project_root, errors, entries
            )
        else:
            errors.append(
                f"{image_id}: 参考必须声明无外部参考或使用完整 REF 语法"
            )
        image_prompt = _copyable_prompt(body)
        image_prompts[image_id] = image_prompt
        if image_prompt is None:
            errors.append(
                f"{image_id}: 缺少唯一且非空的可复制提示词"
                + _copyable_prompt_cause(body)
            )

    motions = _sections(video, "MOTION")
    shot_ids = re.findall(r"^##[ \t\u3000]+(SHOT-[A-Z0-9-]+)\b", storyboard, re.MULTILINE)
    motion_ids = re.findall(r"^##[ \t\u3000]+(MOTION-[A-Z0-9-]+)\b", video, re.MULTILINE)
    if len(shot_ids) != len(set(shot_ids)):
        errors.append("分镜.md: SHOT 标题 ID 重复")
    if len(motion_ids) != len(set(motion_ids)):
        errors.append("视频提示词.md: MOTION 标题 ID 重复")
    group_ids = re.findall(r"^##[ \t\u3000]+(GROUP-[A-Z0-9-]+)\b", video, re.MULTILINE)
    if len(group_ids) != len(set(group_ids)):
        errors.append("视频提示词.md: GROUP 标题 ID 重复")
    music_ids = re.findall(r"^##[ \t\u3000]+(MUSIC-[A-Z0-9-]+)\b", video, re.MULTILINE)
    if len(music_ids) != len(set(music_ids)):
        errors.append("视频提示词.md: MUSIC 标题 ID 重复")
    named_music = re.findall(
        r"^##[ \t\u3000]+(MUSIC-[A-Z0-9-]+) · ([^\r\n]+)\r?$", video, re.MULTILINE
    )
    if len(named_music) != len(music_ids) or any(
        not label.strip() for _, label in named_music
    ):
        errors.append("视频提示词.md: MUSIC 标题必须写成 ## MUSIC-... · <名称>")
    for music_id, body in _sections(video, "MUSIC").items():
        _fields(body, owner=music_id, errors=errors)
        if (
            re.search(r"^###[ \t\u3000]+可复制提示词[ \t\u3000]*\r?$", body, re.MULTILINE)
            and _copyable_prompt(body) is None
        ):
            errors.append(
                f"{music_id}: 缺少唯一且非空的可复制提示词"
                + _copyable_prompt_cause(body)
            )
    named_shots = re.findall(
        r"^##[ \t\u3000]+(SHOT-[A-Z0-9-]+) · ([^\r\n]+)\r?$", storyboard, re.MULTILINE
    )
    named_motions = re.findall(
        r"^##[ \t\u3000]+(MOTION-[A-Z0-9-]+) · ([^\r\n]+)\r?$", video, re.MULTILINE
    )
    if len(named_shots) != len(shot_ids) or any(
        not label.strip() for _, label in named_shots
    ):
        errors.append("分镜.md: SHOT 标题必须写成 ## SHOT-... · <名称>")
    if len(named_motions) != len(motion_ids) or any(
        not label.strip() for _, label in named_motions
    ):
        errors.append("视频提示词.md: MOTION 标题必须写成 ## MOTION-... · <名称>")
    if has_storyboard and not shots:
        errors.append("分镜.md: 没有 SHOT 条目")
    if has_video and not motions:
        errors.append("视频提示词.md: 没有 MOTION 条目")

    motion_by_shot: dict[str, tuple[str, str, Optional[str]]] = {}
    motion_duration: dict[str, str] = {}
    motion_fields_by_id: dict[str, dict[str, str]] = {}
    motion_prompts_list: list[Optional[str]] = []
    for motion_id, body in motions.items():
        fields = _fields(body, owner=motion_id, errors=errors)
        motion_fields_by_id[motion_id] = fields
        shot_id = _plain(fields.get("分镜", ""))
        motion_duration[shot_id] = _plain(fields.get("时长", ""))
        copyable_prompt = _copyable_prompt(body)
        motion_prompts_list.append(copyable_prompt)
        if not shot_id:
            errors.append(f"{motion_id}: 缺少分镜字段")
        elif shot_id in motion_by_shot:
            errors.append(f"{motion_id}: 分镜 {shot_id} 被多个 MOTION 引用")
        else:
            motion_by_shot[shot_id] = (motion_id, body, copyable_prompt)
        if motion_id.removeprefix("MOTION-") != shot_id.removeprefix("SHOT-"):
            errors.append(f"{motion_id}: ID 必须与分镜 {shot_id} 一一对应")
        if copyable_prompt is None:
            errors.append(
                f"{motion_id}: 缺少唯一且非空的可复制提示词"
                + _copyable_prompt_cause(body)
            )

    if has_storyboard and has_video and set(motion_by_shot) != set(shots):
        errors.append("分镜.md/视频提示词.md: SHOT 与 MOTION 未一一对应")

    def check_motion(
        motion_id: str,
        motion_body: str,
        upstream_input: str,
    ) -> None:
        """MOTION rules evaluated against the MOTION's own 输入参考图."""
        motion_fields = motion_fields_by_id.get(motion_id)
        if motion_fields is None:
            motion_fields = _fields(motion_body, owner=motion_id, errors=errors)
        motion_input = motion_fields.get("输入参考图", "")
        if not motion_input:
            errors.append(f"{motion_id}: 缺少输入参考图字段")
        else:
            _references(motion_input, motion_id, project_root, errors, entries)
        if "参考音频" in motion_fields:
            _audio_references(
                motion_fields["参考音频"],
                motion_id,
                project_root,
                errors,
                image_slots=[
                    item[3][0]
                    for item in _slot_matches(
                        PENDING_REFERENCE_SUFFIX_RE.sub("", motion_input.strip())
                    )
                ],
                voices=voices,
            )

        governing_input = motion_input or upstream_input
        if _has_pending_references(motion_input) or _has_pending_references(upstream_input):
            errors.append(f"{motion_id}: 仍有待补参考图，不能生成最终视频提示词")

        sends_pictures = bool(governing_input) and not _is_none(governing_input)
        expected_mode = "图生视频" if sends_pictures else "文生视频"
        if _plain(motion_fields.get("生成方式", "")) != expected_mode:
            errors.append(f"{motion_id}: 生成方式应为{expected_mode}")
        anchor = _plain(motion_fields.get("开场画面", ""))
        if not sends_pictures:
            if governing_input and not _is_explicit_text_to_video(governing_input):
                errors.append(
                    f"{motion_id}: 无真实输入参考图时不能擅自改成文生视频；"
                    "请先绑定已有图片、列出待补图片，或写「输入参考图：无」"
                )
            if not anchor or anchor == "无":
                errors.append(f"{motion_id}: 文生视频缺少开场画面")

    collected_keyframes: list[Optional[str]] = []
    for shot_id, shot_body in shots.items():
        fields = _fields(shot_body, owner=shot_id, errors=errors)
        source_value = fields.get("来源", "")
        shot_scenes = _shot_sources(source_value, shot_id, known_scenes, errors)
        claimed_scenes.update(shot_scenes)
        shot_scene_map[shot_id] = shot_scenes
        shot_seconds = _declared_seconds(_plain(fields.get("时长", "")))
        motion_seconds = _declared_seconds(motion_duration.get(shot_id, ""))
        if (
            shot_seconds is not None
            and motion_seconds is not None
            and shot_seconds != motion_seconds
        ):
            errors.append(
                f"{shot_id}: 分镜时长 {shot_seconds:g} 秒与视频提示词 "
                f"{motion_seconds:g} 秒不一致；视频提示词时长必须与分镜一致"
            )
        image_value = fields.get("图片提示词项", "")
        if image_value and not _is_none(image_value):
            image_refs = IMG_RE.findall(image_value)
            image_remainder = IMG_RE.sub("", image_value).strip("；。 ")
            if (
                len(image_refs) != len(re.findall(r"\bIMG-[A-Z0-9-]+\b", image_value))
                or image_remainder
            ):
                errors.append(f"{shot_id}: 图片提示词项语法不完整")
            for image_id, label, _ in image_refs:
                if not has_images:
                    continue
                if image_id not in image_headings:
                    errors.append(f"{shot_id}: IMG 标题不存在: {image_id}")
                elif label != image_headings[image_id]:
                    errors.append(f"{shot_id}: IMG 名称与标题不一致: {image_id}")

        shot_input = fields.get("输入参考图", "")
        if not shot_input:
            errors.append(f"{shot_id}: 缺少输入参考图字段")
        else:
            _references(shot_input, shot_id, project_root, errors, entries)
        if "参考音频" in fields:
            errors.append(
                f"{shot_id}: 参考音频写在《视频提示词.md》的 MOTION 条目里，分镜不登记"
            )

        basis_value = fields.get("出场设定", "")
        if not basis_value:
            errors.append(f"{shot_id}: 缺少出场设定字段")
        elif has_visual:
            _visual_basis(
                basis_value, shot_id, visual_entries, other_headings, errors
            )
        keyframe = _copyable_prompt(shot_body, heading=r"首帧提示词")
        collected_keyframes.append(keyframe)
        if keyframe is None:
            errors.append(
                f"{shot_id}: 缺少唯一且非空的首帧提示词"
                + _copyable_prompt_cause(shot_body, heading=r"首帧提示词")
            )
        if re.search(r"^###[ \t\u3000]+尾帧提示词[ \t\u3000]*\r?$", shot_body, re.MULTILINE):
            closing = _copyable_prompt(shot_body, heading=r"尾帧提示词")
            collected_keyframes.append(closing)
            if closing is None:
                errors.append(
                    f"{shot_id}: 尾帧提示词不是唯一且非空的可复制正文"
                    + _copyable_prompt_cause(shot_body, heading=r"尾帧提示词")
                )

        motion = motion_by_shot.get(shot_id)
        if not motion:
            continue
        motion_id, motion_body, _copyable_prompt_unused = motion
        check_motion(motion_id, motion_body, shot_input)

    if not has_storyboard:
        for motion_id, motion_body in motions.items():
            own_input = motion_fields_by_id[motion_id].get("输入参考图", "")
            check_motion(motion_id, motion_body, own_input)

    for scene_id in scene_headings if has_storyboard else ():
        if scene_id in claimed_scenes or scene_id in unfilmed:
            continue
        errors.append(
            f"分镜.md: 场景 {scene_id} 没有对应镜头；"
            "要拍就写进某一镜的来源，不拍就写进未拍场次并给出理由"
        )
    for scene_id in sorted(set(unfilmed) & claimed_scenes):
        errors.append(f"分镜.md: 场景 {scene_id} 既有对应镜头又记为未拍")

    group_members = _check_delivery_groups(
        _sections(video, "GROUP"),
        video=video,
        motions=motions,
        motion_duration=motion_duration,
        shot_order=list(shots) if has_storyboard else None,
        shot_scenes=shot_scene_map,
        errors=errors,
        project_root=project_root,
        entries=entries,
        motion_fields_by_id=motion_fields_by_id,
        partial=partial,
        voices=voices,
    )

    image_family_prompts: list[Optional[str]] = [
        *(image_prompts.values() if has_images else ()),
        *collected_keyframes,
    ]
    video_family_prompts: list[Optional[str]] = [
        *motion_prompts_list,
        *(info[1] for info in group_members.values()),
    ]
    _check_language_designators(
        project_root,
        entries=visual_entries,
        warnings=warnings,
        has_image_family=has_images or has_storyboard,
        has_video_family=has_video,
        image_prompts=image_family_prompts,
        video_prompts=video_family_prompts,
        fallback_texts=(visual if has_visual else "", screenplay if has_screenplay else ""),
    )
    _check_continuity_locks(
        locks,
        shots=shots if has_storyboard else None,
        image_prompts=image_prompts if has_images else None,
        errors=errors,
    )
    return ValidationResult(errors, warnings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path, help="包含五份 Markdown 的剧集目录")
    parser.add_argument("--project-root", type=Path, help="用于解析 REF 项目相对路径")
    parser.add_argument(
        "--partial",
        action="store_true",
        help="只核对已有的文档；缺少的文档相关规则跳过，不算通过也不算失败",
    )
    args = parser.parse_args()
    # 诊断与剧集路径都是中文。stdout 重定向时 Windows 用 ANSI 代码页，默认的
    # strict 处理器会在打印这一步抛错；stderr 早就是 backslashreplace，这里让
    # stdout 用同一个处理器：能编码就照常显示中文，不能编码才退成转义。
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")
    result = validate_episode_with_warnings(
        args.episode, args.project_root, partial=args.partial
    )
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    if result.errors:
        for error in result.errors:
            print(f"ERROR: {error}")
        return 1
    missing = missing_documents(args.episode) if args.partial else []
    if len(missing) == len(REQUIRED_DOCUMENTS):
        print(f"OK（局部）: {args.episode}；还没有创作文档，没有可核对的内容")
    elif missing:
        print(f"OK（局部）: {args.episode}；未核对与这些文档相关的规则: {', '.join(missing)}")
    else:
        print(f"OK: {args.episode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
