#!/usr/bin/env python3
"""Read an episode's creator documents into the structures the dashboard shows.

The dashboard never parses Markdown in the browser. Everything here reads the
same documents the checker reads, with the checker's own patterns wherever one
exists, so the dashboard and ``creator_markdown_check.py`` cannot disagree
about what a shot, a reference slot or a continuity lock is.

Two documents belong to other stages: the screenplay grammar is owned by the
write stage's index builder and the cut list by the edit tool. Skills install
one at a time, so this module does not import them; it keeps a minimal reader
of each and ``tests/test_dashboard_server.py`` holds both to the canonical
parser on the same inputs.

Every reader is tolerant: a section it cannot read comes back as ``None`` with
one sentence the creator can act on, and the view falls back to the raw text.
Nothing here reads files; the server hands in text it read safely.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Optional


MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "short-drama needs Python {}.{} or newer; this interpreter is {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )


def _load_checker() -> ModuleType:
    path = Path(__file__).resolve().with_name("creator_markdown_check.py")
    spec = importlib.util.spec_from_file_location("creator_views_checker", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load the creator document checker: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load_checker()

SCREENPLAY = "剧本.md"
SETTINGS = "视觉设定.md"
STORYBOARD = "分镜.md"
IMAGE_PROMPTS = "图片提示词.md"
VIDEO_PROMPTS = "视频提示词.md"
CUT_LIST = "剪辑单.md"
CREATOR_DOCUMENTS = (SCREENPLAY, SETTINGS, STORYBOARD, IMAGE_PROMPTS, VIDEO_PROMPTS)
# Where the edit stage writes the finished film, relative to the episode.
FILM = "制作成果/成片/成片.mp4"

# ------------------------------------------------------------------ shot size

# The rhythm profile's close_shot_share_min counts exactly these (develop's
# episode-design reference): 近景、特写、大特写与细节镜头. 中近景 is not one.
CLOSE_SCALES = frozenset({"近景", "特写", "大特写", "细节"})
_SCALE_RE = re.compile("大特写|中近景|远景|全景|中景|近景|特写|细节")


def shot_scale(framing: str) -> str:
    """The first shot-size word in a 景别/机位 value, or "" when none is named.

    Longer words are tried first at each position, so 中近景 and 大特写 are read
    whole instead of as the 近景 or 特写 inside them.
    """

    match = _SCALE_RE.search(framing or "")
    return match.group(0) if match else ""


# ------------------------------------------------------------------ screenplay

# The write stage's grammar (screenplay_index.py): one scene heading per scene,
# one paragraph per block, production tags in half-width brackets.
_EPISODE = r"EP(?:[0-9]{3}|[1-9][0-9]{3,})"
# The same spelling project_tool.py's EPISODE_ID_RE enforces on 剧集/<EP>/.
EPISODE_ID_RE = re.compile(_EPISODE)
TITLE_RE = re.compile(r"^#[ \t\u3000]+(?:" + _EPISODE + r")?[ \t\u3000]*(?:·[ \t\u3000]*)?(.*?)\r?$")
# Same heading grammar as the writing stage's index, season prefix included
# (`S01-EP001-SC001`), so a screenplay the index accepts never drops scenes here.
SCENE_RE = check.FULL_SCENE_HEADING_RE
TAG_RE = re.compile(r"^\[(?P<tag>VO|OS|SFX|画面文字|连续性|转场)\][ \t\u3000]*(?P<body>\S[\s\S]*)$")
_MAX_SPEAKER_LENGTH = 40
_SPEAKER_TOKEN = r"[^\s：:（）()\[\]#，。！？；,!?;—]+"
_SPEAKER_LABEL = (
    rf"(?=.{{1,{_MAX_SPEAKER_LENGTH}}}(?:[ \t\u3000]*[（(]|[：:]))"
    rf"{_SPEAKER_TOKEN}(?: {_SPEAKER_TOKEN}){{0,3}}"
)
_OPTIONAL_CUE = (
    r"(?:[ \t\u3000]*(?:（(?P<cue_fw>[^（）\r\n]+)）|\((?P<cue_hw>[^()\r\n]+)\)))?"
)
_NOT_CLOCK_PREFIX = r"(?!\d{1,2}[:：]\d{2}(?:\D|$))"
DIALOGUE_RE = re.compile(
    rf"^{_NOT_CLOCK_PREFIX}(?P<speaker>{_SPEAKER_LABEL}){_OPTIONAL_CUE}[：:][ \t\u3000]*(?P<text>\S[\s\S]*)$"
)
VOICED_TAGS = frozenset({"VO", "OS"})


def _normalize_text(text: str) -> str:
    return str(check._normalize_text(text))


def _slice_until_h2(text: str, start: int) -> str:
    next_h2 = check.ANY_SECTION_RE.search(text, start)
    return text[start : next_h2.start() if next_h2 else len(text)]


def _speaker_cue(match: re.Match[str]) -> str:
    return match.group("cue_fw") or match.group("cue_hw") or ""


def spoken_characters(line: str) -> int:
    """What is voiced: no whitespace, no bracketed direction (duration_estimate.py)."""

    stripped = re.sub(r"（[^）]*）|\([^)]*\)", "", line)
    return len(re.sub(r"\s", "", stripped))


def _paragraphs(text: str) -> list[str]:
    """Blank-line separated blocks, headings and cast lines on their own, comments dropped."""

    text = check._strip_html_comments(_normalize_text(text))
    blocks: list[str] = []
    current: list[str] = []
    seen_first_scene = False
    at_scene_head = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        if line.startswith("#"):
            if current:
                blocks.append("\n".join(current))
                current = []
            blocks.append(line)
            if re.match(r"^##(?![#])", line):
                seen_first_scene = True
                at_scene_head = True
            elif seen_first_scene:
                at_scene_head = False
            continue
        if (not seen_first_scene or at_scene_head) and check.CAST_LINE_RE.match(raw):
            if current:
                blocks.append("\n".join(current))
                current = []
            blocks.append(line)
            continue
        if seen_first_scene:
            at_scene_head = False
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def parse_screenplay(text: str) -> dict[str, Any]:
    """Scenes with their action, dialogue and production-tag blocks, in order."""

    text = _normalize_text(text)
    title = ""
    scenes: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    at_scene_head = False
    for paragraph in _paragraphs(text):
        if paragraph.startswith("##") and not paragraph.startswith("###"):
            match = SCENE_RE.fullmatch(paragraph)
            location = match.group("location").strip() if match else ""
            time_of_day = match.group("time").strip() if match else ""
            if not match or not location or not time_of_day:
                raise ValueError(
                    f"场次标题格式不对（应为 `## EP001-SC001 内|外|内外 · 地点 · 时间`）：{paragraph}"
                )
            current = {
                "id": match.group("scene"),
                "space": match.group("space"),
                "place": location,
                "time": time_of_day,
                "blocks": [],
            }
            scenes.append(current)
            at_scene_head = True
            continue
        if re.match(r"^#[ \t\u3000]+", paragraph):
            found = TITLE_RE.match(paragraph)
            title = (found.group(1) if found else re.sub(r"^#[ \t\u3000]+", "", paragraph)).strip()
            continue
        if paragraph.startswith("#") or current is None:
            at_scene_head = False
            continue
        if at_scene_head and check.CAST_LINE_RE.match(paragraph):
            continue
        at_scene_head = False
        tag = TAG_RE.fullmatch(paragraph)
        if tag:
            body = tag.group("body").strip()
            voice = DIALOGUE_RE.fullmatch(body) if tag.group("tag") in VOICED_TAGS else None
            if voice:
                current["blocks"].append({
                    "k": "line", "tag": tag.group("tag"), "who": voice.group("speaker"),
                    "paren": _speaker_cue(voice), "text": voice.group("text").strip(),
                })
            else:
                current["blocks"].append({"k": "tag", "tag": tag.group("tag"), "text": body})
            continue
        dialogue = DIALOGUE_RE.fullmatch(paragraph)
        if dialogue:
            current["blocks"].append({
                "k": "line", "tag": "", "who": dialogue.group("speaker"),
                "paren": _speaker_cue(dialogue), "text": dialogue.group("text").strip(),
            })
            continue
        current["blocks"].append({"k": "action", "text": paragraph})
    if not scenes:
        raise ValueError("没有找到 `## EP001-SC001 内 · 地点 · 时间` 这样的场次标题")
    return {"title": title, "scenes": scenes}


def voice_share(script: dict[str, Any]) -> dict[str, int]:
    """Spoken characters overall and in [VO]; [OS] is dialogue, not voice-over."""

    spoken = voiced = 0
    for scene in script["scenes"]:
        for block in scene["blocks"]:
            if block["k"] != "line":
                continue
            count = spoken_characters(block["text"])
            spoken += count
            if block["tag"] == "VO":
                voiced += count
    return {"spoken": spoken, "vo": voiced}


# ------------------------------------------------------------------ visual settings

_FIELD_KEY_HEAD = (
    rf"(?:"
    rf"\*\*\*{_NOT_CLOCK_PREFIX}{check._STAR_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*\*\*\*"
    rf"|___{_NOT_CLOCK_PREFIX}{check._UNDER_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*___"
    rf"|\*\*{_NOT_CLOCK_PREFIX}{check._STAR_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*\*\*"
    rf"|__{_NOT_CLOCK_PREFIX}{check._UNDER_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*__"
    rf"|\*{_NOT_CLOCK_PREFIX}{check._STAR_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*\*"
    rf"|_{_NOT_CLOCK_PREFIX}{check._UNDER_KEY_CHARS}[ \t\u3000]*[：:][ \t\u3000]*_"
    rf"|{check._NOT_EMPH_CLOCK_PREFIX}{check._PLAIN_KEY_CHARS}[ \t\u3000]*[：:]"
    rf")"
)
FIELD_RE = check.FIELD_LINE_RE
EMPTY_FIELD_STUB_RE = re.compile(
    r"^[ \t\u3000]*[-*+][ \t\u3000]+[^：:\r\n]{1,32}[：:][ \t\u3000]*$"
)
LOOSE_BULLET_RE = re.compile(r"^[ \t\u3000]*[-*+][ \t\u3000]+(.+)$")
LOCK_HEAD_RE = re.compile(
    rf"^[ \t\u3000]*[-*+][ \t\u3000]+{check._emph_field_head('连戏锁')}[ \t\u3000]*"
    r"(LOCK-[A-Z0-9-]+)《([^》\n]+)》",
    re.MULTILINE,
)
OVERLAY_ONLY_RE = re.compile(r"只在后期叠加")


def _strip_emphasis(key: str) -> str:
    return str(check._strip_key_emphasis(key))


def parse_settings(text: str) -> dict[str, Any]:
    text = check._strip_html_comments(_normalize_text(text))
    errors: list[str] = []
    entries = {(entry.category, entry.name): entry for entry in check._visual_entries(text, errors)}
    locks = {lock.lock_id: lock for lock in check._continuity_locks(text, errors)}
    heads = list(check.VISUAL_SETTING_HEADING_RE.finditer(text))
    preamble = _slice_until_h2(text, 0)
    meta = {_strip_emphasis(key): value.strip() for key, value in FIELD_RE.findall(preamble)}
    era_parts = [part.strip() for part in meta.get("时代背景", "").split("；") if part.strip()]
    facets: list[dict[str, str]] = []
    for part in era_parts[1:]:
        key, sep, value = part.partition("：")
        if not sep:
            key, _, value = part.partition(":")
        facets.append({"k": _strip_emphasis(key), "v": value.strip().rstrip("。")})
    era = {"period": era_parts[0] if era_parts else "", "facets": facets}
    items = []
    for head in heads:
        body = _slice_until_h2(text, head.end())
        category, name = head.group(1), head.group(2).strip()
        entry = entries.get((category, name))
        fields = {_strip_emphasis(key): value.strip() for key, value in FIELD_RE.findall(body)}
        loose: list[str] = []
        for line in body.splitlines():
            bullet = LOOSE_BULLET_RE.match(line)
            if (
                bullet
                and not FIELD_RE.match(line)
                and not EMPTY_FIELD_STUB_RE.match(line)
                and not check.LOCK_LINE_RE.match(line)
                and not check.SCREEN_NAME_LINE_RE.match(line)
                and not check.ROLE_VOICE_LINE_RE.match(line)
            ):
                loose.append(bullet.group(1).strip())
        entry_locks: list[dict[str, Any]] = []
        for named in LOCK_HEAD_RE.finditer(body):
            if named.group(1) in locks:
                found = locks[named.group(1)]
                entry_locks.append({
                    "id": found.lock_id,
                    "name": named.group(2),
                    "surface": found.surface,
                    "shots": list(found.shots),
                    "images": list(found.images),
                })
        lock = entry_locks[0] if entry_locks else None
        designators = list(entry.designators) if entry else []
        items.append({
            "cat": category,
            "name": name,
            "designators": [item for item in designators if item != name],
            "desc": loose,
            "fields": {k: v for k, v in fields.items() if k not in ("连戏锁", "提示词名称")},
            "lock": lock,
            "locks": entry_locks,
            "overlay": bool(OVERLAY_ONLY_RE.search(body)),
        })
    if not items:
        raise ValueError("没有找到 `## 人物 · 名称` 这样的设定条目")
    return {"form": meta.get("制作形态", "").rstrip("。"), "era": era, "items": items}


parse_visual_settings = parse_settings


# ------------------------------------------------------------------ storyboard

SHOT_TITLE_RE = re.compile(r"^##[ \t\u3000]+\S+[ \t\u3000]*·[ \t\u3000]*([^\r\n]+)\r?$", re.MULTILINE)
NOTE_RE = re.compile(r"^> ([^\r\n]+)\r?$", re.MULTILINE)
BLOCKING_HEADING_RE = re.compile(
    r"^场景站位[ \t\u3000]*·[ \t\u3000]*(\S+?)(?:[ \t\u3000]*·[ \t\u3000]*(.+))?$"
)
BULLET_FIELD_RE = FIELD_RE
REF_STATES = {
    "t2v": "文生视频（不用参考图）",
    "pending": "待补参考图",
    "bound": "已写参考图",
    "none": "未写参考图",
}


def _number(identifier: str) -> str:
    found = re.search(r"(\d+)$", identifier)
    return found.group(1) if found else identifier


def _slots(value: str) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for match in check.REF_RE.finditer(value):
        slots.append({
            "kind": "REF", "id": match.group(1), "order": int(match.group(2)),
            "path": match.group(3), "name": match.group(4), "use": (match.group(5) or "").strip(),
        })
    for match in check.PLAN_RE.finditer(value):
        slots.append({
            "kind": "PLAN", "id": match.group(1), "order": int(match.group(2)),
            "target": match.group(3), "name": match.group(4), "use": (match.group(5) or "").strip(),
        })
    return sorted(slots, key=lambda slot: slot["order"])


def _ref_state(value: str, slots: list[dict[str, Any]]) -> str:
    if check._has_pending_references(value):
        return "pending"
    if check._is_explicit_text_to_video(value) or check._is_none(value):
        return "t2v"
    return "bound" if slots else "none"


def parse_storyboard(text: str) -> dict[str, Any]:
    text = check._strip_html_comments(_normalize_text(text), preserve_copyable=True)
    head = _slice_until_h2(text, 0)
    note = NOTE_RE.search(head)
    shots = []
    for shot_id, section in check._sections(text, "SHOT").items():
        fields = check._fields(section, owner=shot_id, errors=[])
        title = SHOT_TITLE_RE.search(section)
        framing = fields.get("景别/机位", "")
        move = fields.get("运镜", "")
        scale = shot_scale(framing)
        reference = fields.get("输入参考图", "")
        slots = _slots(reference)
        scene = check.SCENE_ID_RE.search(fields.get("来源", ""))
        basis_text = fields.get("出场设定", "").split(check.OFFSCREEN_PREFIX)[0]
        seconds = check._declared_seconds(fields.get("时长", ""))
        shots.append({
            "id": shot_id,
            "n": _number(shot_id),
            "title": title.group(1).strip() if title else "",
            "scene": scene.group(0) if scene else "",
            "sec": seconds if seconds is not None else 0,
            "secDeclared": seconds is not None,
            "purpose": fields.get("目的", ""),
            "framing": framing,
            "scale": scale,
            "close": scale in CLOSE_SCALES,
            "move": move,
            "moveKind": re.split(r"[；;，,]", move)[0].strip(),
            "start": fields.get("起点", ""),
            "action": fields.get("动作", ""),
            "end": fields.get("终点", ""),
            "sound": fields.get("声音", ""),
            "screenText": fields.get("画面文字", ""),
            "imgs": [
                {"id": ident, "name": name, "ctl": control}
                for ident, name, control in check.IMG_RE.findall(fields.get("图片提示词项", ""))
            ],
            "refs": slots,
            "refState": _ref_state(reference, slots),
            "refLabel": REF_STATES[_ref_state(reference, slots)],
            "basis": [
                {"cat": category, "name": name, "ctl": control}
                for category, name, control in check.VISUAL_BASIS_ENTRY_RE.findall(basis_text)
            ],
            "keyframe": check._copyable_prompt(section, "首帧提示词") or "",
            "closing_keyframe": check._copyable_prompt(section, "尾帧提示词") or "",
        })
    if not shots:
        raise ValueError("没有找到 `## SHOT-EP001-001 · 标题` 这样的镜头")
    return {
        "note": note.group(1).strip() if note else "",
        "blocking": parse_scene_blocking(text),
        "shots": shots,
    }


def parse_scene_blocking(text: str) -> list[dict[str, Any]]:
    """`## 场景站位 · <scene> · <place>` blocks: the staging every shot of a scene inherits."""

    text = check._strip_html_comments(_normalize_text(text), preserve_copyable=True)
    blocks = []
    for section in re.split(r"(?m)^##[ \t\u3000]+", text)[1:]:
        heading, _, body = section.partition("\n")
        match = BLOCKING_HEADING_RE.fullmatch(heading.strip())
        if not match:
            continue
        blocks.append({
            "scene": match.group(1),
            "place": (match.group(2) or "").strip(),
            "rows": [
                [_strip_emphasis(key), value.strip()]
                for key, value in BULLET_FIELD_RE.findall(body)
            ],
        })
    return blocks


def start_frame(shot: dict[str, Any]) -> Optional[str]:
    """The one picture a shot binds as its first frame, if any."""

    for slot in shot["refs"]:
        if slot["kind"] == "REF" and slot["use"] == "起始帧":
            return str(slot["path"])
    return None


# ------------------------------------------------------------------ prompts

IMG_HEADING_RE = re.compile(r"^##[ \t\u3000]+(IMG-[A-Z0-9-]+) · ([^\r\n]+)\r?$", re.MULTILINE)


def parse_image_prompts(text: str) -> list[dict[str, Any]]:
    text = check._strip_html_comments(_normalize_text(text), preserve_copyable=True)
    parts = list(IMG_HEADING_RE.finditer(text))
    prompts = []
    for match in parts:
        section = match.group(0) + _slice_until_h2(text, match.end())
        fields = check._fields(section, owner=match.group(1), errors=[])
        prompts.append({
            "id": match.group(1), "title": match.group(2).strip(),
            "use": fields.get("用途", ""), "ref": fields.get("参考", ""),
            "prompt": check._copyable_prompt(section) or "",
        })
    if not prompts:
        if re.search(r"^#{2,4}[ \t\u3000]*IMG(?:-|\b)", text, re.MULTILINE):
            raise ValueError("没有找到 `## IMG-… · 标题` 这样的图片提示词条目")
        return []
    return prompts


def parse_video_prompts(text: str) -> list[dict[str, Any]]:
    text = check._strip_html_comments(_normalize_text(text), preserve_copyable=True)
    prompts = []
    for motion_id, section in check._sections(text, "MOTION").items():
        fields = check._fields(section, owner=motion_id, errors=[])
        title = SHOT_TITLE_RE.search(section)
        shot = re.search(r"SHOT-[A-Z0-9-]+", fields.get("分镜", ""))
        prompts.append({
            "id": motion_id,
            "n": _number(motion_id),
            "title": title.group(1).strip() if title else "",
            "shot": shot.group(0) if shot else "",
            "sec": check._declared_seconds(fields.get("时长", "")) or 0,
            "mode": fields.get("生成方式", ""),
            "chain": fields.get("动作过程", ""),
            "prompt": check._copyable_prompt(section) or "",
        })
    if not prompts:
        raise ValueError("没有找到 `## MOTION-… · 标题` 这样的视频提示词条目")
    return prompts


def parse_video_groups(text: str) -> list[dict[str, Any]]:
    """`GROUP-...` delivery groups: one submitted body standing for several MOTIONs."""

    text = check._strip_html_comments(_normalize_text(text), preserve_copyable=True)
    groups = []
    for group_id, section in check._sections(text, "GROUP").items():
        fields = check._fields(section, owner=group_id, errors=[])
        title = SHOT_TITLE_RE.search(section)
        groups.append({
            "id": group_id,
            "n": _number(group_id),
            "title": title.group(1).strip() if title else "",
            "members": check._group_members(fields.get("成员", "")),
            "sec": check._declared_seconds(fields.get("时长", "")) or 0,
            "prompt": check._copyable_prompt(section) or "",
        })
    return groups


def parse_music_prompts(text: str) -> list[dict[str, Any]]:
    """`MUSIC-...` music / BGM prompt entries in 视频提示词.md, if any."""

    text = check._strip_html_comments(_normalize_text(text), preserve_copyable=True)
    entries = []
    for music_id, section in check._sections(text, "MUSIC").items():
        fields = check._fields(section, owner=music_id, errors=[])
        title = SHOT_TITLE_RE.search(section)
        entries.append({
            "id": music_id,
            "n": _number(music_id),
            "title": title.group(1).strip() if title else "",
            "use": fields.get("用途", "") or fields.get("剧情作用", ""),
            "range": fields.get("区间", "") or fields.get("铺乐区间", ""),
            "mood": fields.get("情绪", "") or fields.get("情绪起伏", ""),
            "sec": check._declared_seconds(fields.get("时长", "")) or 0,
            "prompt": check._copyable_prompt(section) or "",
        })
    return entries


def usable_groups(
    text: Optional[str], problems: list[str], documents: Optional[dict[str, Optional[str]]] = None
) -> list[dict[str, Any]]:
    """The groups the copy queue may fold their members into.

    The checker runs over the documents in hand; a group stands in for its
    members only when it reports nothing about the group, its member MOTIONs or
    their shots. Anything else keeps the members as separate cards with a
    notice, so a malformed group never hides, reorders or misstates a prompt.
    """
    if not text:
        return []
    text = _normalize_text(text)
    clean_text = check._strip_html_comments(text, preserve_copyable=True)
    normalized_docs = {
        name: _normalize_text(val) if val is not None else None
        for name, val in (documents or {}).items()
    }
    documents = {**normalized_docs, VIDEO_PROMPTS: text}
    findings = check.validate_documents(
        {name: documents.get(name) for name in check.REQUIRED_DOCUMENTS}, None, partial=True
    )
    motions = check._sections(clean_text, "MOTION")
    shot_of = {
        motion_id: check._plain(check._fields(body, owner=motion_id, errors=[]).get("分镜", ""))
        for motion_id, body in motions.items()
    }
    # Findings about the documents as a whole (unpaired shots, repeated
    # headings) name no entry, yet they can be about any group's members.
    whole = [
        finding
        for finding in findings
        if finding.startswith(("分镜.md", "视频提示词.md"))
        and not re.search(r"\b(?:SHOT|MOTION|GROUP)-[A-Z0-9-]+", finding)
    ]
    board = documents.get(STORYBOARD)
    shots = (
        set(check._sections(check._strip_html_comments(board, preserve_copyable=True), "SHOT"))
        if board
        else None
    )
    ids = re.findall(r"^##[ \t\u3000]+(GROUP-[A-Z0-9-]+)\b", clean_text, re.MULTILINE)
    usable = []
    for group in parse_video_groups(clean_text):
        if whole:
            problems.append(f"{VIDEO_PROMPTS}：{group['id']} 未并入复制队列（{whole[0]}），按逐镜显示")
            continue
        # The copy queue follows the MOTION order of this document; a group can
        # take its members' place only if they sit there consecutively, in order,
        # whether or not a storyboard is around to say the same.
        order = list(motions)
        places = [order.index(m) for m in group["members"] if m in order]
        if places and len(places) == len(group["members"]) and places != list(
            range(places[0], places[0] + len(places))
        ):
            problems.append(
                f"{VIDEO_PROMPTS}：{group['id']} 的成员在视频提示词里不相邻或顺序不对，按逐镜显示"
            )
            continue
        unshot = [m for m in group["members"] if shots is not None and shot_of.get(m) not in shots]
        if unshot:
            problems.append(
                f"{VIDEO_PROMPTS}：{group['id']} 的成员 {'、'.join(unshot)} 在分镜里没有对应镜头，按逐镜显示"
            )
            continue
        if ids.count(group["id"]) > 1:
            problems.append(f"{VIDEO_PROMPTS}：{group['id']} 标题重复，按逐镜显示")
            continue
        names = {group["id"], *group["members"], *(shot_of.get(m, "") for m in group["members"])} - {""}
        about = [
            finding
            for finding in findings
            if any(re.search(rf"(?<![A-Z0-9-]){re.escape(name)}(?![A-Z0-9-])", finding) for name in names)
        ]
        if about or not group["members"]:
            detail = about[0] if about else "没有成员"
            problems.append(f"{VIDEO_PROMPTS}：{group['id']} 未并入复制队列（{detail}），按逐镜显示")
            continue
        usable.append(group)
    return usable


# ------------------------------------------------------------------ cut list

# The edit stage's grammar (short-drama-edit/scripts/edit_tool.py). Only reading:
# the edit tool is the one that refuses a malformed cut list.
CUT_HEADING_RE = re.compile(r"^##[ \t\u3000]+(CUT-[^\s·]+)[ \t\u3000]*(?:·[ \t\u3000]*(.*))?\r?$")
CUT_FIELD_RE = re.compile(
    rf"^[ \t\u3000]*[-*+][ \t\u3000]*({_FIELD_KEY_HEAD})[ \t\u3000]*(.*)$"
)
PICTURE_KEYS = {"亮度": "brightness", "饱和": "saturation", "色温": "warmth"}
PICTURE_TERM_RE = re.compile(r"(亮度|饱和|色温)\s*([+-]?[0-9]*\.?[0-9]+)")
SOURCE_RE = re.compile(r"^((?:GROUP|MOTION|SHOT|IMG)-\S+)\s*·\s*(.+?)\s*$")
MOVE_RE = re.compile(r"^(推近|拉远|左移|右移|上移|下移)\s*([0-9]+)\s*[%％]$")
MOVE_RATE_RE = re.compile(r"^(推近|拉远|左移|右移|上移|下移)\s*([0-9]+(?:\.[0-9]+)?)\s*[%％]\s*[/／]\s*秒$")
BED_RE = re.compile(r"^\s*(?:(-?[0-9]+(?:\.[0-9]+)?)\s+)?(.+?)\s*$")
VOICE_RE = re.compile(r"^\s*(-?[0-9]+(?:\.[0-9]+)?)\s+(.+?)\s*$")
WINDOW_RE = re.compile(r"^\s*([0-9.]+)\s*[-–~]\s*([0-9.]+)\s*$")
CUE_RE = re.compile(r"^\s*([0-9.]+)\s*[-–~]\s*([0-9.]+)\s+(.+?)\s*$")
KEYWORDS_RE = re.compile(r"[（(]重点[：:]\s*(.+?)\s*[）)]\s*$")
SCREEN_TEXT_STYLES = ("卡片", "系统面板", "任务面板", "角标", "字卡")
SCREEN_TEXT_RE = re.compile(
    r"^\s*([0-9.]+)\s*[-–~]\s*([0-9.]+)\s+(" + "|".join(SCREEN_TEXT_STYLES) + r")\s+(.+?)\s*$"
)
COUNTDOWN_RE = re.compile(r"[（(]倒计时[：:]\s*([0-9]+(?:\.[0-9]+)?|接续)\s*[）)]\s*$")
RARITY_RE = re.compile(r"[（(](传说|史诗|稀有)[）)]$")
OPTIONS_RE = re.compile(
    r"[（(]\s*((?:(?:起点|增益)[：:]|叠音(?=\s*(?:[；;）)]|$)))[^（）()]*)[）)]\s*$"
)
OPTION_RE = re.compile(r"^(起点|增益)[：:]\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*(?:dB)?$", re.I)
NUMBERED_RE = {
    "字幕": re.compile(r"^字幕(?:\s*(\d+))?$"),
    "画面文字": re.compile(r"^画面文字(?:\s*(\d+))?$"),
    "音效": re.compile(r"^音效(?:\s*(\d+))?$"),
    "配音": re.compile(r"^配音(?:\s*(\d+))?$"),
}


def _delivery(lines: list[str]) -> dict[str, Any]:
    delivery: dict[str, Any] = {
        "target": None,
        "lufs": None,
        "burn": True,
        "frame": None,
        "fps": None,
        "grain": None,
        "shot_match": False,
    }
    for raw in lines:
        match = CUT_FIELD_RE.match(raw)
        if not match:
            continue
        name, value = _strip_emphasis(match.group(1)), match.group(2).strip()
        if name == "成片目标时长":
            found = re.search(r"[0-9]+(?:\.[0-9]+)?", value)
            delivery["target"] = float(found.group(0)) if found else None
        elif name == "交付响度":
            found = re.search(r"-?[0-9]+(?:\.[0-9]+)?", value)
            delivery["lufs"] = float(found.group(0)) if found else None
        elif name == "字幕":
            delivery["burn"] = value != "无" and "不烧" not in value
        elif name == "颗粒":
            if value in {"无", "不加"}:
                delivery["grain"] = None
            else:
                found = re.search(r"[0-9]+(?:\.[0-9]+)?", value)
                if found:
                    amount = float(found.group(0))
                    delivery["grain"] = amount if amount > 0 else None
        elif name == "接镜匹配":
            delivery["shot_match"] = value not in {"无", "关"}
        elif name == "画幅与帧率":
            size = re.search(r"([0-9]{2,5})\s*[×x*]\s*([0-9]{2,5})", value)
            if size:
                delivery["frame"] = [int(size.group(1)), int(size.group(2))]
            rate = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*fps", value, re.I)
            if rate:
                delivery["fps"] = float(rate.group(1))
    return delivery


def _entries(fields: dict[str, str], label: str) -> tuple[bool, list[str]]:
    """One kind of field, written once plain or as 「<label> 1..N」, in order.

    Returns whether the numbered form was used, and the values.
    """

    numbered: list[tuple[int, str]] = []
    plain: Optional[str] = None
    for key, value in fields.items():
        match = NUMBERED_RE[label].match(key)
        if not match:
            continue
        if match.group(1) is None:
            plain = value
        else:
            numbered.append((int(match.group(1)), value))
    if numbered:
        return True, [value for _, value in sorted(numbered)]
    return False, [] if plain is None else [plain]


def _subtitles(fields: dict[str, str]) -> list[dict[str, Any]]:
    def keywords(value: str) -> tuple[str, list[str]]:
        marked = KEYWORDS_RE.search(value)
        if not marked:
            return value.strip(), []
        words = [word.strip() for word in marked.group(1).split("｜")]
        return value[: marked.start()].strip(), words

    numbered, entries = _entries(fields, "字幕")
    cues: list[dict[str, Any]] = []
    if numbered:
        for value in entries:
            found = CUE_RE.match(value)
            if not found:
                continue
            text, words = keywords(found.group(3))
            cues.append({"s": float(found.group(1)), "e": float(found.group(2)), "text": text, "keys": words})
        return cues
    if not entries or entries[0].strip() == "无":
        return []
    text, words = keywords(entries[0])
    window = WINDOW_RE.match(fields.get("字幕时间", ""))
    return [{
        "s": float(window.group(1)) if window else None,
        "e": float(window.group(2)) if window else None,
        "text": text, "keys": words,
    }]


def _screen_texts(fields: dict[str, str]) -> list[dict[str, Any]]:
    texts = []
    for value in _entries(fields, "画面文字")[1]:
        if value.strip() == "无":
            continue
        countdown: Optional[float] = None
        resume = False
        counted = COUNTDOWN_RE.search(value)
        if counted:
            value = value[: counted.start()]
            if counted.group(1) == "接续":
                resume = True
            else:
                countdown = float(counted.group(1))
        found = SCREEN_TEXT_RE.match(value)
        if not found:
            continue
        items, rarities = [], []
        for raw in found.group(4).split("｜"):
            item = raw.strip()
            rare = RARITY_RE.search(item)
            cleaned = item[: rare.start()].strip() if rare else item
            items.append(re.sub(r"([0-9][0-9,]*\s*)／(?=\s*[0-9])", r"\1/", cleaned))
            rarities.append(rare.group(1) if rare else None)
        texts.append({
            "s": float(found.group(1)), "e": float(found.group(2)), "style": found.group(3),
            "items": items, "rarities": rarities, "countdown": countdown, "resume": resume,
        })
    return texts


def _sound_effects(fields: dict[str, str]) -> list[dict[str, Any]]:
    effects = []
    for value in _entries(fields, "音效")[1]:
        if value.strip() == "无":
            continue
        value, gain, offset, _ = _options(value)
        found = CUE_RE.match(value)
        if not found:
            continue
        effects.append({
            "s": float(found.group(1)), "e": float(found.group(2)), "path": found.group(3),
            "gain": gain, "from": offset,
        })
    return effects


def _options(value: str, *, allow_overlap: bool = False) -> tuple[str, float, float, bool]:
    """Split 「（起点：<秒>；增益：<dB>；叠音）」 off a sound line: (rest, gain, 起点, 叠音)."""

    stated = OPTIONS_RE.search(value)
    if not stated:
        return value, 0.0, 0.0, False
    options: dict[str, float] = {}
    overlap = False
    for part in re.split(r"[；;]", stated.group(1)):
        token = part.strip()
        if allow_overlap and token == "叠音":
            overlap = True
            continue
        found = OPTION_RE.match(token)
        if not found:
            return value, 0.0, 0.0, False
        options[found.group(1)] = float(found.group(2))
    return value[: stated.start()], options.get("增益", 0.0), options.get("起点", 0.0), overlap


def _voices(fields: dict[str, str]) -> list[dict[str, Any]]:
    voices = []
    for value in _entries(fields, "配音")[1]:
        if value.strip() == "无":
            continue
        value, gain, offset, overlap = _options(value, allow_overlap=True)
        found = VOICE_RE.match(value)
        if found:
            entry: dict[str, Any] = {
                "s": float(found.group(1)),
                "path": found.group(2),
                "gain": gain,
                "from": offset,
            }
            if overlap:
                entry["overlap"] = True
            voices.append(entry)
    return voices


def _bed(fields: dict[str, str]) -> Optional[dict[str, Any]]:
    """A 「环境声」 line: where it starts in its cut and what loops; path None is 「无」."""

    if "环境声" not in fields:
        return None
    value, gain, offset, _ = _options(fields["环境声"])
    found = BED_RE.match(value)
    if not found:
        return None
    path = found.group(2)
    return {"s": float(found.group(1) or 0.0), "path": None if path == "无" else path, "gain": gain, "from": offset}


def _move(fields: dict[str, str], still: bool) -> Optional[dict[str, Any]]:
    """A still's 「运镜」; 固定 when unwritten or unreadable, None on a video cut."""

    if not still:
        return None
    written = fields.get("运镜", "").strip()
    paced = MOVE_RATE_RE.match(written)
    if paced:
        return {"kind": paced.group(1), "amount": 0, "rate": float(paced.group(2))}
    found = MOVE_RE.match(written)
    if found:
        return {"kind": found.group(1), "amount": int(found.group(2)), "rate": None}
    return {"kind": "固定", "amount": 0, "rate": None}


def _seconds(value: Optional[str]) -> Optional[float]:
    try:
        return float((value or "").strip())
    except ValueError:
        return None


def _picture(fields: dict[str, str]) -> Any:
    if "画面" not in fields:
        return None
    raw = fields["画面"].strip()
    if not raw or raw == "无":
        return None
    if raw == "不校":
        return "不校"
    parsed = {
        PICTURE_KEYS[label]: float(value)
        for label, value in PICTURE_TERM_RE.findall(raw)
    }
    return parsed or None


def _split_unused_items(value: str) -> list[str]:
    items: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in value:
        if ch in "（(":
            depth += 1
            buf.append(ch)
        elif ch in "）)":
            if depth > 0:
                depth -= 1
            buf.append(ch)
        elif ch in "；;" and depth == 0:
            piece = "".join(buf).strip()
            if piece:
                items.append(piece)
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        items.append(tail)
    return items


def parse_cut_list(
    text: str,
    motion_shots: Optional[dict[str, str]] = None,
    group_shots: Optional[dict[str, list[str]]] = None,
) -> dict[str, Any]:
    text = check._strip_html_comments(_normalize_text(text))
    preamble: list[str] = []
    unused: list[str] = []
    pending: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    for raw in text.splitlines():
        heading = CUT_HEADING_RE.match(raw)
        if heading:
            current = {"id": heading.group(1), "title": (heading.group(2) or "").strip(), "fields": {}}
            pending.append(current)
            continue
        if re.match(r"^##[ \t\u3000]+", raw):
            current = None
            continue
        if current is None:
            preamble_field = CUT_FIELD_RE.match(raw)
            if preamble_field and _strip_emphasis(preamble_field.group(1)) == "未采用镜头":
                unused.extend(_split_unused_items(preamble_field.group(2)))
            preamble.append(raw)
            continue
        field = CUT_FIELD_RE.match(raw)
        if field:
            key = _strip_emphasis(field.group(1))
            if key not in current["fields"]:
                current["fields"][key] = field.group(2).strip()
    cuts = []
    cursor = 0.0
    for item in pending:
        fields = item["fields"]
        source = SOURCE_RE.match(fields.get("来源", ""))
        start, end, declared = (_seconds(fields.get(name)) for name in ("入点", "出点", "时长"))
        if source is None or start is None or end is None or declared is None:
            # The edit tool refuses this cut; the dashboard shows the rest.
            continue
        motion = source.group(1)
        still = motion.startswith(("SHOT-", "IMG-"))
        resolved_group_shots: Optional[list[str]] = None
        # A still names its storyboard shot directly; an IMG- still names none.
        if motion.startswith("SHOT-"):
            shot = motion
        elif still:
            shot = None
        elif motion.startswith("GROUP-"):
            resolved_group_shots = list((group_shots or {}).get(motion, []))
            shot = resolved_group_shots[0] if resolved_group_shots else None
        else:
            shot = (motion_shots or {}).get(motion) or ("SHOT-" + motion[len("MOTION-") :])
        cut_entry: dict[str, Any] = {
            "id": item["id"], "n": _number(item["id"]), "title": item["title"],
            "motion": motion, "shot": shot, "still": still, "move": _move(fields, still),
            "media": source.group(2), "in": start, "out": end, "sec": declared,
            "at": round(cursor, 3),
            "subs": _subtitles(fields), "texts": _screen_texts(fields), "sfx": _sound_effects(fields),
            "voices": _voices(fields), "bed": _bed(fields),
        }
        if resolved_group_shots is not None:
            cut_entry["group_shots"] = resolved_group_shots
        replay_raw = fields.get("重放", "").strip()
        if replay_raw and replay_raw != "无":
            cut_entry["replay"] = replay_raw
        picture_value = _picture(fields)
        if picture_value is not None:
            cut_entry["picture"] = picture_value
        cuts.append(cut_entry)
        cursor += declared
    if not cuts:
        raise ValueError("没有读到可用的 `## CUT-… · 标题` 段落（每段要有来源、入点、出点、时长）")
    return {**_delivery(preamble), "unused": unused, "cuts": cuts, "seconds": round(cursor, 3)}


# ------------------------------------------------------------------ review

# The review stage's suggested structure. Rule ids and the reviewer's internal
# severity names stay on the server: the creator reads what to change.
FINDING_RE = re.compile(r"^##[ \t\u3000]+(\S+) · (REV-[A-Za-z0-9-]+) · ([^\r\n]+)\r?$", re.MULTILINE)
DELETED_HOOKS_RE = re.compile(r"^##[ \t\u3000]*被删的强钩子[ \t\u3000]*\r?$", re.MULTILINE)
SEVERITIES = {
    "blocker": "must", "必须改": "must", "major": "should", "建议改": "should",
    "minor": "could", "可以更好": "could",
}
VERDICTS = {
    "PASS": ("可以继续", "ok"),
    "REVISE": ("需要修改", "bad"),
    "APPROVE": ("可以继续", "ok"),
    "APPROVE_WITH_NOTES": ("可以继续，有建议", "ok"),
    "PROVISIONAL": ("待补材料复核", "warn"),
    "REJECT": ("需要重做", "bad"),
}
TARGET_RE = re.compile(r"SHOT-[A-Z0-9-]+|CUT-[A-Z0-9-]+|(?:[A-Za-z0-9]+-)+SC[0-9]+")


def parse_review(text: str) -> dict[str, Any]:
    text = check._strip_html_comments(_normalize_text(text))
    head = {
        _strip_emphasis(key): value.strip()
        for key, value in FIELD_RE.findall(_slice_until_h2(text, 0))
    }
    parts = list(FINDING_RE.finditer(text))
    findings = []
    for match in parts:
        body = _slice_until_h2(text, match.end())
        fields = {_strip_emphasis(key): value.strip() for key, value in FIELD_RE.findall(body)}
        where = fields.get("位置", "")
        findings.append({
            "sev": SEVERITIES.get(match.group(1).casefold(), "could"),
            "id": match.group(2),
            "title": match.group(3).strip(),
            "where": where,
            "targets": list(dict.fromkeys(TARGET_RE.findall(where))),
            "evidence": fields.get("证据", ""),
            "impact": fields.get("影响", ""),
            "fix": fields.get("修改要求", ""),
        })
    deleted_hooks: list[str] = []
    for hook_match in DELETED_HOOKS_RE.finditer(text):
        hook_body = _slice_until_h2(text, hook_match.end())
        for raw_line in hook_body.splitlines():
            cleaned = re.sub(
                r"^[ \t\u3000]*(?:[-*+]|\d+[.、)])[ \t\u3000]+",
                "",
                raw_line.strip(),
            ).strip()
            if cleaned:
                deleted_hooks.append(cleaned)
    verdict = head.get("结论", "").strip()
    upper = verdict.upper()
    mapped = VERDICTS.get(upper)
    verdict_label = mapped[0] if mapped else verdict
    if mapped:
        verdict_tone = mapped[1]
    elif not verdict:
        verdict_tone = "warn"
    elif "可以继续" in verdict:
        verdict_tone = "ok"
    elif "待补" in verdict:
        verdict_tone = "warn"
    else:
        verdict_tone = "bad"
    return {
        "scope": head.get("范围", "").strip(),
        "verdict": verdict_label,
        "verdictTone": verdict_tone,
        "independent": "独立" in head.get("复核方式", ""),
        "findings": findings,
        "deleted_hooks": deleted_hooks,
    }


# ------------------------------------------------------------------ episode

def _attempt(
    problems: list[str], document: str, reader: Callable[[str], Any], text: Optional[str]
) -> Any:
    if text is None:
        return None
    try:
        return reader(text)
    except (ValueError, KeyError, IndexError, AttributeError, TypeError) as exc:
        detail = str(exc) if isinstance(exc, ValueError) and str(exc) else "格式和约定不一致"
        problems.append(f"{document} 没有按结构读出来：{detail}。下面按原文显示。")
        return None


def episode_title(script: Optional[dict[str, Any]]) -> str:
    return str(script.get("title", "")) if script else ""


def metrics(script: Optional[dict[str, Any]], board: Optional[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"shots": 0, "seconds": 0, "avg": None, "close": None, "unsized": 0,
                              "vo": None, "spoken": 0}
    if board:
        shots = board["shots"]
        seconds = sum(shot["sec"] for shot in shots)
        sized = [shot for shot in shots if shot["scale"]]
        result.update({
            "shots": len(shots),
            "seconds": round(seconds, 3),
            "avg": round(seconds / len(shots), 2) if shots else None,
            "close": round(sum(1 for shot in shots if shot["close"]) / len(shots), 3) if shots else None,
            "closeCount": sum(1 for shot in shots if shot["close"]),
            "unsized": len(shots) - len(sized),
        })
    if script:
        counts = voice_share(script)
        result["spoken"] = counts["spoken"]
        result["vo"] = round(counts["vo"] / counts["spoken"], 3) if counts["spoken"] else None
    return result


def read_episode(episode_id: str, documents: dict[str, Optional[str]], review: Optional[str]) -> dict[str, Any]:
    """Parse whatever of the episode exists. Missing documents are ``None``."""

    documents = {
        name: _normalize_text(value) if value is not None else None
        for name, value in documents.items()
    }
    if review is not None:
        review = _normalize_text(review)
    problems: list[str] = []
    script = _attempt(problems, SCREENPLAY, parse_screenplay, documents.get(SCREENPLAY))
    settings = _attempt(problems, SETTINGS, parse_settings, documents.get(SETTINGS))
    board = _attempt(problems, STORYBOARD, parse_storyboard, documents.get(STORYBOARD))
    images = _attempt(problems, IMAGE_PROMPTS, parse_image_prompts, documents.get(IMAGE_PROMPTS))
    videos = _attempt(problems, VIDEO_PROMPTS, parse_video_prompts, documents.get(VIDEO_PROMPTS))
    groups = usable_groups(documents.get(VIDEO_PROMPTS), problems, documents) if videos else []
    if settings:
        # `入画` is resolved the way the checker resolves it: every shot whose
        # 出场设定 lists the entry. Without a storyboard there are none yet.
        for item in settings["items"]:
            item_locks = item.get("locks") or ([item["lock"]] if item.get("lock") else [])
            for lock in item_locks:
                if lock and lock["shots"] == [check.IN_FRAME_SCOPE]:
                    lock["scope"] = check.IN_FRAME_SCOPE
                    lock["shots"] = [
                        shot["id"]
                        for shot in (board or {}).get("shots", [])
                        if any(
                            b["cat"] == item["cat"] and b["name"] == item["name"]
                            for b in shot["basis"]
                        )
                    ]
    motion_shots = {v["id"]: v["shot"] for v in (videos or []) if v.get("shot")}
    group_shots: dict[str, list[str]] = {}
    raw_video = documents.get(VIDEO_PROMPTS)
    music = parse_music_prompts(raw_video) if raw_video else []
    if raw_video:
        for raw_group in parse_video_groups(raw_video):
            resolved_members: list[str] = []
            for member in raw_group["members"]:
                member_shot = motion_shots.get(member)
                if not member_shot and member.startswith("MOTION-"):
                    member_shot = "SHOT-" + member[len("MOTION-") :]
                if member_shot:
                    resolved_members.append(member_shot)
            group_shots[raw_group["id"]] = resolved_members
    cutlist = _attempt(
        problems,
        CUT_LIST,
        lambda raw: parse_cut_list(raw, motion_shots=motion_shots, group_shots=group_shots),
        documents.get(CUT_LIST),
    )
    parsed_review = _attempt(problems, "审查意见", parse_review, review)
    return {
        "id": episode_id,
        "title": episode_title(script),
        "script": script,
        "settings": settings,
        "board": board,
        "imagePrompts": images,
        "videoPrompts": videos,
        "videoGroups": groups,
        "musicPrompts": music,
        "cutlist": cutlist,
        "review": parsed_review,
        "metrics": metrics(script, board),
        "problems": problems,
    }


def review_counts(review: Optional[dict[str, Any]]) -> dict[str, int]:
    counts = {"must": 0, "should": 0, "could": 0}
    for finding in (review or {}).get("findings", []):
        counts[finding["sev"]] += 1
    return counts


# ------------------------------------------------------------------ search

def search_entries(episode: dict[str, Any]) -> list[dict[str, Any]]:
    """Everything a creator asks "where is it" about, one row per findable thing.

    ``view``/``arg`` name where the result opens, in the dashboard's own terms.
    """

    ep = episode["id"]
    rows: list[dict[str, Any]] = []

    def add(group: str, who: str, title: str, extra: str, view: str, arg: str = "", **more: Any) -> None:
        rows.append({"g": group, "w": who, "t": title, "x": extra, "ep": ep, "view": view, "arg": arg, **more})

    for shot in (episode.get("board") or {}).get("shots", []):
        add("镜头", f"{shot['n']} {shot['scale']}".strip(), shot["title"],
            " ".join([shot["purpose"], shot["framing"], shot["move"], shot["start"], shot["action"],
                      shot["end"], shot["sound"], shot["screenText"],
                      shot.get("keyframe", ""), shot.get("closing_keyframe", "")]),
            "board", shot["id"])
    for scene in (episode.get("script") or {}).get("scenes", []):
        short = _number(scene["id"])
        for block in scene["blocks"]:
            if block["k"] == "line":
                add("台词", block["who"], block["text"], "", "script", scene["id"], line=block["text"])
            elif block["k"] == "tag":
                group = {"画面文字": "画面文字", "SFX": "音效"}.get(block["tag"], "剧本")
                add(group, f"SC{short}", block["text"], "", "script", scene["id"], line=block["text"])
            else:
                add("剧本动作", f"SC{short}", block["text"], "", "script", scene["id"])
    for item in (episode.get("settings") or {}).get("items", []):
        item_locks = item.get("locks") or ([item["lock"]] if item.get("lock") else [])
        lock_terms = [
            part
            for lk in item_locks
            if lk
            for part in (lk.get("id", ""), lk.get("name", ""), lk.get("surface", ""))
            if part
        ]
        add("设定", item["cat"], item["name"],
            " ".join([*item["desc"], *item["fields"].values(), *item["designators"], *lock_terms]),
            "settings", item["name"])
    group_of = {member: group["id"] for group in episode.get("videoGroups") or [] for member in group["members"]}
    known_shots = {shot["id"] for shot in (episode.get("board") or {}).get("shots", [])}
    for group in episode.get("videoGroups") or []:
        add("提示词", group["id"], group["title"], group["prompt"], "prompts", "video", id=group["id"])
    for prompt in episode.get("videoPrompts") or []:
        if prompt["id"] in group_of and prompt["shot"] in known_shots:
            # Its own card is folded into the group's; the shot drawer still shows it.
            add("提示词", prompt["id"], prompt["title"], prompt["prompt"], "board", prompt["shot"])
        elif prompt["id"] in group_of:
            add("提示词", prompt["id"], prompt["title"], prompt["prompt"], "prompts", "video", id=group_of[prompt["id"]])
        else:
            add("提示词", prompt["id"], prompt["title"], prompt["prompt"], "prompts", "video", id=prompt["id"])
    for prompt in episode.get("imagePrompts") or []:
        add("提示词", prompt["id"], prompt["title"], prompt["prompt"] + " " + prompt["use"],
            "prompts", "image", id=prompt["id"])
    for music in episode.get("musicPrompts") or []:
        add("配乐", music["id"], music["title"],
            " ".join([music["prompt"], music["use"], music["mood"], music["range"]]).strip(),
            "prompts", "video", id=music["id"])
    for finding in (episode.get("review") or {}).get("findings", []):
        label = {"must": "必须改", "should": "建议改", "could": "可以更好"}[finding["sev"]]
        add("审查", label, finding["title"],
            " ".join([finding["evidence"], finding["impact"], finding["fix"], " ".join(finding["targets"])]),
            "review", finding["id"])
    for hook in (episode.get("review") or {}).get("deleted_hooks", []):
        add("审查", "被删的强钩子", hook, "", "review", "deleted-hooks")
    for cut in (episode.get("cutlist") or {}).get("cuts", []):
        for sub in cut["subs"]:
            add("剪辑", cut["id"], sub["text"], cut["title"], "film", "", cut=cut["id"])
        for text in cut["texts"]:
            add("剪辑", cut["id"], "｜".join(text["items"]), text["style"], "film", "", cut=cut["id"])
    return rows


def search(rows: list[dict[str, Any]], query: str, limit: int = 60) -> list[dict[str, Any]]:
    """Rows whose title, label or body contain the query, with where it matched."""

    needle = query.strip()
    if not needle:
        return []
    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    hits = []
    for row in rows:
        for field in ("t", "w", "x"):
            haystack = str(row[field])
            found = pattern.search(haystack)
            if not found:
                continue
            at, end = found.start(), found.end()
            start = max(0, at - 24) if field == "x" else 0
            snippet = haystack[start : end + 60] if field == "x" else haystack
            hits.append({
                **{key: value for key, value in row.items() if key != "x"},
                "field": field,
                "snippet": snippet,
                "clipped": start > 0,
                "at": at - start,
                "len": end - at,
            })
            break
        if len(hits) >= limit:
            break
    return hits
