#!/usr/bin/env python3
"""Validate the executable cross-document contract of one creator-first episode."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from collections.abc import Iterable, Mapping
from typing import NamedTuple, Optional


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
SECTION_RE = re.compile(r"^## ((?:SHOT|MOTION|GROUP)-[A-Z0-9-]+)\b", re.MULTILINE)
ANY_SECTION_RE = re.compile(r"^## ", re.MULTILINE)
IMG_RE = re.compile(r"\b(IMG-[A-Z0-9-]+)《([^》]+)》（控制：([^）]+)）")
# 用途 is optional in the pattern on purpose: a declaration written before this
# field existed still parses, so the creator gets "REF 缺少用途" instead of the
# generic syntax error that gives no hint about what to add.
REF_RE = re.compile(
    r"(REF-[A-Z0-9-]+)（顺序：([1-9]\d*)）· "
    r"([^；\n]+?\.(?:png|jpe?g|webp))《([^》\n]+)》"
    r"（(?:用途：([^；）\n]+)；)?控制：([^；）]+)；不得控制：([^）]+)）",
    re.IGNORECASE,
)
# The same slot grammar, but the locator is a document entry instead of a file.
# A creator who generates in an external tool never has the file inside the
# project, and the copyable body only ever needed 顺序 and 用途 -- the path is a
# production input, not a prompt input. PLAN says "this picture does not exist
# here; attach it yourself in this order", which is a different claim from
# 「已有图片」 and from 「待补」.
PLAN_RE = re.compile(
    r"(PLAN-[A-Z0-9-]+)（顺序：([1-9]\d*)）· "
    r"((?:IMG|SHOT)-[A-Z0-9-]+)《([^》\n]+)》"
    r"（(?:用途：([^；）\n]+)；)?控制：([^；）]+)；不得控制：([^）]+)）",
    re.IGNORECASE,
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
AUDIO_SUFFIXES = ("wav", "mp3", "m4a", "aac", "flac")
AUDIO_REF_RE = re.compile(
    r"(REF-[A-Z0-9-]+)（顺序：([1-9]\d*)）· "
    r"([^；\n]+?\.(?:" + "|".join(AUDIO_SUFFIXES) + r"))《([^》\n]+)》"
    r"（用途：([^；）\n]+)；角色：([^；）\n]+)；控制：([^；）]+)；不得控制：([^）]+)）",
    re.IGNORECASE,
)
AUDIO_PURPOSE = "音色"
AUDIO_SYNTAX = (
    "REF-<槽位>（顺序：<n>）· <音频路径>《<中文名>》"
    "（用途：音色；角色：<人物名>；控制：<范围>；不得控制：<范围>）"
)
# An audio file or 用途：音色 in a picture field is a voice binding written in
# the wrong place; the generic "broken REF syntax" would not say where it goes.
AUDIO_IN_IMAGE_FIELD_RE = re.compile(
    r"\.(?:" + "|".join(AUDIO_SUFFIXES) + r"|opus)《|用途：音色", re.IGNORECASE
)
# Where 《视觉设定.md》 records a character's accepted voice reference: one
# line under that 人物 entry, path first.
VOICE_RECORD_RE = re.compile(
    r"^[ \t　]*[-*+][ \t　]*声音参考[：:](.*)$", re.MULTILINE
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
_MAX_SPEAKER_LENGTH = 40
_SPEAKER_TOKEN = r"[^\s：:（）()\[\]#，。！？；,!?;—]+"
_SPEAKER_LABEL = (
    rf"(?=.{{1,{_MAX_SPEAKER_LENGTH}}}(?:[ \t]*[（(]|：|:))"
    rf"{_SPEAKER_TOKEN}(?: {_SPEAKER_TOKEN}){{0,3}}"
)
_OPTIONAL_CUE = r"(?:[ \t]*(?:（[^（）\r\n]+）|\([^()\r\n]+\)))?"
SCREENPLAY_DIALOGUE_RE = re.compile(
    rf"^(?P<speaker>{_SPEAKER_LABEL}){_OPTIONAL_CUE}：(?P<text>\S[\s\S]*)$"
)
SCREENPLAY_VOICE_TAG_RE = re.compile(
    rf"^\[(?:VO|OS)\]\s*(?P<speaker>{_SPEAKER_LABEL}){_OPTIONAL_CUE}：(?P<text>\S[\s\S]*)$"
)
# A later line of a paragraph that starts another block (the index's
# ASCII_DIALOGUE_RE, ANY_TAG_RE and MALFORMED_TAG_RE): the paragraph is missing
# a separator and the index emits no dialogue for it.
SCREENPLAY_BLOCK_START_RE = re.compile(
    rf"^{_SPEAKER_LABEL}{_OPTIONAL_CUE}:\s*\S"
    r"|^\[[^\]\r\n]+\]"
    r"|^\[(?:VO|OS|SFX|画面文字|连续性|转场)(?:\s|：|:)"
)
# Where the clause that introduces a quote begins.
CLAUSE_BREAK_RE = re.compile(r"[。！？；!?;]|(?<!\d)\.(?!\d)")
# `EP001-SC001` is the documented shape, but a project that scopes ids by season
# writes `S01-EP001-SC001`. Both are one stable scene id, so the pattern takes
# any hyphenated prefix rather than exactly one segment.
SLOT_HEAD_RE = re.compile(
    r"(?:REF|PLAN)-[A-Za-z0-9][A-Za-z0-9-]*（顺序：", re.IGNORECASE
)
SCENE_ID_PATTERN = r"(?:[A-Za-z0-9]+-)+SC[0-9]+"
SCENE_HEADING_RE = re.compile(
    r"^## (" + SCENE_ID_PATTERN + r")\b", re.MULTILINE
)
SCENE_ID_RE = re.compile(SCENE_ID_PATTERN)
# A quoted span of the source line, 「…」 or 『…』.
QUOTE_RE = re.compile(r"「[^」]*」|『[^』]*』")
# A scene the storyboard decided not to film. SHT-01 has always allowed the
# omission and always required a reason; without a place to write it the
# omission and an oversight look identical in the finished document.
UNFILMED_LINE_RE = re.compile(
    r"^[ \t\u3000]*[-*+][ \t\u3000]*未拍场次[：:](.*)$", re.MULTILINE
)
UNFILMED_ENTRY_RE = re.compile(
    r"(" + SCENE_ID_PATTERN + r")（理由：([^）\n]+)）"
)
# Dialogue reaches the model as a quoted run, either inside the H3 `<d>` tag or
# inside quotation marks. Runs shorter than four Han characters are in-frame
# labels and interjections far more often than they are lines, so the check
# stays off them rather than inventing an escape hatch for signage.
SPOKEN_SPAN_RE = re.compile(
    r"<d>([\s\S]*?)</d>|[\"“]([^\"”]*)[\"”]|「([^」]*)」|『([^』]*)』"
)
H3_INLINE_TAG_RE = re.compile(r"<(?:cutoff|scenetrans)\s*/?>", re.IGNORECASE)
SPOKEN_RUN_RE = re.compile(r"[\u3400-\u9fff]{4,}")
SPEECH_CUE_RE = re.compile(
    r"(?:"
    r"(?:说|道|喊|叫|问|答|吼|骂|念|低语|开口|追问|反问|回答|提醒|命令|大喝|喃喃|"
    r"脱口而出|出声|插嘴|接话|呵斥|怒斥|质问|嘱咐|交代|旁白|画外音|台词)"
    r"[^。！？；\n\"“「『写印刻挂显标]{0,12}[：:，,\s]*"
    r"|\b(?:says?|said|speaks?|spoke|asks?|asked|replies|replied|answers?|answered|"
    r"calls?|called|shouts?|shouted|whispers?|whispered|murmurs?|murmured|"
    r"yells?|yelled|mutters?|muttered|utters?|uttered|cries|cried|reads?|"
    r"announces?|announced|declares?|declared|voice-over|voiceover)\b"
    r"[^.!?;:\n\"“「『]{0,48}[:,\s]*"
    r")$",
    re.IGNORECASE,
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
    r"^## (" + "|".join(VISUAL_CATEGORIES) + r") · (.+?)[ \t　]*$", re.MULTILINE
)
# Any other `## <word> · <name>` heading, so an 出场设定 entry that fails to
# resolve can say "the entry is there, the section word is not one of the four"
# instead of blaming the storyboard for a `视觉设定.md` problem.
OTHER_SETTING_HEADING_RE = re.compile(r"^## ([^\n·]+?) · (.+?)[ \t　]*$", re.MULTILINE)
# 提示词名称 is the one field the coverage check depends on, so — like a
# continuity lock — anything that looks like it has to parse rather than
# silently drop out.
# Anchored at the start of the line so a sentence that merely mentions the
# field is prose, not a malformed declaration.
SCREEN_NAME_LINE_RE = re.compile(
    r"^[ \t　]*[-*+]?[ \t　]*提示词名称[ \t　]*[：:][^\n]*$", re.MULTILINE
)
SCREEN_NAME_RE = re.compile(
    r"^[ \t　]*[-*+][ \t　]*提示词名称[：:](.+)$", re.MULTILINE
)
ROLE_VOICE_LINE_RE = re.compile(
    r"^[ \t　]*[-*+]?[ \t　]*角色声线[ \t　]*[：:][^\n]*$", re.MULTILINE
)
ROLE_VOICE_RE = re.compile(
    r"^[ \t　]*[-*+][ \t　]*角色声线[：:](.+)$", re.MULTILINE
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
LOCK_LINE_RE = re.compile(r"^[ \t\u3000]*[-*+][ \t\u3000]*连戏锁[：:].*$", re.MULTILINE)
LOCK_RE = re.compile(
    r"^[ \t\u3000]*[-*+][ \t\u3000]*连戏锁[：:]\s*(LOCK-[A-Z0-9-]+)《([^》\n]+)》"
    r"（镜头：([^；）\n]+)"
    r"(?:；图片提示词项：([^；）\n]+))?）"
    r"· 锁定词：(.+)$"
)
# The surface has to name what is in the picture. A match glued to a negation
# ("no pale blue sweater") describes what must be absent, so it cannot be the
# evidence that the fact is present.
# Chinese runs without spaces, so the CJK markers cannot require a preceding
# boundary the way the English ones do. A bare 无 is deliberately not a marker:
# 无袖毛衣 describes the garment rather than excluding it.
NEGATION_RE = re.compile(
    r"(?:"
    r"(?:^|[\s,;:(\[/—-])(?:no|not|non|never|without|avoid|excludes?|excluding|"
    r"free\s+of|--?no)(?:\s+(?:a|an|the|any|some))?[\s-]*"
    r"|(?:不要|不得|不能|不应|不含|不出现|没有|未|避免|禁止|排除|去掉|移除)"
    r"(?:出现|包含|存在|带|有)?[\s]*"
    r")$",
    re.IGNORECASE,
)


def _sections(document: str, kind: str) -> dict[str, str]:
    """Each `## <kind>-...` entry, running up to the next second-level heading.

    The entry stops at *any* `## ` heading, not only the next entry of its own
    kind: a report or a delivery group written after the last shot would
    otherwise be read as that shot's fields.
    """
    headings = [match.start() for match in ANY_SECTION_RE.finditer(document)]
    sections: dict[str, str] = {}
    for match in SECTION_RE.finditer(document):
        if not match.group(1).startswith(f"{kind}-"):
            continue
        end = next((start for start in headings if start > match.start()), None)
        sections.setdefault(match.group(1), document[match.start() : end])
    return sections


def _fields(section: str, *, owner: str, errors: list[str]) -> dict[str, str]:
    pairs = re.findall(r"^- ([^：\n]+)：(.+)$", section, re.MULTILINE)
    fields: dict[str, str] = {}
    for key, value in pairs:
        # `- **参考**：…` is ordinary Markdown and reads as the same field to a
        # human. Taking the emphasis literally turned it into a different key,
        # so the author got "缺少参考字段" while looking straight at 参考.
        key = re.sub(r"^(?:\*\*|__|\*|_)(.+?)(?:\*\*|__|\*|_)$", r"\1", key.strip())
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
    return plain.startswith("无（待补参考图：") or bool(
        PENDING_REFERENCE_SUFFIX_RE.search(value.strip())
    )


def _is_no_external_reference(value: str) -> bool:
    return not _contains_slot_token(value) and bool(
        re.fullmatch(r"无(?:外部参考)?(?:；[^\n]*)?。?", value.strip())
    )


def _copyable_prompt(
    section: str, heading: str = r"可复制(?:通用)?提示词"
) -> Optional[str]:
    markers = list(re.finditer(rf"^### {heading}\s*$", section, re.MULTILINE))
    if len(markers) != 1:
        return None
    body = section[markers[0].end() :]
    following = re.search(r"^###\s+|^##\s+", body, re.MULTILINE)
    if following is not None:
        body = body[: following.start()]
    lines = [line for line in body.splitlines() if line.strip()]
    if not lines or any(not line.startswith(">") for line in lines):
        return None
    prompt = "\n".join(line[1:].lstrip() for line in lines).strip()
    return prompt or None


def _copyable_prompt_cause(
    section: str, heading: str = r"可复制(?:通用)?提示词"
) -> str:
    """Why `_copyable_prompt` returned None, as a suffix for the error.

    "缺少唯一且非空的可复制提示词" is true of four different documents and tells
    the author nothing about which one they wrote. The expensive case is a
    single stray line -- a separator, an HTML comment, a note -- inside an
    otherwise complete block: the prompt is visibly right there, so the message
    reads as a checker bug and the real line goes unlooked at.
    """

    # Name the heading the author actually has to write, not this one's default:
    # the keyframe caller passes a different one, and pointing at the wrong
    # heading is worse than saying nothing.
    label = "### " + re.sub(r"\(\?:([^)]*)\)\?", "", heading).replace("\\", "")
    markers = list(re.finditer(rf"^### {heading}\s*$", section, re.MULTILINE))
    if not markers:
        return f"：没有 `{label}` 小节标题"
    if len(markers) > 1:
        return f"：`{label}` 出现了 {len(markers)} 次，只能有一个"
    body = section[markers[0].end() :]
    following = re.search(r"^###\s+|^##\s+", body, re.MULTILINE)
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
    return resolved == root or root in resolved.parents


class EntryIndex(NamedTuple):
    """The document entries a `PLAN-...` locator is allowed to name."""

    # None when that document is not part of a partial check: its locators
    # cannot be resolved, so they are not reported as missing either.
    images: Optional[dict[str, str]]
    shots: Optional[frozenset]


def _slot_matches(value: str) -> list:
    """Every `REF-...` and `PLAN-...` slot in `value`, in written order.

    The two patterns cannot match the same span: a REF locator has to be an
    image path and a PLAN locator has to be an `IMG-`/`SHOT-` id.
    """
    found = []
    for kind, pattern in (("REF", REF_RE), ("PLAN", PLAN_RE)):
        for match in pattern.finditer(value):
            found.append((match.start(), match.end(), kind, match.groups()))
    found.sort(key=lambda item: item[0])
    return found


def _input_exempts_lock(
    value: str,
    lock: ContinuityLock,
    shot_id: str,
    shots: Optional[Mapping[str, str]],
) -> bool:
    """Whether an 输入参考图 line already carries ``lock`` visually for ``shot_id``."""
    if not value or _is_none(value):
        return False
    cleaned = PENDING_REFERENCE_SUFFIX_RE.sub("", value.strip())
    for _start, _end, kind, groups in _slot_matches(cleaned):
        locator = groups[2]
        label = groups[3]
        purpose = (groups[4] or "").strip()
        may_control = groups[5]
        if kind == "REF" and purpose == "起始帧":
            return True
        if kind == "PLAN" and purpose == "起始帧":
            if locator == shot_id:
                return True
            if shots is not None and locator in shots:
                keyframe = _copyable_prompt(shots[locator], heading=r"首帧提示词")
                if keyframe is not None and _carries_surface(keyframe, lock.surface):
                    return True
        if purpose in {"主体", "造型状态"}:
            if kind == "PLAN" and locator in lock.images:
                return True
            if lock.entry is not None:
                entry_name = lock.entry[1]
                if entry_name and (entry_name in label or entry_name in may_control):
                    return True
    return False


def _references(
    value: str,
    owner: str,
    project_root: Optional[Path],
    errors: list[str],
    entries: Optional[EntryIndex] = None,
) -> frozenset:
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


def _han_key(value: str) -> str:
    """Only the Han characters, so quoting and language tags do not decide identity."""
    return "".join(re.findall(r"[\u3400-\u9fff]+", value))


class SpokenLine(NamedTuple):
    """One dialogue paragraph of 剧本.md: its scene, speaker and Han text."""

    scene: Optional[str]
    speaker: str
    key: str


def _screenplay_dialogue(screenplay: str) -> list[SpokenLine]:
    """Every dialogue paragraph, read the way screenplay_index.py reads it.

    Mirrors `_parse_screenplay` block by block: a comment runs through the line
    that closes it, and an unclosed one ends the parse; a heading sets or clears
    the scene (scene ids use this checker's own SCENE_HEADING_RE, the one
    来源 resolves against); a paragraph runs until a blank line, a heading or a comment and
    counts only inside a scene; a later line that starts another block means a
    missing separator, so the paragraph is not dialogue. The one difference is
    the speaker list: the index takes it from the project, and here a speaker
    is only ever looked up by 人物 entry name.
    """
    found: list[SpokenLine] = []
    scene: Optional[str] = None
    lines = screenplay.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
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
            heading = SCENE_HEADING_RE.match(stripped)
            scene = heading.group(1) if heading else None
            index += 1
            continue
        end = index
        while end + 1 < len(lines):
            following = lines[end + 1].strip()
            if not following or following.startswith(("#", "<!--")):
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
        if match is not None and _han_key(match.group("text")):
            found.append(
                SpokenLine(scene, match.group("speaker"), _han_key(match.group("text")))
            )
    return found


def _normalize_spoken_span(raw_span: str, *, is_dialogue_tag: bool) -> str:
    cleaned = H3_INLINE_TAG_RE.sub("", raw_span) if is_dialogue_tag else raw_span
    cleaned = re.sub(r"(?<=[A-Za-z0-9])\n(?=[A-Za-z0-9])", " ", cleaned)
    return cleaned.replace("\n", "")


def _quote_speakers(
    prompt: Optional[str], lines: list[SpokenLine], names: dict[str, list[str]]
) -> list[tuple[str, frozenset]]:
    """Each quote in the copyable body with the speakers it can belong to.

    Dialogue reaches the body quoted and verbatim (VID-25), so the screenplay
    says whose line it is. A short quote such as 「是。」 has to match a whole
    line, or any one-character quote would count as anybody's. When two
    speakers share the line, the clause that introduces the quote decides it
    only if it names exactly one of them; otherwise the quote stays ambiguous.
    """
    if prompt is None:
        return []
    result: list[tuple[str, frozenset]] = []
    previous_end = 0
    for match in SPOKEN_SPAN_RE.finditer(prompt):
        is_dialogue_tag = match.group(1) is not None
        raw_span = next(
            (group for group in match.groups() if group is not None), ""
        )
        span = _normalize_spoken_span(raw_span, is_dialogue_tag=is_dialogue_tag)
        key = _han_key(span) if len(span) <= 200 else ""
        candidates = frozenset(
            line.speaker
            for line in lines
            if key and (key == line.key or (len(key) >= 4 and key in line.key))
        )
        if len(candidates) > 1:
            lead = prompt[previous_end : match.start()].replace("\n", " ")
            breaks = list(CLAUSE_BREAK_RE.finditer(lead))
            clause = lead[breaks[-1].end() :] if breaks else lead
            named = frozenset(
                speaker
                for speaker in candidates
                if any(name in clause for name in names.get(speaker, [speaker]))
            )
            if len(named) == 1:
                candidates = named
        if candidates:
            result.append((span, candidates))
        previous_end = match.end()
    return result


def _voice_records(visual: str, errors: list[str]) -> dict[str, str]:
    """Each 人物 entry's `- 声音参考：` value, keyed by the entry name."""
    headings = list(re.finditer(r"^## [^\n]*$", visual, re.MULTILINE))
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
    for line in ROLE_VOICE_LINE_RE.findall(visual):
        match = ROLE_VOICE_RE.match(line)
        if match is None or not _plain(match.group(1)):
            errors.append(
                "视觉设定.md: 角色声线必须写成 `- 角色声线：<声线说明>`: " + _excerpt(line)
            )
    headings = list(re.finditer(r"^## [^\n]*$", visual, re.MULTILINE))
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
    speaking = {line.speaker for line in voices.dialogue}
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

    characters: frozenset
    records: dict[str, str]
    dialogue: list[SpokenLine]
    # Every name a clause may use for a 人物 entry: its name and 提示词名称.
    names: dict[str, list[str]]
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
    prompt: Optional[str],
    voices: VoiceContext,
    scenes: Optional[list[str]],
) -> None:
    """Validate one MOTION's 参考音频 line against the character it names."""
    if _is_none(value):
        return
    # A line said in another scene is not evidence for this shot.
    # None: no storyboard says which scenes this MOTION films, so who speaks a
    # line cannot be told apart and attribution is skipped.
    in_scope = [line for line in voices.dialogue if not scenes or line.scene in scenes]
    quotes = _quote_speakers(prompt, in_scope, voices.names)
    plain = value.strip()
    matches = list(AUDIO_REF_RE.finditer(plain))
    cursor = 0
    for index, match in enumerate(matches):
        if plain[cursor : match.start()] != ("" if index == 0 else "；"):
            matches = []
            break
        cursor = match.end()
    if not matches or plain[cursor:] not in {"", "。"}:
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
        shared = [span for span, speakers in quotes if name in speakers]
        if scenes is None or not (voices.has_screenplay and voices.has_visual) or any(
            speakers == {name} for _, speakers in quotes
        ):
            pass
        elif shared:
            others = sorted(
                {s for _, speakers in quotes if name in speakers for s in speakers} - {name}
            )
            errors.append(
                f"{owner}: 引文「{_excerpt(shared[0], 24)}」在《剧本.md》里也是"
                f"{'、'.join(others)}的台词，看不出是不是人物「{name}」在说；"
                "在引文前的分句里点名说话人，或引一句只属于他的台词"
            )
        else:
            errors.append(
                f"{owner}: 人物「{name}」在本镜可复制提示词里没有说出《剧本.md》记在其名下的台词；"
                "不说话的人物不绑定参考音频"
            )
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


def _normalized(value: str) -> str:
    """Fold case and collapse whitespace so a hard-wrapped prompt still matches.

    A copyable prompt is one rendered paragraph; the line breaks the repo's
    Markdown style puts in it are not part of the text a creator wrote.
    """
    return re.sub(r"\s+", " ", value).strip().casefold()


def _wordish(character: str) -> bool:
    return bool(character) and character.isascii() and (
        character.isalnum() or character == "-"
    )


def _carries_surface(prompt: str, surface: str) -> bool:
    """Is this lock surface actually asserted by this prompt?

    Plain containment is not enough. `chipped white enamel mug` must not be
    satisfied by `unchipped ... mug`, and `no pale blue sweater` in a negative
    tail asserts the opposite of the fact the lock exists to hold.
    """
    haystack = _normalized(prompt)
    needle = _normalized(surface)
    if not needle:
        return False
    start = haystack.find(needle)
    while start != -1:
        end = start + len(needle)
        before = haystack[start - 1] if start else ""
        after = haystack[end] if end < len(haystack) else ""
        # Only ASCII words have boundaries to glue across. Chinese is written
        # without spaces, so treating an adjacent CJK character as "glued" would
        # make a Chinese surface impossible to satisfy.
        glued = (
            (_wordish(needle[:1]) and _wordish(before))
            or (_wordish(needle[-1:]) and _wordish(after))
        )
        if not glued and NEGATION_RE.search(haystack[:start]) is None:
            return True
        start = haystack.find(needle, start + 1)
    return False


class VisualEntry(NamedTuple):
    """One `视觉设定.md` entry plus every name a prompt body may call it by."""

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
    headings = list(VISUAL_SETTING_HEADING_RE.finditer(document))
    entries: list[VisualEntry] = []
    seen: set[tuple[str, str]] = set()
    for index, heading in enumerate(headings):
        end = (
            headings[index + 1].start()
            if index + 1 < len(headings)
            else len(document)
        )
        category, name = heading.group(1), heading.group(2).strip()
        if not name:
            errors.append(f"视觉设定.md: {category}条目缺少名称")
            continue
        if (category, name) in seen:
            errors.append(f"视觉设定.md: 条目重复: {category}「{name}」")
            continue
        seen.add((category, name))
        declared = SCREEN_NAME_RE.findall(document[heading.end() : end])
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
            VisualEntry(category, name, designators, bool(declared))
        )
    return entries


def _named_entries(
    prompt: str,
    entries: list[VisualEntry],
    *,
    fold_case: bool = False,
    by_entry_name: bool = False,
    include_entry_name: bool = False,
) -> set[tuple[str, str]]:
    """Which declared entries does this frozen keyframe actually call by name?

    Longer designators win: a keyframe that shows 「许棠手机」 names the prop, and
    the 人物「许棠」 substring inside it is not a second, unrelated claim.
    """
    haystack = re.sub(r"\s+", " ", prompt).strip()
    if fold_case:
        haystack = haystack.casefold()
    owners: dict[str, list[VisualEntry]] = {}
    for entry in entries:
        # 来源 quotes 剧本.md, which is written in the project's own language and
        # calls people by their entry names — not by the 提示词名称 a prompt body
        # uses. Matching a Chinese screenplay quote against an English designator
        # would never fire, so that text is matched by entry name instead. An
        # entry that opted out with `提示词名称：无` opted out of being found by
        # name at all, and stays out of both.
        if not entry.designators:
            needles: list[str] = []
        elif by_entry_name:
            needles = [entry.name]
        elif include_entry_name:
            needles = _unique([entry.name, *entry.designators])
        else:
            needles = entry.designators
        for designator in needles:
            needle = re.sub(r"\s+", " ", designator).strip()
            if fold_case:
                needle = needle.casefold()
            # A one-character designator matches far too much prose to be
            # evidence; _visual_entries already reports it.
            if len(needle) < 2:
                continue
            owners.setdefault(needle, []).append(entry)
    named: set[tuple[str, str]] = set()
    # Spans of every occurrence of a longer designator, whether or not it was
    # credited. 「戒指盒」 occupies its characters even when the sentence is
    # 「没有戒指」, so 道具「戒指」 must not be read out of it.
    taken: list[tuple[int, int]] = []
    for needle in sorted(owners, key=len, reverse=True):
        occurrences: list[tuple[int, int]] = []
        start = haystack.find(needle)
        while start != -1:
            end = start + len(needle)
            occurrences.append((start, end))
            start = haystack.find(needle, start + 1)
        for start, end in occurrences:
            before = haystack[start - 1] if start else ""
            after = haystack[end] if end < len(haystack) else ""
            glued = (
                (_wordish(needle[:1]) and _wordish(before))
                or (_wordish(needle[-1:]) and _wordish(after))
            )
            # Strictly longer, so two entries sharing one designator are both
            # credited instead of the first in document order winning.
            inside_longer = any(
                taken_start <= start
                and end <= taken_end
                and taken_end - taken_start > end - start
                for taken_start, taken_end in taken
            )
            if (
                not glued
                and not inside_longer
                and NEGATION_RE.search(haystack[:start]) is None
            ):
                named.update(entry.key for entry in owners[needle])
        taken.extend(occurrences)
    return named


class VisualBasis(NamedTuple):
    """One shot's parsed 出场设定: what it declares, and what it excludes."""

    parsed: bool
    declared: set[tuple[str, str]]
    offscreen: set[tuple[str, str]]

    @property
    def accounted(self) -> set[tuple[str, str]]:
        return self.declared | self.offscreen


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


def _check_named_coverage(
    prompt: str,
    owner: str,
    where: str,
    basis: "VisualBasis",
    entries: list[VisualEntry],
    errors: list[str],
    *,
    by_entry_name: bool = False,
    include_entry_name: bool = False,
) -> None:
    """Every entry this text calls by name is either in frame or declared 画外."""
    # Matching is case-sensitive so an ordinary English word never impersonates a
    # character called May or Will. A body that writes the name in another case
    # would otherwise fall out of the check silently, so it is reported here.
    named = _named_entries(
        prompt,
        entries,
        by_entry_name=by_entry_name,
        include_entry_name=include_entry_name,
    )
    folded = _named_entries(
        prompt,
        entries,
        fold_case=True,
        by_entry_name=by_entry_name,
        include_entry_name=include_entry_name,
    )
    for category, name in sorted(folded - named):
        errors.append(
            f"{owner}: {where}里的名字与提示词名称大小写不一致: {category}「{name}」；"
            "同一个名字全集只用一个拼写"
        )
    for category, name in sorted(named):
        if (category, name) not in basis.accounted:
            errors.append(
                f"{owner}: {where}写到{category}「{name}」，出场设定没有覆盖；"
                "本镜确实看不见时在出场设定末尾加「；画外："
                f"{category}「{name}」」，正文里这个名字不可靠时在《视觉设定.md》"
                "写「提示词名称：无」"
            )


def _visual_basis(
    value: str,
    owner: str,
    entries: list[VisualEntry],
    other_headings: dict[str, str],
    errors: list[str],
) -> VisualBasis:
    """Parse one shot's 出场设定 and resolve it against `视觉设定.md`."""
    empty = VisualBasis(True, set(), set())
    if _is_none(value):
        return empty
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
        # Coverage is not reported on top of a parse failure: every entry would
        # be listed as uncovered and bury the one error that matters.
        return VisualBasis(False, set(), set())
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
    offscreen: set[tuple[str, str]] = set()
    if offscreen_raw:
        offscreen_raw = offscreen_raw.replace(VISUAL_BASIS_PREFIX, "")
        remainder = OFFSCREEN_ENTRY_RE.sub("", offscreen_raw).strip("；、 ")
        offscreen_matches = list(OFFSCREEN_ENTRY_RE.finditer(offscreen_raw))
        if not offscreen_matches or remainder:
            errors.append(
                f"{owner}: 画外清单必须写成 `；画外：<人物|造型|地点|道具>「<名称>」`，多项用；连接"
            )
            return VisualBasis(False, set(), set())
        for match in offscreen_matches:
            key = (match.group(1), match.group(2).strip())
            if key in declared:
                errors.append(
                    f"{owner}: {key[0]}「{key[1]}」同时写进出场设定和画外清单"
                )
            offscreen.add(key)
            _resolve_entry(key, known, other_headings, owner, errors)
    return VisualBasis(True, declared, offscreen)


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
        SPOKEN_SPAN_RE.sub("", prompt)
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


def _load_manifest_dict(project_root: Optional[Path]) -> Optional[dict]:
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
    errors: list[str],
    has_image_family: bool = False,
    has_video_family: bool = False,
    image_prompts: Iterable[Optional[str]] = (),
    video_prompts: Iterable[Optional[str]] = (),
    copyable_prompts: Iterable[Optional[str]] = (),
    fallback_texts: Iterable[str] = (),
) -> None:
    """Every character must be nameable whenever any active prompt family is non-zh."""
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
    if all(lang.casefold().startswith("zh") for lang in active_languages):
        return
    for entry in entries:
        if entry.category != "人物":
            continue
        if not entry.has_screen_name and entry.designators == [entry.name]:
            errors.append(
                f"视觉设定.md: 人物「{entry.name}」缺少提示词名称；"
                "提示词正文不是中文时，写「提示词名称：<正文里的拼写>」，"
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
    motion_by_shot: dict[str, tuple[str, str, Optional[str]]],
    image_prompts: Optional[dict[str, Optional[str]]],
    errors: list[str],
    in_frame: Optional[dict[str, set[tuple[str, str]]]] = None,
    groups: Optional[
        Mapping[
            str,
            tuple[list[str], Optional[str]]
            | tuple[list[str], Optional[str], str]
            | tuple[list[str], Optional[str], bool],
        ]
    ] = None,
    motion_inputs: Optional[Mapping[str, str]] = None,
) -> None:
    """Require every declared lock surface to be present where it was scoped.

    ``shots`` or ``image_prompts`` is None when that document is not part of a
    partial check; that half of the lock is skipped.
    """
    def input_for_shot(shot_key: str) -> str:
        motion_entry = motion_by_shot.get(shot_key)
        if motion_entry is None:
            return ""
        m_id, m_body, _ = motion_entry
        if motion_inputs is not None and m_id in motion_inputs:
            return motion_inputs[m_id]
        return _fields(m_body, owner=m_id, errors=[]).get("输入参考图", "")

    for lock in locks:
        lock_id = lock.lock_id
        surface = lock.surface
        if shots is None:
            # Without 分镜.md: explicit shots and 全集 still reach the MOTION and
            # GROUP bodies through each MOTION's 分镜 field; 入画 needs the
            # storyboard's 出场设定 and waits for it.
            if lock.shots == ["全集"]:
                targets: list[str] = sorted(motion_by_shot)
            elif lock.shots == [IN_FRAME_SCOPE]:
                targets = []
            else:
                targets = lock.shots
        elif lock.shots == ["全集"]:
            targets = sorted(shots)
        elif lock.shots == [IN_FRAME_SCOPE]:
            targets = sorted(
                shot_id
                for shot_id, declared in (in_frame or {}).items()
                if lock.entry in declared
            )
        else:
            targets = lock.shots
        for shot_id in targets:
            if shots is not None:
                if shot_id not in shots:
                    errors.append(f"{lock_id}: 连戏锁指向不存在的镜头: {shot_id}")
                    continue
                keyframe = _copyable_prompt(shots[shot_id], heading=r"首帧提示词")
                if keyframe is None:
                    errors.append(f"{lock_id}: {shot_id} 缺少可读的首帧提示词")
                elif not _carries_surface(keyframe, surface):
                    errors.append(f"{lock_id}: {shot_id} 首帧提示词缺少锁定词")
            motion = motion_by_shot.get(shot_id)
            if motion is None:
                continue
            motion_id, _motion_body, copyable_prompt = motion
            motion_input = input_for_shot(shot_id)
            if _input_exempts_lock(motion_input, lock, shot_id, shots):
                continue
            if copyable_prompt is not None and not _carries_surface(
                copyable_prompt, surface
            ):
                errors.append(f"{lock_id}: {motion_id} 可复制提示词缺少锁定词")
        # A delivery group's body is what is actually submitted, so a lock that
        # covers any member shot without a matching visual reference reaches it too.
        for group_id, group_info in (groups or {}).items():
            members = group_info[0]
            group_prompt = group_info[1]
            third = group_info[2] if len(group_info) > 2 else ""
            locked_shots = set(members) & set(targets)
            if group_prompt is None or not locked_shots:
                continue
            if isinstance(third, bool):
                group_exempt = third
            elif third.strip():
                group_exempt = all(
                    _input_exempts_lock(third, lock, shot_id, shots)
                    for shot_id in locked_shots
                )
            else:
                group_exempt = all(
                    shot_id in motion_by_shot
                    and _input_exempts_lock(
                        input_for_shot(shot_id), lock, shot_id, shots
                    )
                    for shot_id in locked_shots
                )
            if group_exempt:
                continue
            if not _carries_surface(group_prompt, surface):
                errors.append(f"{lock_id}: {group_id} 可复制提示词缺少锁定词")
        for image_id in lock.images:
            if image_prompts is None:
                break
            if image_id not in image_prompts:
                errors.append(f"{lock_id}: 连戏锁指向不存在的 IMG 条目: {image_id}")
                continue
            image_prompt = image_prompts[image_id]
            if image_prompt is not None and not _carries_surface(image_prompt, surface):
                errors.append(f"{lock_id}: {image_id} 可复制提示词缺少锁定词")


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
    shot_scenes: dict[str, list],
    spoken_sources: "Optional[tuple]",
    errors: list[str],
    project_root: Optional[Path] = None,
    entries: Optional[EntryIndex] = None,
    motion_fields_by_id: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> dict[str, tuple[list[str], Optional[str], str]]:
    """Check the multi-shot delivery groups of 视频提示词.md (VID-13, VID-15)."""
    result: dict[str, tuple[list[str], Optional[str], str]] = {}
    owner_of: dict[str, str] = {}
    titled = dict(re.findall(r"^## (GROUP-[A-Z0-9-]+) · ([^\n]+)$", video, re.MULTILINE))
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
        listed = _group_members(fields.get("成员", ""))
        members = _unique(listed)
        if len(members) != len(listed):
            errors.append(f"{group_id}: 成员重复；一次合生里每个镜头只出现一次")
        prompt = _copyable_prompt(body)
        if prompt is None:
            errors.append(
                f"{group_id}: 缺少唯一且非空的可复制提示词" + _copyable_prompt_cause(body)
            )
        elif spoken_sources is not None:
            _check_spoken_lines(prompt, group_id, spoken_sources, errors)
        if not members:
            errors.append(f"{group_id}: 缺少成员字段")
            continue
        unknown = [item for item in members if item not in motions]
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
    match = re.search(r"^## SHOT-", storyboard, re.MULTILINE)
    return storyboard if match is None else storyboard[: match.start()]


def _shot_sources(
    value: str, owner: str, scenes: "Optional[frozenset]", errors: list[str]
) -> list:
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
    storyboard: str, scenes: "frozenset", errors: list[str]
) -> dict:
    """Scenes 分镜.md declares it deliberately does not film, with reasons."""
    head = _storyboard_head(storyboard)
    declared: dict = {}
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


def _spoken_key(value: str) -> str:
    """Drop punctuation and spacing so quoting choices do not decide identity."""
    return re.sub(r"[^\u3400-\u9fff0-9A-Za-z]", "", value)


def _quoted_speech(prompt: str) -> list:
    runs: list = []
    previous_end = 0
    for match in SPOKEN_SPAN_RE.finditer(prompt):
        is_dialogue_tag = match.group(1) is not None
        raw_span = next(
            (group for group in match.groups() if group is not None), ""
        )
        span = _normalize_spoken_span(raw_span, is_dialogue_tag=is_dialogue_tag)
        if len(span) > 200:
            previous_end = match.end()
            continue
        if not is_dialogue_tag:
            lead = prompt[previous_end : match.start()].replace("\n", " ")
            breaks = list(CLAUSE_BREAK_RE.finditer(lead))
            clause = lead[breaks[-1].end() :] if breaks else lead
            if SPEECH_CUE_RE.search(clause) is None:
                previous_end = match.end()
                continue
        runs.extend(SPOKEN_RUN_RE.findall(span))
        previous_end = match.end()
    return runs


def _check_spoken_lines(
    prompt: str, owner: str, sources: "tuple", errors: list[str]
) -> None:
    """Quoted Chinese in a copyable body has to come from an upstream document.

    The video stage already owes the screenplay verbatim dialogue. Checking it
    here is what stops a prompt from writing the line the shot wishes the
    character had said. 视觉设定.md and 分镜.md count as sources too: a location
    or prop entry carries the exact text on a sign, and a shot's own fields
    carry the on-screen text and sound this shot was designed around. What no
    upstream document contains is a line the prompt made up.
    """
    for run in _quoted_speech(prompt):
        key = _spoken_key(run)
        if key and not any(key in source for source in sources):
            errors.append(
                f"{owner}: 可复制提示词的引文在《剧本.md》《视觉设定.md》《分镜.md》里都找不到: "
                f"{_excerpt(run, 24)}"
            )


def missing_documents(episode: Path) -> list[str]:
    """The creator documents an episode directory does not have yet."""
    return [name for name in REQUIRED_DOCUMENTS if not (episode / name).is_file()]


def validate_episode(
    episode: Path, project_root: Optional[Path] = None, *, partial: bool = False
) -> list[str]:
    """Return all deterministic contract errors for ``episode``.

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
    return validate_documents(
        texts, (project_root or episode.parent.parent).resolve(), partial=partial
    )


def validate_documents(
    texts: "Mapping[str, Optional[str]]",
    project_root: Optional[Path],
    *,
    partial: bool = False,
) -> list[str]:
    """The same rules over document text already in hand, keyed by file name.

    A missing or None entry is a missing document. ``project_root`` None skips
    only what needs the disk: whether a REF file exists, and the project's
    prompt language.
    """
    errors: list[str] = []
    missing = [name for name in REQUIRED_DOCUMENTS if texts.get(name) is None]
    if missing and not partial:
        return [f"缺少创作文档: {', '.join(missing)}"]
    present = frozenset(REQUIRED_DOCUMENTS) - frozenset(missing)
    if not present:
        # A partial check before any document exists has nothing to fail on;
        # the CLI says so instead of reporting an error the creator cannot fix.
        return []

    def read(name: str) -> str:
        return texts.get(name) or ""

    has_screenplay = "剧本.md" in present
    has_visual = "视觉设定.md" in present
    has_images = "图片提示词.md" in present
    has_storyboard = "分镜.md" in present
    has_video = "视频提示词.md" in present
    images = read("图片提示词.md")
    storyboard = read("分镜.md")
    video = read("视频提示词.md")
    visual = read("视觉设定.md")
    screenplay = read("剧本.md")
    scene_headings = SCENE_HEADING_RE.findall(screenplay)
    scenes = frozenset(scene_headings)
    known_scenes = scenes if has_screenplay else None
    # A quote may come from any of the three; with one missing, an unmatched
    # quote is unverifiable rather than invented.
    quote_sources_complete = has_screenplay and has_visual and has_storyboard
    if has_screenplay and not scenes:
        errors.append(
            "剧本.md: 没有可解析的场景标题；场景标题写成 ## <场景 ID> 内|外 · 地点 · 时间"
        )
    if len(scene_headings) != len(scenes):
        errors.append("剧本.md: 场景 ID 重复")
    spoken_sources = (
        _spoken_key(screenplay),
        _spoken_key(visual),
        _spoken_key(storyboard),
    )
    unfilmed = (
        _unfilmed_scenes(storyboard, scenes, errors)
        if has_storyboard and has_screenplay
        else {}
    )
    claimed_scenes: set = set()
    in_frame: dict[str, set[tuple[str, str]]] = {}
    shot_scene_map: dict[str, list] = {}
    locks = _continuity_locks(visual, errors)
    visual_entries = _visual_entries(visual, errors)
    role_voices = _role_voices(visual, errors)
    voices = VoiceContext(
        characters=frozenset(
            entry.name for entry in visual_entries if entry.category == "人物"
        ),
        records=_voice_records(visual, errors),
        dialogue=_screenplay_dialogue(screenplay),
        names={
            entry.name: _unique([entry.name, *entry.designators])
            for entry in visual_entries
            if entry.category == "人物"
        },
        has_visual=has_visual,
        has_screenplay=has_screenplay,
    )
    _check_role_voices(visual_entries, role_voices, voices, errors)
    other_headings = {
        match.group(2).strip(): match.group(1).strip()
        for match in OTHER_SETTING_HEADING_RE.finditer(visual)
        if match.group(1).strip() not in VISUAL_CATEGORIES
    }
    shots = _sections(storyboard, "SHOT")
    image_pairs = re.findall(r"^## (IMG-[A-Z0-9-]+) · (.+)$", images, re.MULTILINE)
    image_headings = dict(image_pairs)
    # A planned picture names the board or keyframe that already decides what it
    # depicts, so both indexes have to exist before any declaration is read.
    entries = EntryIndex(
        images=image_headings if has_images else None,
        shots=frozenset(shots) if has_storyboard else None,
    )
    all_image_headings = re.findall(r"^## (IMG-[A-Z0-9-]+)\b", images, re.MULTILINE)
    if len(image_pairs) != len(all_image_headings) or any(
        not label.strip() for _, label in image_pairs
    ):
        errors.append("图片提示词.md: IMG 标题必须写成 ## IMG-... · <名称>")
    if len(image_pairs) != len(image_headings):
        errors.append("图片提示词.md: IMG 标题 ID 重复")
    image_matches = list(re.finditer(r"^## (IMG-[A-Z0-9-]+)\b", images, re.MULTILINE))
    image_prompts: dict[str, Optional[str]] = {}
    for index, match in enumerate(image_matches):
        body = images[
            match.start() : image_matches[index + 1].start()
            if index + 1 < len(image_matches)
            else None
        ]
        reference_value = _fields(body, owner=match.group(1), errors=errors).get(
            "参考", ""
        )
        if not reference_value:
            errors.append(f"{match.group(1)}: 缺少参考字段")
        elif _is_no_external_reference(reference_value):
            pass
        elif _contains_ref_token(reference_value):
            _references(
                reference_value, match.group(1), project_root, errors, entries
            )
        else:
            errors.append(
                f"{match.group(1)}: 参考必须声明无外部参考或使用完整 REF 语法"
            )
        image_prompt = _copyable_prompt(body)
        image_prompts[match.group(1)] = image_prompt
        if image_prompt is None:
            errors.append(
                f"{match.group(1)}: 缺少唯一且非空的可复制提示词"
                + _copyable_prompt_cause(body)
            )

    motions = _sections(video, "MOTION")
    shot_ids = re.findall(r"^## (SHOT-[A-Z0-9-]+)\b", storyboard, re.MULTILINE)
    motion_ids = re.findall(r"^## (MOTION-[A-Z0-9-]+)\b", video, re.MULTILINE)
    if len(shot_ids) != len(set(shot_ids)):
        errors.append("分镜.md: SHOT 标题 ID 重复")
    if len(motion_ids) != len(set(motion_ids)):
        errors.append("视频提示词.md: MOTION 标题 ID 重复")
    group_ids = re.findall(r"^## (GROUP-[A-Z0-9-]+)\b", video, re.MULTILINE)
    if len(group_ids) != len(set(group_ids)):
        errors.append("视频提示词.md: GROUP 标题 ID 重复")
    named_shots = re.findall(
        r"^## (SHOT-[A-Z0-9-]+) · ([^\n]+)$", storyboard, re.MULTILINE
    )
    named_motions = re.findall(
        r"^## (MOTION-[A-Z0-9-]+) · ([^\n]+)$", video, re.MULTILINE
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
        copyable_prompt: Optional[str],
        upstream_input: str,
        scenes: Optional[list],
    ) -> tuple[dict[str, str], str]:
        """MOTION rules evaluated against the MOTION's own输入参考图."""
        motion_fields = motion_fields_by_id.get(motion_id)
        if motion_fields is None:
            motion_fields = _fields(motion_body, owner=motion_id, errors=errors)
        if copyable_prompt is not None and quote_sources_complete:
            _check_spoken_lines(
                copyable_prompt, motion_id, spoken_sources, errors
            )
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
                prompt=copyable_prompt,
                voices=voices,
                scenes=scenes,
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
        return motion_fields, anchor

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
            basis = VisualBasis(False, set(), set())
        elif not has_visual:
            basis = VisualBasis(False, set(), set())
        else:
            basis = _visual_basis(
                basis_value, shot_id, visual_entries, other_headings, errors
            )
        if basis.parsed:
            in_frame[shot_id] = basis.declared
        keyframe = _copyable_prompt(shot_body, heading=r"首帧提示词")
        collected_keyframes.append(keyframe)
        if keyframe is None:
            errors.append(
                f"{shot_id}: 缺少唯一且非空的首帧提示词"
                + _copyable_prompt_cause(shot_body, heading=r"首帧提示词")
            )
        elif basis.parsed:
            _check_named_coverage(
                keyframe, shot_id, "首帧提示词", basis, visual_entries, errors
            )
        if re.search(r"^### 尾帧提示词\s*$", shot_body, re.MULTILINE):
            closing = _copyable_prompt(shot_body, heading=r"尾帧提示词")
            collected_keyframes.append(closing)
            if closing is None:
                errors.append(
                    f"{shot_id}: 尾帧提示词不是唯一且非空的可复制正文"
                    + _copyable_prompt_cause(shot_body, heading=r"尾帧提示词")
                )
            elif basis.parsed:
                _check_named_coverage(
                    closing, shot_id, "尾帧提示词", basis, visual_entries, errors
                )

        motion = motion_by_shot.get(shot_id)
        if not motion:
            continue
        motion_id, motion_body, copyable_prompt = motion
        motion_fields, anchor = check_motion(
            motion_id, motion_body, copyable_prompt, shot_input, shot_scenes
        )
        motion_input = motion_fields.get("输入参考图", "")
        if not _is_none(motion_input or shot_input):
            continue
        if anchor and anchor != "无" and basis.parsed:
            _check_named_coverage(
                anchor,
                motion_id,
                "开场画面",
                basis,
                visual_entries,
                errors,
                include_entry_name=True,
            )

    if not has_storyboard:
        for motion_id, motion_body in motions.items():
            own_input = motion_fields_by_id[motion_id].get("输入参考图", "")
            check_motion(motion_id, motion_body, _copyable_prompt(motion_body), own_input, None)

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
        spoken_sources=spoken_sources if quote_sources_complete else None,
        errors=errors,
        project_root=project_root,
        entries=entries,
        motion_fields_by_id=motion_fields_by_id,
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
        errors=errors,
        has_image_family=has_images or has_storyboard,
        has_video_family=has_video,
        image_prompts=image_family_prompts,
        video_prompts=video_family_prompts,
        fallback_texts=(visual if has_visual else "", screenplay if has_screenplay else ""),
    )
    _check_continuity_locks(
        locks,
        shots=shots if has_storyboard else None,
        motion_by_shot=motion_by_shot,
        image_prompts=image_prompts if has_images else None,
        errors=errors,
        in_frame=in_frame,
        groups=group_members,
        motion_inputs={
            m_id: mf.get("输入参考图", "")
            for m_id, mf in motion_fields_by_id.items()
        },
    )
    return errors


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
    errors = validate_episode(args.episode, args.project_root, partial=args.partial)
    if errors:
        for error in errors:
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
