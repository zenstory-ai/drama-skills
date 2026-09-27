#!/usr/bin/env python3
"""Assemble a short-drama episode from its cut list.

Three subcommands, deliberately separated so a report can never borrow one's
evidence for another's claim:

``check``   parse and cross-check ``剪辑单.md`` against the project. No rendering.
``render``  cut, join, mix sound effects, burn subtitles and screen text, and
            normalize loudness into 制作成果/成片/.
``verify``  measure an already-rendered film and print the numbers.

``verify`` prints measurements, never verdicts. Whether the film is any good is
a question for review or for the creator, and no number here answers it.
"""

from __future__ import annotations

import argparse
import json
import operator
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, NamedTuple, Optional, Sequence

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "short-drama-edit needs Python {}.{} or newer; this interpreter is {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )

CUT_LIST_NAME = "剪辑单.md"
MOTION_DOCUMENT = "视频提示词.md"
SCREENPLAY_DOCUMENT = "剧本.md"
OUTPUT_DIRECTORY = Path("制作成果") / "成片"
SEGMENT_DIRECTORY = "分段"
# A CJK subtitle needs a font that actually has the glyphs. libass falls back
# through fontconfig when this one is absent, which is the right behaviour: a
# missing font shows as a different typeface, never as empty boxes.
SUBTITLE_FONT = "Noto Sans CJK SC"
# The optional Remotion route ships as source only. Its `node_modules` is
# hundreds of megabytes of third-party code that is neither creative content nor
# part of the skill, so the runnable copy lives outside the project entirely --
# the same rule the suite applies to adapter configuration and credentials.
REMOTION_SOURCE = Path(__file__).resolve().parent.parent / "assets" / "remotion"
REMOTION_SOURCE_FILES = (
    "package.json",
    "tsconfig.json",
    "remotion.config.ts",
    "src/index.ts",
    "src/schema.ts",
    "src/Root.tsx",
    "src/Overlay.tsx",
    "src/Subtitles.tsx",
    "src/font.ts",
    "src/rules.mjs",
    "src/screen/ScreenText.tsx",
    "src/screen/tokens.ts",
    "src/screen/chrome.tsx",
    "src/screen/Card.tsx",
    "src/screen/SystemPanel.tsx",
    "src/screen/TaskPanel.tsx",
    "src/screen/CornerChip.tsx",
)
DEFAULT_REMOTION_WORKSPACE = Path.home() / ".cache" / "short-drama-edit" / "remotion"
REMOTION_COMPOSITION = "Overlay"
# Remotion defaults its worker count to the machine's core count, and each worker
# is a browser holding a full frame. On a 10-core / 8 GB laptop that took the
# machine down mid-render. Raise this only after measuring the host.
DEFAULT_REMOTION_CONCURRENCY = 2
SUBTITLE_RENDERERS = ("ffmpeg", "remotion")

CUT_HEADING = re.compile(r"^##\s+(CUT-[^\s·]+)\s*(?:·\s*(.*))?$")
MOTION_HEADING = re.compile(r"^##\s+(MOTION-[^\s·]+)")
FIELD = re.compile(r"^-\s*([^：]+)：\s*(.*)$")
UNUSED_LINE = re.compile(r"^-\s*未采用镜头：\s*(.*)$")
# A source line is "MOTION-... · relative/path". The separator is the same
# middle dot the storyboard uses for reference slots, so the two documents read
# alike; a plain slash would collide with the path itself.
SOURCE = re.compile(r"^(MOTION-\S+)\s*·\s*(.+?)\s*$")
SUBTITLE_WINDOW = re.compile(r"^\s*([0-9.]+)\s*[-–~]\s*([0-9.]+)\s*$")
# One shot can carry several lines: an exchange of three is one shot, not three.
# Numbered fields keep them ordered and let each one state its own window.
SUBTITLE_FIELD = re.compile(r"^字幕(?:\s*(\d+))?$")
SUBTITLE_CUE = re.compile(r"^\s*([0-9.]+)\s*[-–~]\s*([0-9.]+)\s+(.+?)\s*$")
# Burned subtitles follow GY/T 288 and short-drama practice: no closing
# punctuation, a pause inside a line shows as a full-width space, and ？ ！ stay
# because they change how the line reads. Only the burned text changes: the cut
# list keeps the screenplay's punctuation, so the line is still checked against
# 剧本.md as written. ASCII marks are left alone mid-line: they sit inside
# numbers such as 1,000.
SUBTITLE_PAUSE_MARKS = "，、；：。"
SUBTITLE_KEPT_END_MARKS = "？！?!"
SUBTITLE_END_MARKS = "".join(
    mark for mark in "，、；：。…—～！？,.;:!?~" if mark not in SUBTITLE_KEPT_END_MARKS
)
# One line on screen: a longer line is split at its pauses into cues shown one
# after another, each given a share of the window by its character count.
SUBTITLE_MAX_VISIBLE = 12
# 「字幕：… （重点：词｜词）」 marks words to highlight; they must occur in the line.
SUBTITLE_KEYWORDS = re.compile(r"[（(]重点[：:]\s*(.+?)\s*[）)]\s*$")
# Colour by who is speaking, read from 剧本.md rather than written again here:
# `[VO] 系统：` is the system voice, any other `[VO]` an inner or narrating voice.
SPOKEN_LINE = re.compile(
    r"^\s*(?:\[(VO|OS)\]\s*)?([^\s：:\[\]（(]+)(?:[（(][^）)]*[）)])?\s*[：:]\s*(.+?)\s*$"
)
SYSTEM_SPEAKER = "系统"
# The same values as the Remotion layer's `src/screen/tokens.ts`.
SUBTITLE_COLOURS = {"line": "#FFFFFF", "vo": "#9FE8FF", "system": "#3FE0FF"}
SUBTITLE_KEYWORD_COLOUR = "#FFD400"
# Text the picture had to leave blank -- a system panel, a countdown, follower
# counts on a monitor -- because video models garble it. It is drawn here, over
# the finished picture, and every item must come from a [画面文字] line.
SCREEN_TEXT_FIELD = re.compile(r"^画面文字(?:\s*(\d+))?$")
SCREEN_TEXT_STYLES = {"卡片": "card", "系统面板": "system", "任务面板": "task", "角标": "corner"}
SCREEN_TEXT = re.compile(
    r"^\s*([0-9.]+)\s*[-–~]\s*([0-9.]+)\s+(" + "|".join(SCREEN_TEXT_STYLES) + r")\s+(.+?)\s*$"
)
SCREEN_TEXT_ITEM_SEPARATOR = "｜"
COUNTDOWN = re.compile(r"[（(]倒计时[：:]\s*([0-9]+(?:\.[0-9]+)?|接续)\s*[）)]\s*$")
COUNTDOWN_STYLES = {"任务面板", "角标"}
# 「现金 10 万（传说）」: an item's rarity sets its colour. Unmarked items are 稀有.
RARITY = re.compile(r"[（(](传说|史诗|稀有)[）)]$")
RARITY_STYLES = {"系统面板", "任务面板"}
# The three panels share the top of the frame; the chip has its own corner.
SCREEN_TEXT_SLOTS = {"卡片": "面板", "系统面板": "面板", "任务面板": "面板", "角标": "角标"}
SCREENPLAY_SCREEN_TEXT = re.compile(r"^\s*\[画面文字\]\s*(.+?)\s*$", re.MULTILINE)
# Two pieces of the same screen text that meet at a cut are one piece on
# screen: a chip that persists across five shots must not re-enter five times.
SCREEN_TEXT_JOIN_GAP = 0.05
SOUND_EFFECT_FIELD = re.compile(r"^音效(?:\s*(\d+))?$")
GAIN = re.compile(r"[（(]增益[：:]\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*(?:dB)?\s*[）)]\s*$", re.I)
GAIN_LIMITS = (-40.0, 6.0)
# A shot-match is three numbers and nothing else. Anything richer belongs in a
# grading tool, and anything implicit belongs nowhere: a correction the cut list
# does not state is a correction no reviewer can see.
PICTURE_KEYS = {"亮度": "brightness", "饱和": "saturation", "色温": "warmth"}
PICTURE_TERM = re.compile(r"(亮度|饱和|色温)\s*([+-]?[0-9]*\.?[0-9]+)")
# Each term's real range, not a symmetric magnitude: ffmpeg's `eq` takes
# saturation in 0..3, so a negative value that passes an abs() bound is accepted
# by the document and then rejected by the renderer, halfway through a render.
PICTURE_LIMITS = {
    "brightness": (-0.25, 0.25),
    "saturation": (0.0, 2.0),
    "warmth": (-30.0, 30.0),
}
# 「画面：不校」 keeps a cut exactly as generated: no stated correction and no
# automatic one. 「画面：无」 only says nothing is stated.
PICTURE_UNTOUCHED = "不校"
# Clips are generated one by one and come back up to ~35 luma apart at a cut,
# which reads as a flash. Within one scene, render pulls each cut this far
# toward the scene's median per-channel mean and spread: close enough to stop
# the flash, short of flattening a deliberate change inside the scene.
SHOT_MATCH_STRENGTH = 0.7
# A near-flat clip (a black insert) has almost no spread; stretching it to the
# scene's would amplify noise, so the gain is held to a plausible grade.
SHOT_MATCH_GAIN_LIMITS = (0.6, 1.6)
SHOT_MATCH_SAMPLE = "fps=4,scale=64:-2"
STORYBOARD_DOCUMENT = "分镜.md"
SHOT_HEADING = re.compile(r"^##\s+(SHOT-[^\s·]+)")
SHOT_REFERENCE = re.compile(r"SHOT-[A-Za-z0-9-]+")
SCENE_ID = re.compile(r"[A-Za-z]+[0-9]+-SC[0-9]+")
# verify reads the delivered film at this size in grey, one value per pixel.
FRAME_PROBE_SIZE = (90, 160)
# A frame is suspect when it differs from both neighbours by more than this
# (mean absolute difference, 0-255) while the neighbours differ from each other
# by less than this share of it: a picture that belongs to neither side, such
# as a strip of another shot decoded into the top of the frame.
FLASH_FRAME_DIFFERENCE = 8.0
FLASH_NEIGHBOUR_SHARE = 0.5
# A panel entering over 2-3 frames of glitch trips the detector too; a suspect
# frame this soon after a screen text starts is labelled as that.
SCREEN_TEXT_ENTRANCE = 0.15
# Mean-luma change across a cut (0-255) above which verify asks for a look.
CUT_JUMP_NOTICE = 20.0
TOLERANCE = 0.005
# ffmpeg's `noise` strength runs to 100, which is snow, not grain. The useful
# band for a finished film is single digits; the cap keeps a typo from shipping
# a broken-signal look that measures perfectly fine.
GRAIN_LIMIT = 20.0


class EditError(Exception):
    """A defect in the cut list or its inputs, reported rather than raised through."""


class ScreenText(NamedTuple):
    start: float
    end: float
    style: str
    items: tuple[str, ...]
    # Seconds left at `start`; None when nothing counts down.
    countdown: Optional[float] = None
    # 「倒计时：接续」 carries on from the latest earlier countdown in the film.
    resume: bool = False
    # One per item: 传说 / 史诗 / 稀有, or None where the item names none.
    rarities: tuple[Optional[str], ...] = ()


# (start, end, text as in 剧本.md, words to highlight); times relative to the cut.
Subtitle = tuple[Optional[float], Optional[float], str, tuple[str, ...]]


class SoundEffect(NamedTuple):
    start: float
    end: float
    path: str
    gain_db: float = 0.0


class Cut(NamedTuple):
    cut_id: str
    title: str
    motion: str
    media: str
    start: float
    end: float
    declared: float
    subtitles: tuple[Subtitle, ...]
    picture: dict[str, float]
    line_number: int
    screen_texts: tuple[ScreenText, ...] = ()
    sound_effects: tuple[SoundEffect, ...] = ()
    # 「画面：不校」: neither a stated nor an automatic correction.
    untouched: bool = False


class Delivery(NamedTuple):
    target_seconds: Optional[float]
    loudness_lufs: Optional[float]
    burn_subtitles: bool
    frame_size: Optional[tuple[int, int]]
    fps: Optional[float]
    grain: Optional[float]
    # 「接镜匹配：无」 turns the automatic within-scene match off.
    shot_match: bool = True


class ChannelStats(NamedTuple):
    """Per-channel (R, G, B) mean and standard deviation, 0-255."""

    mean: tuple[float, ...]
    spread: tuple[float, ...]


class ShotMatch(NamedTuple):
    """Per-channel `value * gain + offset`, applied to one cut."""

    gains: tuple[float, ...]
    offsets: tuple[float, ...]


def _seconds(raw: str, *, field: str, line: int) -> float:
    try:
        return float(raw.strip())
    except ValueError as error:
        raise EditError(f"{CUT_LIST_NAME}:{line}: {field} 不是秒数: {raw!r}") from error


def _parse_delivery(lines: Sequence[str]) -> Delivery:
    target = None
    loudness = None
    burn = True
    frame_size: Optional[tuple[int, int]] = None
    fps: Optional[float] = None
    grain: Optional[float] = None
    shot_match = True
    for raw in lines:
        match = FIELD.match(raw)
        if not match:
            continue
        name, value = match.group(1).strip(), match.group(2).strip()
        if name == "成片目标时长":
            found = re.search(r"[0-9]+(?:\.[0-9]+)?", value)
            if found:
                target = float(found.group(0))
        elif name == "交付响度":
            found = re.search(r"-?[0-9]+(?:\.[0-9]+)?", value)
            if found:
                loudness = float(found.group(0))
        elif name == "字幕":
            burn = "无" != value.strip() and "不烧" not in value
        elif name == "颗粒":
            # Grain belongs to the delivery spec rather than to a cut, for the
            # same reason loudness does: applied per cut it would become one
            # more thing that differs between segments, which is the defect it
            # is here to cover.
            if value.strip() in {"无", "不加"}:
                grain = None
            else:
                found = re.search(r"[0-9]+(?:\.[0-9]+)?", value)
                if found:
                    amount = float(found.group(0))
                    if not 0.0 <= amount <= GRAIN_LIMIT:
                        raise EditError(
                            f"{CUT_LIST_NAME}: 颗粒 {amount} 超出 0–{GRAIN_LIMIT:g}；"
                            "这一档以上不再像胶片，像信号故障"
                        )
                    grain = amount or None
        elif name == "接镜匹配":
            shot_match = value.strip() not in {"无", "关"}
        elif name == "画幅与帧率":
            size = re.search(r"([0-9]{2,5})\s*[×x*]\s*([0-9]{2,5})", value)
            if size:
                frame_size = (int(size.group(1)), int(size.group(2)))
            rate = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*fps", value, re.I)
            if rate:
                fps = float(rate.group(1))
    return Delivery(target, loudness, burn, frame_size, fps, grain, shot_match)


def parse_cut_list(path: Path) -> tuple[Delivery, list[Cut], list[str]]:
    """Read 剪辑单.md into a delivery spec, ordered cuts, and unused-material notes."""

    if not path.is_file():
        raise EditError(f"没有 {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    preamble: list[str] = []
    unused: list[str] = []
    cuts: list[Cut] = []
    current: Optional[dict[str, Any]] = None

    def close(pending: Optional[dict[str, Any]]) -> None:
        if pending is None:
            return
        cuts.append(_finish_cut(pending))

    for number, raw in enumerate(lines, start=1):
        heading = CUT_HEADING.match(raw)
        if heading:
            close(current)
            current = {
                "cut_id": heading.group(1),
                "title": (heading.group(2) or "").strip(),
                "line": number,
                "fields": {},
            }
            continue
        if raw.startswith("## "):
            close(current)
            current = None
            continue
        if current is None:
            unused_match = UNUSED_LINE.match(raw)
            if unused_match:
                unused.extend(
                    item.strip() for item in unused_match.group(1).split("；") if item.strip()
                )
            preamble.append(raw)
            continue
        field = FIELD.match(raw)
        if field:
            current["fields"][field.group(1).strip()] = (field.group(2).strip(), number)
    close(current)
    return _parse_delivery(preamble), cuts, unused


def _finish_cut(pending: dict[str, Any]) -> Cut:
    fields: dict[str, tuple[str, int]] = pending["fields"]
    cut_id: str = pending["cut_id"]
    line: int = pending["line"]

    def required(name: str) -> tuple[str, int]:
        if name not in fields:
            raise EditError(f"{CUT_LIST_NAME}:{line}: {cut_id} 缺少「{name}」")
        return fields[name]

    source_raw, source_line = required("来源")
    source = SOURCE.match(source_raw)
    if not source:
        raise EditError(
            f"{CUT_LIST_NAME}:{source_line}: {cut_id} 的来源要写成 "
            f"「MOTION-... · 项目相对路径」，当前是 {source_raw!r}"
        )
    start_raw, start_line = required("入点")
    end_raw, end_line = required("出点")
    declared_raw, declared_line = required("时长")
    subtitles = _parse_subtitles(fields, cut_id=cut_id, line=line)
    picture: dict[str, float] = {}
    picture_raw = fields.get("画面")
    untouched = picture_raw is not None and picture_raw[0].strip() == PICTURE_UNTOUCHED
    if picture_raw is not None:
        text, where = picture_raw
        if text.strip() not in {"", "无", PICTURE_UNTOUCHED}:
            for label, value in PICTURE_TERM.findall(text):
                key = PICTURE_KEYS[label]
                number = float(value)
                low, high = PICTURE_LIMITS[key]
                if not low <= number <= high:
                    raise EditError(
                        f"{CUT_LIST_NAME}:{where}: {cut_id} 的画面「{label}」超出允许范围"
                        f"（{low:g} 到 {high:g}）：{number}"
                    )
                picture[key] = number
            if not picture:
                raise EditError(
                    f"{CUT_LIST_NAME}:{where}: {cut_id} 的画面写了内容但没有可执行的项；"
                    "只认「亮度 <数>」「饱和 <数>」「色温 <数>」，不需要校正时写「无」，"
                    f"连自动接镜也不要时写「{PICTURE_UNTOUCHED}」"
                )
    return Cut(
        cut_id=cut_id,
        title=pending["title"],
        motion=source.group(1),
        media=source.group(2),
        start=_seconds(start_raw, field="入点", line=start_line),
        end=_seconds(end_raw, field="出点", line=end_line),
        declared=_seconds(declared_raw, field="时长", line=declared_line),
        subtitles=subtitles,
        picture=picture,
        line_number=line,
        screen_texts=_parse_screen_texts(fields, cut_id=cut_id, line=line),
        sound_effects=_parse_sound_effects(fields, cut_id=cut_id, line=line),
        untouched=untouched,
    )


def _field_entries(
    fields: dict[str, tuple[str, int]],
    pattern: re.Pattern[str],
    label: str,
    *,
    cut_id: str,
    line: int,
) -> tuple[bool, list[tuple[int, str, int]]]:
    """Collect one kind of field, written once plain or as 「<label> 1..N」.

    Returns whether the numbered form was used, and (number, value, line) rows
    in number order. The plain form comes back as a single row numbered 1.
    """

    numbered: list[tuple[int, str, int]] = []
    plain: Optional[tuple[str, int]] = None
    for key, (value, where) in fields.items():
        match = pattern.match(key.strip())
        if not match:
            continue
        if match.group(1) is None:
            plain = (value, where)
        else:
            numbered.append((int(match.group(1)), value, where))

    if numbered and plain is not None:
        raise EditError(
            f"{CUT_LIST_NAME}:{line}: {cut_id} 同时写了「{label}」和「{label} N」；"
            f"一段用一种写法——一条用「{label}」，多条全部编号"
        )
    if not numbered:
        return False, [] if plain is None else [(1, plain[0], plain[1])]
    numbered.sort()
    expected = list(range(1, len(numbered) + 1))
    if [item[0] for item in numbered] != expected:
        raise EditError(
            f"{CUT_LIST_NAME}:{line}: {cut_id} 的{label}编号要从 1 连续排到 "
            f"{len(numbered)}，当前是 {[item[0] for item in numbered]}"
        )
    return True, numbered


def _parse_screen_texts(
    fields: dict[str, tuple[str, int]], *, cut_id: str, line: int
) -> tuple[ScreenText, ...]:
    """Read 「画面文字 N：<起>-<止> <样式> <项>｜<项>…（倒计时：<秒>|接续）」 lines."""

    _, entries = _field_entries(fields, SCREEN_TEXT_FIELD, "画面文字", cut_id=cut_id, line=line)
    texts: list[ScreenText] = []
    for index, value, where in entries:
        if value.strip() == "无":
            continue
        countdown: Optional[float] = None
        resume = False
        counted = COUNTDOWN.search(value)
        if counted:
            value = value[: counted.start()]
            if counted.group(1) == "接续":
                resume = True
            else:
                countdown = float(counted.group(1))
        found = SCREEN_TEXT.match(value)
        if not found:
            raise EditError(
                f"{CUT_LIST_NAME}:{where}: {cut_id} 的「画面文字 {index}」要写成"
                f"「<起>-<止> <样式> <文字>」，样式是 {'/'.join(SCREEN_TEXT_STYLES)}"
            )
        style = found.group(3)
        items: list[str] = []
        rarities: list[Optional[str]] = []
        for raw in found.group(4).split(SCREEN_TEXT_ITEM_SEPARATOR):
            item = raw.strip()
            rare = RARITY.search(item)
            if rare and style not in RARITY_STYLES:
                raise EditError(
                    f"{CUT_LIST_NAME}:{where}: {cut_id} 的「画面文字 {index}」是{style}，"
                    f"稀有度只用在{'或'.join(sorted(RARITY_STYLES))}上"
                )
            items.append(item[: rare.start()].strip() if rare else item)
            rarities.append(rare.group(1) if rare else None)
        if not all(items):
            raise EditError(
                f"{CUT_LIST_NAME}:{where}: {cut_id} 的「画面文字 {index}」有空项；"
                f"「{SCREEN_TEXT_ITEM_SEPARATOR}」两边都要有文字"
            )
        if counted and style not in COUNTDOWN_STYLES:
            raise EditError(
                f"{CUT_LIST_NAME}:{where}: {cut_id} 的「画面文字 {index}」是{style}，"
                f"倒计时只放在{'或'.join(sorted(COUNTDOWN_STYLES))}上"
            )
        texts.append(ScreenText(
            float(found.group(1)), float(found.group(2)), style, tuple(items),
            countdown, resume, tuple(rarities),
        ))

    by_slot: dict[str, list[ScreenText]] = {}
    for text in texts:
        by_slot.setdefault(SCREEN_TEXT_SLOTS[text.style], []).append(text)
    for slot, group in by_slot.items():
        ordered = sorted(group, key=lambda item: item.start)
        for earlier, later in zip(ordered, ordered[1:]):
            if later.start < earlier.end - TOLERANCE:
                raise EditError(
                    f"{CUT_LIST_NAME}:{line}: {cut_id} 的画面文字时间重叠：同一位置（{slot}）"
                    f"{earlier.start:g}-{earlier.end:g} 与 {later.start:g}-{later.end:g}"
                )
    return tuple(texts)


def _parse_sound_effects(
    fields: dict[str, tuple[str, int]], *, cut_id: str, line: int
) -> tuple[SoundEffect, ...]:
    """Read 「音效 N：<起>-<止> <文件>（增益：<dB>）」 lines."""

    _, entries = _field_entries(fields, SOUND_EFFECT_FIELD, "音效", cut_id=cut_id, line=line)
    effects: list[SoundEffect] = []
    for index, value, where in entries:
        if value.strip() == "无":
            continue
        gain = 0.0
        stated = GAIN.search(value)
        if stated:
            value = value[: stated.start()]
            gain = float(stated.group(1))
            low, high = GAIN_LIMITS
            if not low <= gain <= high:
                raise EditError(
                    f"{CUT_LIST_NAME}:{where}: {cut_id} 的「音效 {index}」增益 {gain:g} dB "
                    f"超出 {low:g} 到 {high:g}"
                )
        found = SUBTITLE_CUE.match(value)
        if not found:
            raise EditError(
                f"{CUT_LIST_NAME}:{where}: {cut_id} 的「音效 {index}」要写成"
                "「<起>-<止> <项目相对路径>」"
            )
        effects.append(SoundEffect(float(found.group(1)), float(found.group(2)), found.group(3), gain))
    return tuple(effects)


def _parse_subtitles(
    fields: dict[str, tuple[str, int]], *, cut_id: str, line: int
) -> tuple[Subtitle, ...]:
    """Read every subtitle a cut declares, in written order.

    A shot is not one line. The exchange "就是什么 / 就是少了点东西 / 少了什么" is a
    single over-shoulder shot carrying three, and a cut list that can hold only
    one of them silently drops the other two — the film then plays lines that
    never reach the screen, and nothing reports it.
    """

    is_numbered, entries = _field_entries(
        fields, SUBTITLE_FIELD, "字幕", cut_id=cut_id, line=line
    )

    def keywords(value: str, where: int) -> tuple[str, tuple[str, ...]]:
        marked = SUBTITLE_KEYWORDS.search(value)
        if not marked:
            return value.strip(), ()
        text = value[: marked.start()].strip()
        words = tuple(
            word.strip() for word in marked.group(1).split(SCREEN_TEXT_ITEM_SEPARATOR)
        )
        stray = [word for word in words if not word or word not in text]
        if stray:
            raise EditError(
                f"{CUT_LIST_NAME}:{where}: {cut_id} 的字幕重点词不在这句里: {stray}"
            )
        return text, words

    if is_numbered:
        cues: list[Subtitle] = []
        for index, value, where in entries:
            found = SUBTITLE_CUE.match(value)
            if not found:
                raise EditError(
                    f"{CUT_LIST_NAME}:{where}: {cut_id} 的「字幕 {index}」要写成"
                    "「<起>-<止> <台词>」，多句必须各自带时间"
                )
            text, words = keywords(found.group(3), where)
            cues.append((float(found.group(1)), float(found.group(2)), text, words))
        for earlier, later in zip(cues, cues[1:]):
            if later[0] is not None and earlier[1] is not None and later[0] < earlier[1]:
                raise EditError(
                    f"{CUT_LIST_NAME}:{line}: {cut_id} 的字幕时间重叠：两句不能同时在屏上"
                )
        return tuple(cues)

    if not entries or entries[0][1].strip() == "无":
        return ()
    text, words = keywords(entries[0][1], entries[0][2])
    window_raw = fields.get("字幕时间")
    if window_raw is None:
        return ((None, None, text, words),)
    found = SUBTITLE_WINDOW.match(window_raw[0])
    if not found:
        raise EditError(
            f"{CUT_LIST_NAME}:{window_raw[1]}: {cut_id} 的字幕时间要写成「起-止」秒数"
        )
    return ((float(found.group(1)), float(found.group(2)), text, words),)


def _which(name: str) -> Optional[str]:
    return shutil.which(name)


def _require(name: str) -> str:
    found = _which(name)
    if found is None:
        raise EditError(
            f"PATH 上没有 {name}。本阶段要渲染和测量真实媒体，没有它就没有可报告的事实；"
            "先安装 ffmpeg，不用别的手段近似。"
        )
    return found


def probe_duration(media: Path) -> float:
    probe = _require("ffprobe")
    result = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(media)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise EditError(f"ffprobe 读不出时长: {media} ({result.stderr.strip()})")
    return float(result.stdout.strip())


def probe_stream(media: Path) -> dict[str, Any]:
    probe = _require("ffprobe")
    result = subprocess.run(
        [probe, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate", "-show_entries", "format=duration",
         "-of", "json", str(media)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise EditError(f"ffprobe 读不出流信息: {media} ({result.stderr.strip()})")
    document = json.loads(result.stdout)
    stream = (document.get("streams") or [{}])[0]
    rate = stream.get("r_frame_rate", "0/1")
    numerator, _, denominator = rate.partition("/")
    fps = float(numerator) / float(denominator) if float(denominator or 0) else 0.0
    return {
        "width": stream.get("width"),
        "height": stream.get("height"),
        "fps": round(fps, 3),
        "duration": float(document.get("format", {}).get("duration", 0.0)),
    }


def _unaccounted_shots(known: set[str], cuts: Sequence[Cut], unused: Sequence[str]) -> list[str]:
    """Require each source to be used or explicitly omitted with a reason."""

    used = {cut.motion for cut in cuts}
    excused = set()
    for note in unused:
        match = re.fullmatch(r"(MOTION-[\w-]+)\s*[（(]理由[：:]\s*(.+?)[）)]", note.strip())
        if match and match.group(2).strip():
            excused.add(match.group(1))
    missing = sorted(known - used - excused)
    if not missing:
        return []
    return [
        f"{CUT_LIST_NAME}: 以下镜头未采用，且缺少「未采用镜头」及理由："
        + "、".join(missing)
    ]


def check_cuts(
    episode: Path,
    cuts: Sequence[Cut],
    project_root: Path,
    *,
    probe: bool,
    unused: Sequence[str] = (),
) -> list[str]:
    """Every mechanical cross-check the cut list can be held to. Returns findings."""

    findings: list[str] = []
    if not cuts:
        findings.append(f"{CUT_LIST_NAME}: 没有 CUT 条目")
        return findings

    seen: set[str] = set()
    for cut in cuts:
        if cut.cut_id in seen:
            findings.append(f"{CUT_LIST_NAME}:{cut.line_number}: CUT ID 重复: {cut.cut_id}")
        seen.add(cut.cut_id)

    motion_path = episode / MOTION_DOCUMENT
    if motion_path.is_file():
        known = {
            match.group(1)
            for match in (
                MOTION_HEADING.match(line)
                for line in motion_path.read_text(encoding="utf-8").splitlines()
            )
            if match
        }
        for cut in cuts:
            if cut.motion not in known:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的来源 "
                    f"{cut.motion} 不在《{MOTION_DOCUMENT}》中"
                )
        findings.extend(_unaccounted_shots(known, cuts, unused))
    else:
        findings.append(f"没有 {motion_path}，来源 MOTION 无法核对")

    screenplay = ""
    screenplay_path = episode / SCREENPLAY_DOCUMENT
    if screenplay_path.is_file():
        screenplay = screenplay_path.read_text(encoding="utf-8")

    media_format: Optional[tuple[Any, Any, float]] = None
    for cut in cuts:
        span = cut.end - cut.start
        if cut.start < 0:
            findings.append(f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 入点为负")
        if span <= 0:
            findings.append(
                f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 出点不晚于入点"
            )
        elif abs(span - cut.declared) > TOLERANCE:
            findings.append(
                f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 出点 - 入点 = "
                f"{span:.2f}，与「时长：{cut.declared:.2f}」不符"
            )
        media = _resolve_media(episode, project_root, cut.media)
        if media is None:
            findings.append(
                f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的素材不存在: {cut.media}"
            )
        elif probe:
            stream = probe_stream(media)
            available = stream["duration"]
            current_format = (stream["width"], stream["height"], stream["fps"])
            if media_format is None:
                media_format = current_format
            elif current_format != media_format:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的画幅或帧率 "
                    f"{current_format} 与首段 {media_format} 不一致；"
                    "先在外部统一素材规格，再更新来源路径与入出点"
                )
            if cut.end > available + TOLERANCE:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 出点 {cut.end:.2f} "
                    f"超过素材实际时长 {available:.2f}"
                )
        for window_start, window_end, text, _ in cut.subtitles:
            if screenplay and _normalize(text) not in _normalize(screenplay):
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的字幕在《"
                    f"{SCREENPLAY_DOCUMENT}》里找不到原文: {text}"
                )
            if window_start is None or window_end is None:
                continue
            if not 0 <= window_start < window_end <= span + TOLERANCE:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的字幕时间超出本段区间"
                    f": {window_start}-{window_end}"
                )
        for effect in cut.sound_effects:
            if not 0 <= effect.start < effect.end <= span + TOLERANCE:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的音效时间超出本段区间"
                    f": {effect.start:g}-{effect.end:g}"
                )
            if _resolve_media(episode, project_root, effect.path) is None:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的音效文件不存在: "
                    f"{effect.path}"
                )

    findings.extend(_screen_text_findings(cuts, screenplay))
    findings.extend(_overlap_findings(cuts))
    findings.extend(_stale_window_findings(episode, project_root, cuts))
    return findings


def _screen_text_findings(cuts: Sequence[Cut], screenplay: str) -> list[str]:
    """Screen text is held to 剧本.md's [画面文字] lines, the way subtitles are to dialogue.

    Without a screenplay the check is skipped exactly as the subtitle one is;
    with one, a screenplay that declares no screen text traces nothing.
    """

    findings: list[str] = []
    sources = [_normalize(body) for body in SCREENPLAY_SCREEN_TEXT.findall(screenplay)]
    counting = False
    for cut in cuts:
        span = cut.end - cut.start
        for text in sorted(cut.screen_texts, key=lambda item: item.start):
            where = f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id}"
            if not 0 <= text.start < text.end <= span + TOLERANCE:
                findings.append(
                    f"{where} 的画面文字时间超出本段区间: {text.start:g}-{text.end:g}"
                )
            if screenplay:
                for item in text.items:
                    if not any(_normalize(item) in source for source in sources):
                        findings.append(
                            f"{where} 的画面文字在《{SCREENPLAY_DOCUMENT}》的"
                            f"「[画面文字]」行里找不到: {item}"
                        )
            if text.resume and not counting:
                findings.append(
                    f"{where} 的画面文字写了「倒计时：接续」，但成片里在它之前没有倒计时"
                )
            counting = counting or text.countdown is not None or text.resume
    return findings


def _stale_window_findings(
    episode: Path, project_root: Path, cuts: Sequence[Cut]
) -> list[str]:
    """Material newer than the cut list means the timings were measured on something else.

    Regenerating one shot is routine — the take was hazy, the action was wrong.
    What is easy to forget is that every subtitle window bound to it was reverse-
    engineered from the *old* take's audio. Nothing else notices: the numbers are
    still in range, the render still succeeds, and the subtitle simply appears at
    a moment when nobody is speaking. This is the one form of staleness the file
    system can see, so it is reported rather than trusted to memory.
    """

    listing = episode / CUT_LIST_NAME
    try:
        authored = listing.stat().st_mtime
    except OSError:
        return []
    findings: list[str] = []
    for cut in cuts:
        timed = (
            any(subtitle[0] is not None for subtitle in cut.subtitles)
            or cut.screen_texts
            or cut.sound_effects
        )
        if not timed:
            continue
        media = _resolve_media(episode, project_root, cut.media)
        if media is None:
            continue
        try:
            changed = media.stat().st_mtime
        except OSError:
            continue
        if changed > authored + 1.0:
            findings.append(
                f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的素材比剪辑单新"
                f"（{cut.media}）；这一段的字幕、画面文字与音效时间是按旧素材反推的，"
                "重出之后必须重测再改，不能沿用"
            )
    return findings


def _overlap_findings(cuts: Sequence[Cut]) -> list[str]:
    """Two cuts drawn from one file must not reuse the same frames (EDT-06)."""

    findings: list[str] = []
    by_media: dict[str, list[Cut]] = {}
    for cut in cuts:
        by_media.setdefault(cut.media, []).append(cut)
    for media, group in by_media.items():
        ordered = sorted(group, key=lambda item: item.start)
        for earlier, later in zip(ordered, ordered[1:]):
            if later.start < earlier.end - TOLERANCE:
                findings.append(
                    f"{CUT_LIST_NAME}: {earlier.cut_id} 与 {later.cut_id} 在同一素材 "
                    f"{media} 上区间重叠（{later.start:.2f} < {earlier.end:.2f}）"
                )
    return findings


def _normalize(text: str) -> str:
    """Compare dialogue ignoring punctuation and whitespace, never ignoring characters."""

    return re.sub(r"[\s，。！？、；：…—·\-“”‘’\"'()（）]", "", text)


def _resolve_media(episode: Path, project_root: Path, relative: str) -> Optional[Path]:
    for base in (episode, project_root):
        candidate = (base / relative).resolve()
        if candidate.is_file():
            return candidate
    return None


def render(
    episode: Path,
    project_root: Path,
    cuts: Sequence[Cut],
    delivery: Delivery,
    *,
    burn_subtitles: bool,
    renderer: str = "ffmpeg",
    remotion_workspace: Path = DEFAULT_REMOTION_WORKSPACE,
    remotion_concurrency: int = DEFAULT_REMOTION_CONCURRENCY,
) -> dict[str, Any]:
    ffmpeg = _require("ffmpeg")
    _require("ffprobe")
    output_root = episode / OUTPUT_DIRECTORY
    segments_root = output_root / SEGMENT_DIRECTORY
    segments_root.mkdir(parents=True, exist_ok=True)

    def measure(cut: Cut) -> Optional[ChannelStats]:
        media = _resolve_media(episode, project_root, cut.media)
        return None if media is None else _channel_stats(ffmpeg, media, cut.start, cut.end - cut.start)

    scenes = _scene_keys(episode, cuts)
    pictures, auto = _picture_plan(cuts, scenes, measure, enabled=delivery.shot_match)

    segments: list[Path] = []
    spans: list[float] = []
    for cut, match in zip(cuts, pictures):
        media = _resolve_media(episode, project_root, cut.media)
        if media is None:
            raise EditError(f"{cut.cut_id} 的素材不存在: {cut.media}")
        segment = segments_root / f"{cut.cut_id}.mp4"
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{cut.start:.3f}", "-t", f"{cut.end - cut.start:.3f}", "-i", str(media),
        ]
        if match:
            command += ["-vf", match]
        command += [
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", str(segment),
        ]
        _run(command)
        segments.append(segment)
        spans.append(probe_duration(segment))

    with tempfile.TemporaryDirectory() as scratch:
        listing = Path(scratch) / "segments.txt"
        listing.write_text(
            "".join(f"file '{segment.as_posix()}'\n" for segment in segments), encoding="utf-8"
        )
        joined = output_root / "成片-未混音.mp4"
        _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
              "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)])

        effects: list[tuple[float, float, Path, float]] = []
        for start, duration, written, gain in _placed_sound_effects(cuts, spans):
            resolved = _resolve_media(episode, project_root, written)
            if resolved is None:
                raise EditError(f"音效文件不存在: {written}")
            effects.append((start, duration, resolved, gain))
        if effects:
            # Mixed into its own file first, so the loudness pass below measures
            # the film the audience hears rather than the one before the chimes.
            mixed = output_root / "成片-含音效.mp4"
            _run(_sound_effect_command(ffmpeg, joined, effects, mixed))
            joined = mixed

        filters: list[str] = []
        subtitle_path = None
        styled_path = None
        overlay_path = None
        cues = (
            _display_cues(_subtitle_cues(cuts, spans), _screenplay_text(episode))
            if burn_subtitles and any(cut.subtitles for cut in cuts)
            else []
        )
        layers = _screen_text_layers(cuts, spans)
        canvas = probe_stream(segments[0]) if cues or layers else {}
        if cues:
            subtitle_path = output_root / "字幕.srt"
            subtitle_path.write_text(_build_srt(cues), encoding="utf-8")
        # Screen text has no ffmpeg route: panels, glow and a live countdown are
        # layout, not subtitle styling. So it always goes through the Remotion
        # pass, and on the ffmpeg subtitle route that pass carries no cues.
        remotion_cues = cues if renderer == "remotion" else []
        if remotion_cues or layers:
            overlay_path = _render_remotion_overlay(
                output_root, remotion_cues, layers, canvas, sum(spans), remotion_workspace,
                concurrency=remotion_concurrency,
                needed_for="画面文字" if layers else "字幕",
            )
        if cues and renderer != "remotion":
            styled = styled_path = output_root / "字幕.ass"
            styled.write_text(
                _build_ass(cues, canvas["width"] or 1080, canvas["height"] or 1920),
                encoding="utf-8",
            )
            escaped = (
                str(styled).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
            )
            filters.append(f"ass='{escaped}'")

        # Grain goes on last, over the whole assembled film, so one texture sits
        # across every cut. `t` makes it move frame to frame — static noise reads
        # as dirt on the lens, not as film.
        grain = (
            f"noise=alls={delivery.grain:g}:allf=t+u"
            if delivery.grain is not None
            else None
        )
        if grain is not None:
            filters.append(grain)

        final = output_root / "成片.mp4"
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(joined)]
        if overlay_path is not None:
            # VP8 carries its alpha as WebM block additions, so the decoder has
            # to be named: the default one drops it and the overlay arrives as
            # an opaque black rectangle.
            command += ["-c:v", "libvpx", "-i", str(overlay_path)]
            # ffmpeg-route subtitles and grain follow the composite, so the
            # subtitle sits above the screen text and one grain covers both.
            chain = ",".join(["[0:v][1:v]overlay=0:0:format=auto", *filters])
            command += [
                "-filter_complex",
                f"{chain},format=yuv420p[v]",
                "-map", "[v]", "-map", "0:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            ]
        elif filters:
            command += ["-vf", ",".join(filters), "-c:v", "libx264",
                        "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
        else:
            command += ["-c:v", "copy"]
        if delivery.loudness_lufs is not None:
            command += ["-af", _loudnorm_filter(ffmpeg, joined, delivery.loudness_lufs)]
            command += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        else:
            command += ["-c:a", "copy"]
        command.append(str(final))
        _run(command)

    return {
        "成片": str(final),
        "分段": [str(segment) for segment in segments],
        "字幕": str(subtitle_path) if subtitle_path else None,
        "压制字幕": str(styled_path) if styled_path else None,
        "叠层": str(overlay_path) if overlay_path else None,
        "字幕渲染": renderer if subtitle_path else None,
        "画面文字": len(layers),
        "音效": len(effects),
        "自动接镜": _shot_match_report(auto, scenes, enabled=delivery.shot_match),
        "段数": len(segments),
        "各段时长之和": round(sum(cut.end - cut.start for cut in cuts), 2),
    }


def _shot_match_filter(cut: Cut) -> str:
    """The correction a cut states in 「画面：」. It replaces the automatic match."""

    stages: list[str] = []
    eq = [
        f"{name}={cut.picture[key]}"
        for key, name in (("brightness", "brightness"), ("saturation", "saturation"))
        if key in cut.picture
    ]
    if eq:
        stages.append("eq=" + ":".join(eq))
    warmth = cut.picture.get("warmth")
    if warmth:
        # Positive is warmer: lift red, drop blue, by the same small amount.
        amount = warmth / 100.0
        stages.append(f"colorbalance=rm={amount:.4f}:bm={-amount:.4f}")
    return ",".join(stages)


def _heading_fields(path: Path, heading: re.Pattern[str], field: str) -> dict[str, str]:
    """`{ID: value}` for one `- <field>：` line under each matching `##` heading."""

    if not path.is_file():
        return {}
    found: dict[str, str] = {}
    current: Optional[str] = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = heading.match(raw)
        if match:
            current = match.group(1)
            continue
        if raw.startswith("## "):
            current = None
            continue
        line = FIELD.match(raw)
        if current and line and line.group(1).strip() == field:
            found.setdefault(current, line.group(2).strip())
    return found


def _scene_keys(episode: Path, cuts: Sequence[Cut]) -> list[Optional[tuple[str, ...]]]:
    """Each cut's scene: MOTION → its 分镜 SHOT → the scene IDs that SHOT's 来源 names.

    A shot drawing on two scenes keys on both, so it matches neither neighbour.
    None where the chain breaks; such a cut is never matched.
    """

    shots = _heading_fields(episode / MOTION_DOCUMENT, MOTION_HEADING, "分镜")
    sources = _heading_fields(episode / STORYBOARD_DOCUMENT, SHOT_HEADING, "来源")
    keys: list[Optional[tuple[str, ...]]] = []
    for cut in cuts:
        shot = SHOT_REFERENCE.search(shots.get(cut.motion, ""))
        scenes = tuple(SCENE_ID.findall(sources.get(shot.group(0), ""))) if shot else ()
        keys.append(scenes or None)
    return keys


def _scene_runs(scenes: Sequence[Optional[tuple[str, ...]]]) -> list[list[int]]:
    """Indexes of consecutive cuts from one scene. Intercut scenes form separate runs."""

    runs: list[list[int]] = []
    for index, scene in enumerate(scenes):
        if scene is None:
            continue
        if runs and scenes[index - 1] == scene:
            runs[-1].append(index)
        else:
            runs.append([index])
    return runs


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _match_toward(
    stats: ChannelStats, reference: ChannelStats, strength: float = SHOT_MATCH_STRENGTH
) -> ShotMatch:
    """Gain and offset per channel moving mean and spread `strength` of the way to `reference`."""

    low, high = SHOT_MATCH_GAIN_LIMITS
    gains: list[float] = []
    offsets: list[float] = []
    for mean, spread, target_mean, target_spread in zip(
        stats.mean, stats.spread, reference.mean, reference.spread
    ):
        mean_to = mean + strength * (target_mean - mean)
        spread_to = spread + strength * (target_spread - spread)
        gain = min(high, max(low, spread_to / spread)) if spread > 1e-6 else 1.0
        gains.append(gain)
        offsets.append(mean_to - gain * mean)
    return ShotMatch(tuple(gains), tuple(offsets))


def _plan_shot_match(
    cuts: Sequence[Cut],
    scenes: Sequence[Optional[tuple[str, ...]]],
    measure: Callable[[Cut], Optional[ChannelStats]],
    strength: float = SHOT_MATCH_STRENGTH,
) -> dict[str, ShotMatch]:
    """The automatic match for every cut it applies to, by CUT ID.

    Within each run of one scene, the cuts that state no correction are pulled
    toward the median of those same cuts. A cut with 「画面：<校正>」 or
    「画面：不校」 is neither corrected nor counted in the median. `measure(cut)`
    returns ChannelStats, or None when the clip cannot be read.
    """

    plan: dict[str, ShotMatch] = {}
    for run in _scene_runs(scenes):
        eligible = [cuts[i] for i in run if not cuts[i].picture and not cuts[i].untouched]
        measured = [(cut, measure(cut)) for cut in eligible] if len(eligible) > 1 else []
        known = [(cut, stats) for cut, stats in measured if stats is not None]
        if len(known) < 2:
            continue
        reference = ChannelStats(
            tuple(_median([stats.mean[c] for _, stats in known]) for c in range(3)),
            tuple(_median([stats.spread[c] for _, stats in known]) for c in range(3)),
        )
        for cut, stats in known:
            plan[cut.cut_id] = _match_toward(stats, reference, strength)
    return plan


def _auto_match_filter(match: ShotMatch) -> str:
    """One `lutrgb` stage; the lookup clips to 0-255 itself."""

    return "lutrgb=" + ":".join(
        f"{channel}='val*{gain:.4f}{offset:+.3f}'"
        for channel, gain, offset in zip("rgb", match.gains, match.offsets)
    )


def _picture_plan(
    cuts: Sequence[Cut],
    scenes: Sequence[Optional[tuple[str, ...]]],
    measure: Callable[[Cut], Optional[ChannelStats]],
    *,
    enabled: bool,
) -> tuple[list[str], dict[str, ShotMatch]]:
    """Each cut's picture filter: its stated correction, else the automatic match, else none."""

    auto = _plan_shot_match(cuts, scenes, measure) if enabled else {}
    filters = [
        _shot_match_filter(cut) if cut.picture
        else _auto_match_filter(auto[cut.cut_id]) if cut.cut_id in auto
        else ""
        for cut in cuts
    ]
    return filters, auto


def _shot_match_report(
    auto: dict[str, ShotMatch], scenes: Sequence[Optional[tuple[str, ...]]], *, enabled: bool
) -> Any:
    """What the automatic match did, so the correction is on the record."""

    if not enabled:
        return "关（剪辑单写了「接镜匹配：无」）"
    if not any(scenes):
        return f"未执行（按《{MOTION_DOCUMENT}》与《{STORYBOARD_DOCUMENT}》找不到各段所属场景）"
    return {
        cut_id: {
            "增益": [round(gain, 3) for gain in match.gains],
            "偏移": [round(offset, 1) for offset in match.offsets],
        }
        for cut_id, match in auto.items()
    }


def _channel_stats(
    ffmpeg: str, media: Path, start: float, duration: float
) -> Optional[ChannelStats]:
    """Per-channel mean and spread of one cut's source range, sampled small."""

    result = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
         "-i", str(media), "-vf", SHOT_MATCH_SAMPLE,
         "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
        capture_output=True, check=False,
    )
    if result.returncode != 0 or len(result.stdout) < 3:
        return None
    return _rgb_stats(result.stdout)


def _rgb_stats(raw: bytes) -> ChannelStats:
    means: list[float] = []
    spreads: list[float] = []
    for channel in range(3):
        values = raw[channel::3]
        count = len(values)
        mean = sum(values) / count
        square = sum(map(operator.mul, values, values)) / count
        means.append(mean)
        spreads.append(max(0.0, square - mean * mean) ** 0.5)
    return ChannelStats(tuple(means), tuple(spreads))


def _loudnorm_filter(ffmpeg: str, media: Path, target: float) -> str:
    """Measure EBU R128 before normalization; verify the encoded output afterward.

    FFmpeg can fall back to dynamic processing when linear gain would exceed
    the peak or loudness-range target. Two passes do not guarantee target LUFS.
    """

    common = f"I={target}:TP=-1.5:LRA=11"
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", str(media),
         "-af", f"loudnorm={common}:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    measured = _last_json_object(result.stderr)
    required = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    if not measured or not all(key in measured for key in required):
        # Say so rather than silently delivering a single-pass approximation.
        raise EditError(
            "loudnorm 第一遍没有返回可用的测量结果，无法做两遍响度标准化；"
            "检查成片音轨是否为空"
        )
    return (
        f"loudnorm={common}:measured_I={measured['input_i']}"
        f":measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}"
        f":measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}:linear=true:print_format=summary"
    )


def _sync_remotion_workspace(workspace: Path) -> Path:
    """Copy the shipped composition into a runnable workspace outside the project.

    Editing the composition means editing the skill's own source; the workspace
    is a build directory that is rewritten on every run, so a change here can
    never be quietly lost, and `node_modules` never lands inside the repository.
    """

    workspace = workspace.expanduser().resolve()
    for name in REMOTION_SOURCE_FILES:
        source = REMOTION_SOURCE / name
        if not source.is_file():
            raise EditError(f"技能里缺少 Remotion 源文件: {name}")
        (workspace / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, workspace / name)
    return workspace


def _overlay_props(
    cues: Sequence[DisplayCue],
    layers: Sequence[dict[str, Any]],
    canvas: dict[str, Any],
    duration: float,
) -> dict[str, Any]:
    """The whole contract with the composition, in output seconds.

    Typography -- faces, sizes, colours -- is the composition's own; only what
    to draw and when crosses this boundary.
    """

    return {
        "cues": [
            {"start": round(cue.start, 3), "end": round(cue.end, 3), "text": cue.text,
             "kind": cue.kind, "keys": list(cue.keys)}
            for cue in cues
        ],
        "screenTexts": [
            {
                **layer,
                "start": round(layer["start"], 3),
                "end": round(layer["end"], 3),
                "countdown": (
                    None if layer["countdown"] is None else round(layer["countdown"], 3)
                ),
            }
            for layer in layers
        ],
        "width": canvas.get("width") or 1080,
        "height": canvas.get("height") or 1920,
        "fps": canvas.get("fps") or 24,
        "durationInSeconds": round(duration, 3),
    }


def _missing_remotion_packages(workspace: Path) -> list[str]:
    """Dependencies the synced package.json names that the workspace has not installed.

    The fonts are packages too: a workspace installed before they were added
    has `node_modules` but no faces, and the bundle would fail halfway in.
    """

    manifest = json.loads((workspace / "package.json").read_text(encoding="utf-8"))
    return sorted(
        name for name in manifest.get("dependencies", {})
        if not (workspace / "node_modules" / name / "package.json").is_file()
    )


def _render_remotion_overlay(
    output_root: Path,
    cues: Sequence[DisplayCue],
    layers: Sequence[dict[str, Any]],
    canvas: dict[str, Any],
    duration: float,
    workspace_root: Path,
    concurrency: int = DEFAULT_REMOTION_CONCURRENCY,
    needed_for: str = "字幕",
) -> Path:
    """Render subtitles and screen text as one transparent video with Remotion.

    The picture is never re-drawn by the browser: only the type is, onto an
    empty frame, and ffmpeg composites that over untouched footage. So the
    route costs one overlay pass and buys real typography — weight, rim, safe
    area, wrapping and an entry animation — expressed once in CSS instead of in
    a subtitle format whose own scaling has to be reasoned about.

    Remotion is a separate project with its own licence: free for individuals
    and small companies, paid above that. It is opt-in for exactly that reason,
    and nothing installs it behind the creator's back.
    """

    workspace = _sync_remotion_workspace(workspace_root)
    # Screen text has no other route, so the way out named here depends on why
    # the pass is running: dropping a flag cannot draw a system panel.
    alternative = (
        "剪辑单里有画面文字，它只能由这条路线绘制；不装就把画面文字行删掉或写「无」。"
        if needed_for == "画面文字"
        else "或改用默认的 ffmpeg 字幕（去掉 --subtitles remotion）。"
    )
    missing = _missing_remotion_packages(workspace)
    if missing:
        raise EditError(
            f"Remotion 叠层的依赖没装全（缺 {'、'.join(missing)}），{needed_for}需要它们。先运行一次：\n"
            f"  cd {workspace} && npm install\n"
            f"{alternative}\n"
            "注意 Remotion 有自己的许可证：个人与小团队免费，超出规模需要商业授权；"
            "本工具不会替你安装它。"
        )
    npx = _which("npx")
    if npx is None:
        raise EditError(
            f"PATH 上没有 npx，无法运行 Remotion 绘制{needed_for}；先装好 Node.js。{alternative}"
        )
    props = output_root / "叠层.props.json"
    props.write_text(
        json.dumps(_overlay_props(cues, layers, canvas, duration), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    overlay = output_root / "叠层.webm"
    result = subprocess.run(
        [npx, "remotion", "render", REMOTION_COMPOSITION, str(overlay),
         f"--props={props}", "--log=error",
         f"--concurrency={max(1, concurrency)}"],
        cwd=str(workspace), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0 or not overlay.is_file():
        raise EditError(
            "Remotion 渲染失败：\n" + (result.stderr or result.stdout or "").strip()[-2000:]
        )
    return overlay


def _frame_geometry(media: Path) -> str:
    stream = probe_stream(media)
    return f"{stream['width']}x{stream['height']}"


def _subtitle_cues(
    cuts: Sequence[Cut], spans: Sequence[float]
) -> list[tuple[float, float, str, tuple[str, ...]]]:
    """Place each line in output time, measuring the segments that were written.

    A segment lands on a frame boundary, so it is a few milliseconds longer than
    the cut list declares. Accumulating the declared numbers instead drifts —
    a third of a second by the end of eight cuts here — and the subtitle leaves
    before the actor stops speaking. The rendered files are the timeline.
    """

    cues: list[tuple[float, float, str, tuple[str, ...]]] = []
    for cut, cursor, scale in _timeline(cuts, spans):
        declared = cut.end - cut.start
        for window_start, window_end, text, words in cut.subtitles:
            start = 0.0 if window_start is None else window_start
            end = declared if window_end is None else window_end
            cues.append((cursor + start * scale, cursor + end * scale, text, words))
    return cues


def _timeline(
    cuts: Sequence[Cut], spans: Sequence[float]
) -> list[tuple[Cut, float, float]]:
    """Each cut with its output start and the factor from declared to rendered time.

    Windows were authored against the declared span; scaling holds them in
    place proportionally rather than letting the tail slip out.
    """

    placed: list[tuple[Cut, float, float]] = []
    cursor = 0.0
    for cut, span in zip(cuts, spans):
        declared = cut.end - cut.start
        placed.append((cut, cursor, span / declared if declared > 0 else 1.0))
        cursor += span
    return placed


class DisplayCue(NamedTuple):
    """One subtitle as burned: output seconds, display text, speaker kind, highlights."""

    start: float
    end: float
    text: str
    kind: str = "line"
    keys: tuple[str, ...] = ()


def _display_line(text: str) -> str:
    """The burned form of a line: no closing punctuation, pauses as full-width spaces."""

    shown = text.strip().rstrip(SUBTITLE_END_MARKS + " 　")
    shown = re.sub(f"[{SUBTITLE_PAUSE_MARKS}]+[ 　]*", "　", shown)
    return re.sub(r"[ 　]{2,}", "　", shown).strip(" 　")


def _visible(text: str) -> int:
    return len(re.sub(r"[ 　]", "", text))


def _split_display(text: str, limit: int = SUBTITLE_MAX_VISIBLE) -> list[str]:
    """Break a displayed line into one-line pieces of at most `limit` characters.

    Pieces break at the line's own pauses (the full-width spaces, and after ？！)
    and are packed back together while they fit. A single phrase longer than
    the limit is cut into near-equal parts, which is the only place a break
    falls where the screenplay has no pause.
    """

    if _visible(text) <= limit:
        return [text]
    phrases = [
        phrase
        for part in text.split("　")
        for phrase in re.findall(r"[^？！?!]+[？！?!]*|[？！?!]+", part)
    ]
    pieces: list[str] = []
    for phrase in phrases:
        count = _visible(phrase)
        if count > limit:
            parts = -(-count // limit)
            size = -(-count // parts)
            pieces.extend(phrase[i:i + size] for i in range(0, len(phrase), size))
        else:
            pieces.append(phrase)
    packed: list[str] = []
    for piece in pieces:
        if packed and _visible(packed[-1]) + _visible(piece) <= limit:
            joiner = "" if packed[-1][-1] in "？！?!" else "　"
            packed[-1] = packed[-1] + joiner + piece
        else:
            packed.append(piece)
    return packed


def _screenplay_text(episode: Path) -> str:
    path = episode / SCREENPLAY_DOCUMENT
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _line_kind(text: str, screenplay: str) -> str:
    """`system`, `vo` or `line`, from the 剧本.md line the subtitle quotes."""

    needle = _normalize(text)
    for raw in screenplay.splitlines():
        spoken = SPOKEN_LINE.match(raw)
        if not spoken or needle not in _normalize(spoken.group(3)):
            continue
        if spoken.group(1) == "VO":
            return "system" if SYSTEM_SPEAKER in spoken.group(2) else "vo"
        return "line"
    return "line"


def _display_cues(
    cues: Sequence[tuple[float, float, str, tuple[str, ...]]],
    screenplay: str = "",
) -> list[DisplayCue]:
    """Turn placed lines into what is burned: display text, split, coloured by speaker.

    A split line shares its window by character count, so each piece stays up
    about as long as it takes to read.
    """

    shown: list[DisplayCue] = []
    for start, end, text, words in cues:
        kind = _line_kind(text, screenplay)
        pieces = _split_display(_display_line(text))
        # A line that is all punctuation ("……") has nothing left to show.
        pieces = [piece for piece in pieces if _visible(piece)]
        total = sum(_visible(piece) for piece in pieces)
        cursor = start
        for piece in pieces:
            length = (end - start) * _visible(piece) / total
            keys = tuple(word for word in words if word in piece)
            shown.append(DisplayCue(cursor, cursor + length, piece, kind, keys))
            cursor += length
    return shown


def _screen_text_layers(
    cuts: Sequence[Cut], spans: Sequence[float]
) -> list[dict[str, Any]]:
    """Place screen text in output time and resolve every countdown to a number.

    「接续」 continues the latest earlier countdown: its value here is that one's
    value minus the output time between them, so a chip picks up exactly where
    the task panel left off however long the cuts in between came out. A piece
    that meets an identical piece at a cut is extended instead of re-entering.
    """

    layers: list[dict[str, Any]] = []
    latest: Optional[dict[str, Any]] = None
    for cut, cursor, scale in _timeline(cuts, spans):
        for text in sorted(cut.screen_texts, key=lambda item: item.start):
            start = cursor + text.start * scale
            end = cursor + text.end * scale
            countdown = text.countdown
            if text.resume:
                if latest is None:
                    raise EditError(
                        f"{cut.cut_id} 的画面文字写了「倒计时：接续」，但在它之前没有倒计时"
                    )
                countdown = latest["countdown"] - (start - latest["start"])
            style = SCREEN_TEXT_STYLES[text.style]
            items = [
                {"text": item, "rarity": rarity}
                for item, rarity in zip(text.items, text.rarities or (None,) * len(text.items))
            ]
            previous = next((layer for layer in reversed(layers) if layer["style"] == style), None)
            if (
                previous is not None
                and previous["items"] == items
                and abs(previous["end"] - start) <= SCREEN_TEXT_JOIN_GAP
                and (
                    (text.resume and previous is latest)
                    or (countdown is None and previous["countdown"] is None)
                )
            ):
                previous["end"] = end
                continue
            layer = {
                "start": start,
                "end": end,
                "style": style,
                "items": items,
                "countdown": countdown,
            }
            layers.append(layer)
            if countdown is not None:
                latest = layer
    return layers


def _placed_sound_effects(
    cuts: Sequence[Cut], spans: Sequence[float]
) -> list[tuple[float, float, str, float]]:
    """Each effect as (output start, duration, path as written, gain dB)."""

    return [
        (cursor + effect.start * scale, (effect.end - effect.start) * scale,
         effect.path, effect.gain_db)
        for cut, cursor, scale in _timeline(cuts, spans)
        for effect in cut.sound_effects
    ]


def _sound_effect_command(
    ffmpeg: str,
    film: Path,
    effects: Sequence[tuple[float, float, Path, float]],
    output: Path,
) -> list[str]:
    """Lay each effect into the film's own audio at its output time.

    `normalize=0` keeps the dialogue at its level: amix's default divides every
    input by the input count, and the film would get quieter each time a chime
    is added. A short fade closes each effect so a trimmed tail does not click.
    """

    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(film)]
    # The film's channel layout is left as it is: forcing mono dialogue up to
    # stereo costs it 3 dB, and the effects are converted to match instead.
    stages = ["[0:a]aformat=sample_rates=48000[a0]"]
    labels = ["[a0]"]
    for index, (start, duration, media, gain) in enumerate(effects, start=1):
        command += ["-i", str(media)]
        fade = min(0.05, duration / 2)
        stages.append(
            f"[{index}:a]atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=out:st={duration - fade:.3f}:d={fade:.3f},volume={gain:g}dB,"
            "aformat=sample_rates=48000,"
            f"adelay={round(start * 1000)}:all=1[s{index}]"
        )
        labels.append(f"[s{index}]")
    stages.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:"
        "dropout_transition=0:normalize=0[a]"
    )
    return command + [
        "-filter_complex", ";".join(stages),
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(output),
    ]


def _build_srt(cues: Sequence[DisplayCue]) -> str:
    """The screenplay's words in their burned form; only the timing is ours."""

    return "\n".join(
        f"{index}\n{_timecode(cue.start)} --> {_timecode(cue.end)}\n{cue.text}\n"
        for index, cue in enumerate(cues, start=1)
    )


def _ass_colour(hex_rgb: str) -> str:
    """`#RRGGBB` as ASS writes it: blue, green, red."""

    red, green, blue = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H00{blue}{green}{red}&".upper()


def _ass_line(cue: DisplayCue) -> str:
    """Escaped text with the speaker's colour and the highlighted words in yellow."""

    base = _ass_colour(SUBTITLE_COLOURS[cue.kind])
    marked = "{\\c" + base + "}" if cue.kind != "line" else ""
    rest = cue.text
    while rest:
        hits = [(rest.find(word), word) for word in cue.keys if word in rest]
        if not hits:
            marked += _ass_text(rest)
            break
        at, word = min(hits)
        marked += _ass_text(rest[:at])
        marked += "{\\c" + _ass_colour(SUBTITLE_KEYWORD_COLOUR) + "}" + _ass_text(word)
        marked += "{\\c" + base + "}"
        rest = rest[at + len(word):]
    return marked


def _build_ass(cues: Sequence[DisplayCue], width: int, height: int) -> str:
    """Author the ASS directly so the type size is stated in frame pixels.

    Letting ffmpeg convert the SRT hands libass a 384-high canvas, and every
    size in the style is then scaled by height/384 on the way to the frame.
    Computing a FontSize from the real height on top of that scales it twice:
    the first attempt here produced type a third of the frame wide, sitting in
    the middle of the picture with both ends of the line cut off. Declaring
    PlayRes as the frame removes the conversion, so one unit is one pixel.
    """

    # The same measures as the Remotion layer: type 4.3% of frame height, a
    # 0.42% dark rim, and the baseline 24% up, clear of the platform's own UI.
    font_size = max(18, round(height * 0.043))
    outline = max(2, round(height * 0.0042))
    margin_v = max(24, round(height * 0.24))
    margin_h = max(24, round(width * 0.06))
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: 正片,{SUBTITLE_FONT},{font_size},&H00FFFFFF,&H00FFFFFF,"
        f"&H00120D0B,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},1,2,"
        f"{margin_h},{margin_h},{margin_v},1\n"
        "\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    lines = [
        f"Dialogue: 0,{_ass_time(cue.start)},{_ass_time(cue.end)},正片,,0,0,0,,{_ass_line(cue)}"
        for cue in cues
    ]
    return header + "\n".join(lines) + "\n"


def _ass_text(text: str) -> str:
    """Escape a line so ASS renders its characters instead of reading them.

    `{`…`}` is an override block in ASS and `\\` starts an escape, so a quoted
    line that happens to contain either would lose characters on screen with no
    error anywhere — and EDT-05 exists precisely to keep the burned text equal
    to the screenplay's, character for character.
    """

    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def _ass_time(seconds: float) -> str:
    hundredths = int(round(seconds * 100))
    hours, hundredths = divmod(hundredths, 360000)
    minutes, hundredths = divmod(hundredths, 6000)
    whole, hundredths = divmod(hundredths, 100)
    return f"{hours:d}:{minutes:02d}:{whole:02d}.{hundredths:02d}"


def _timecode(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole:02d},{milliseconds:03d}"


def _segment_colour(ffmpeg: str, path: Path) -> Optional[tuple[float, float]]:
    """Mean luma and blue-red difference of one segment, on a 0-255 scale."""

    result = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-vf", "fps=2,scale=96:-1",
         "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
        capture_output=True,
    )
    raw = result.stdout
    if result.returncode != 0 or len(raw) < 3:
        return None
    count = len(raw) // 3
    red = sum(raw[i * 3] for i in range(count)) / count
    green = sum(raw[i * 3 + 1] for i in range(count)) / count
    blue = sum(raw[i * 3 + 2] for i in range(count)) / count
    return 0.299 * red + 0.587 * green + 0.114 * blue, blue - red


def _segment_colours(ffmpeg: str, output_root: Path, cuts: Sequence[Cut]) -> list[dict[str, Any]]:
    """Report current cut segments individually, without imposing a shared grade."""

    rows: list[dict[str, Any]] = []
    for cut in cuts:
        path = output_root / SEGMENT_DIRECTORY / f"{cut.cut_id}.mp4"
        colour = _segment_colour(ffmpeg, path) if path.is_file() else None
        row: dict[str, Any] = {"分段": path.name}
        if colour is None:
            row["测量"] = "未测（分段缺失或不可读）"
        else:
            row.update({"平均亮度": round(colour[0], 1), "蓝减红": round(colour[1], 1)})
        rows.append(row)
    return rows


def verify(episode: Path, cuts: Sequence[Cut], delivery: Delivery) -> dict[str, Any]:
    """Measure the rendered film. Every entry is a number or an honest 未测."""

    ffmpeg = _require("ffmpeg")
    final = episode / OUTPUT_DIRECTORY / "成片.mp4"
    if not final.is_file():
        raise EditError(f"没有 {final}；先运行 render")
    stream = probe_stream(final)
    expected = sum(cut.end - cut.start for cut in cuts)
    measurements: dict[str, Any] = {
        "成片": str(final),
        "实测时长": round(stream["duration"], 2),
        "各段时长之和": round(expected, 2),
        "时长差": round(stream["duration"] - expected, 2),
        "画幅": f"{stream['width']}×{stream['height']}",
        "画幅是否等于交付规格": _matches_frame_size(delivery, stream),
        "帧率": stream["fps"],
        "帧率是否等于交付规格": _matches_fps(delivery, stream),
        "目标时长": delivery.target_seconds,
        "与目标时长的差": (
            round(stream["duration"] - delivery.target_seconds, 2)
            if delivery.target_seconds is not None
            else "未测（剪辑单没有声明目标时长）"
        ),
    }
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", str(final),
         "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    measured = _last_json_object(result.stderr)
    if measured and "input_i" in measured:
        measurements["实测响度 LUFS"] = float(measured["input_i"])
        measurements["实测真峰 dBTP"] = float(measured["input_tp"])
    else:
        measurements["实测响度 LUFS"] = "未测（loudnorm 没有返回可解析的测量结果）"
    measurements["交付响度目标"] = delivery.loudness_lufs
    measurements["分段色彩观测"] = _segment_colours(ffmpeg, episode / OUTPUT_DIRECTORY, cuts)
    measurements["画内可读文字"] = (
        "未测（抽有画内文字的帧，逐字对《剧本.md》的「画面文字」与提示词声明的内容）"
    )
    segments = [episode / OUTPUT_DIRECTORY / SEGMENT_DIRECTORY / f"{cut.cut_id}.mp4" for cut in cuts]
    spans = (
        [probe_duration(segment) for segment in segments]
        if all(segment.is_file() for segment in segments)
        else None
    )
    if any(cut.screen_texts or cut.sound_effects for cut in cuts):
        measurements.update(_placements_for_sampling(cuts, spans))
    measurements["台词完整性"] = "未测（本工具不做转写；在成片上转写后逐句对《剧本.md》原文）"
    measurements.update(_frame_report(
        _grey_frames(ffmpeg, final), stream["fps"], cuts, spans, _scene_keys(episode, cuts)
    ))
    measurements["边界帧"] = "未测（抽剪辑点前后各一帧目视核对黑场/白场/半渲染帧）"
    return measurements


def _grey_frames(ffmpeg: str, media: Path) -> Optional[list[bytes]]:
    """Every frame of the film, grey, at FRAME_PROBE_SIZE."""

    width, height = FRAME_PROBE_SIZE
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(media), "-vf", f"scale={width}:{height},format=gray",
         "-f", "rawvideo", "-"],
        capture_output=True, check=False,
    )
    size = width * height
    if result.returncode != 0 or len(result.stdout) < size:
        return None
    raw = result.stdout
    return [raw[at:at + size] for at in range(0, len(raw) - size + 1, size)]


def _mean_difference(first: bytes, second: bytes) -> float:
    return sum(map(abs, map(operator.sub, first, second))) / len(first)


def _suspect_frames(frames: Sequence[bytes]) -> list[tuple[int, float, float, float]]:
    """Frames unlike both neighbours while the neighbours are alike: (index, prev, next, across).

    A hard cut differs from one side only; fast motion differs from both, but
    its neighbours differ from each other even more.
    """

    steps = [_mean_difference(a, b) for a, b in zip(frames, frames[1:])]
    suspects: list[tuple[int, float, float, float]] = []
    for index in range(1, len(frames) - 1):
        before, after = steps[index - 1], steps[index]
        if min(before, after) <= FLASH_FRAME_DIFFERENCE:
            continue
        across = _mean_difference(frames[index - 1], frames[index + 1])
        if across < FLASH_NEIGHBOUR_SHARE * min(before, after):
            suspects.append((index, before, after, across))
    return suspects


def _cut_jumps(
    means: Sequence[float],
    fps: float,
    cuts: Sequence[Cut],
    spans: Sequence[float],
    scenes: Sequence[Optional[tuple[str, ...]]],
) -> list[dict[str, Any]]:
    """Mean-luma change from the last frame before each cut to the first after it."""

    rows: list[dict[str, Any]] = []
    cursor = 0.0
    for index in range(1, len(cuts)):
        cursor += spans[index - 1]
        frame = round(cursor * fps)
        if not 0 < frame < len(means):
            continue
        before, after = scenes[index - 1], scenes[index]
        rows.append({
            "切点秒": round(cursor, 2),
            "前段": cuts[index - 1].cut_id,
            "后段": cuts[index].cut_id,
            "亮度变化": round(means[frame] - means[frame - 1], 1),
            "场景": "未知" if before is None or after is None
            else "同场" if before == after else "换场",
        })
    return rows


def _frame_report(
    frames: Optional[Sequence[bytes]],
    fps: float,
    cuts: Sequence[Cut],
    spans: Optional[Sequence[float]],
    scenes: Sequence[Optional[tuple[str, ...]]],
) -> dict[str, Any]:
    """Luma jumps at cuts and suspect frames, with what to look at. Nothing here blocks."""

    if frames is None or not fps:
        reason = "未测（读不出成片的逐帧画面）"
        return {"切点亮度变化": reason, "疑似坏帧": reason}
    notes: list[str] = []
    report: dict[str, Any] = {}
    if spans is None:
        report["切点亮度变化"] = "未测（分段缺失，无法换算切点时间）"
        entrances: list[float] = []
    else:
        jumps = _cut_jumps([sum(frame) / len(frame) for frame in frames], fps, cuts, spans, scenes)
        report["切点亮度变化"] = jumps
        notes.extend(
            f"{row['切点秒']:.2f} 秒 {row['前段']} → {row['后段']}（{row['场景']}）亮度变化 "
            f"{row['亮度变化']:+.1f}：看是否像闪了一下"
            for row in jumps if abs(row["亮度变化"]) > CUT_JUMP_NOTICE
        )
        entrances = [layer["start"] for layer in _screen_text_layers(cuts, spans)]
    suspects = []
    for index, before, after, across in _suspect_frames(frames):
        seconds = index / fps
        entering = any(0 <= seconds - start <= SCREEN_TEXT_ENTRANCE for start in entrances)
        suspects.append({
            "秒": round(seconds, 3), "帧": index,
            "与前帧差": round(before, 1), "与后帧差": round(after, 1), "前后帧互差": round(across, 1),
            "画面文字入场": entering,
        })
        notes.append(
            f"{seconds:.3f} 秒（第 {index} 帧）与前后两帧都不像："
            + ("画面文字正在入场，确认是入场效果" if entering else "逐帧看是否有错位或串入别的画面")
        )
    report["疑似坏帧"] = suspects
    report["请逐帧查看"] = notes
    return report


def _placements_for_sampling(cuts: Sequence[Cut], spans: Optional[Sequence[float]]) -> dict[str, Any]:
    """Where the screen text and effects landed in the film, from the rendered segments.

    These are the frames and moments to sample; whether the text reads and the
    chime sits right is still for someone to look and listen.
    """

    if spans is None:
        reason = "未测（分段缺失，无法换算成片时间）"
        return {"画面文字落点": reason, "音效落点": reason}
    return {
        "画面文字落点": [
            {
                "起": round(layer["start"], 2),
                "止": round(layer["end"], 2),
                "样式": next(
                    label for label, key in SCREEN_TEXT_STYLES.items() if key == layer["style"]
                ),
                "文字": SCREEN_TEXT_ITEM_SEPARATOR.join(item["text"] for item in layer["items"]),
            }
            for layer in _screen_text_layers(cuts, spans)
        ],
        "音效落点": [
            {"起": round(start, 2), "止": round(start + duration, 2), "文件": written}
            for start, duration, written, _ in _placed_sound_effects(cuts, spans)
        ],
    }


def _matches_frame_size(delivery: Delivery, stream: dict[str, Any]) -> Any:
    if delivery.frame_size is None:
        return "未测（剪辑单没有声明画幅）"
    return (stream["width"], stream["height"]) == delivery.frame_size


def _matches_fps(delivery: Delivery, stream: dict[str, Any]) -> Any:
    if delivery.fps is None:
        return "未测（剪辑单没有声明帧率）"
    return abs(stream["fps"] - delivery.fps) < 0.05


def _last_json_object(text: str) -> Optional[dict[str, Any]]:
    """ffmpeg prints its own tail after the loudnorm block, so decode a prefix."""

    decoder = json.JSONDecoder()
    start = text.rfind("{")
    while start != -1:
        try:
            document, _ = decoder.raw_decode(text[start:].lstrip())
        except json.JSONDecodeError:
            start = text.rfind("{", 0, start)
            continue
        if isinstance(document, dict):
            return document
        start = text.rfind("{", 0, start)
    return None


def _run(command: Sequence[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise EditError(f"命令失败: {' '.join(command[:6])}…\n{result.stderr.strip()}")


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="短剧剪辑：核对剪辑单、渲染成片、测量成片")
    parser.add_argument("command", choices=("check", "render", "verify"))
    parser.add_argument("episode", help="剧集/<EP> 目录")
    parser.add_argument("--project-root", default=".", help="项目根目录（解析素材相对路径）")
    parser.add_argument("--no-subtitles", action="store_true", help="render 时不烧字幕")
    parser.add_argument(
        "--subtitles", choices=SUBTITLE_RENDERERS, default="ffmpeg",
        help="字幕渲染方式：ffmpeg（默认，无外部依赖）或 remotion（需先安装，排版更好）",
    )
    parser.add_argument(
        "--remotion-workspace", type=Path, default=DEFAULT_REMOTION_WORKSPACE,
        help=f"Remotion 运行工作区（默认 {DEFAULT_REMOTION_WORKSPACE}），必须在项目之外",
    )
    parser.add_argument(
        "--remotion-concurrency", type=int, default=DEFAULT_REMOTION_CONCURRENCY,
        help=(
            f"Remotion 的并发无头浏览器数（默认 {DEFAULT_REMOTION_CONCURRENCY}）。"
            "每个都持有一整帧，调高很容易把内存吃满"
        ),
    )
    arguments = parser.parse_args(argv)

    episode = Path(arguments.episode).resolve()
    project_root = Path(arguments.project_root).resolve()
    try:
        delivery, cuts, unused = parse_cut_list(episode / CUT_LIST_NAME)
        if arguments.command == "check":
            findings = check_cuts(
                episode, cuts, project_root,
                probe=_which("ffprobe") is not None, unused=unused,
            )
            payload: dict[str, Any] = {
                "段数": len(cuts),
                "各段时长之和": round(sum(cut.end - cut.start for cut in cuts), 2),
                "目标时长": delivery.target_seconds,
                "未采用镜头": unused,
                "findings": findings,
            }
            if _which("ffprobe") is None:
                payload["未测"] = ["区间是否超过素材实际时长（PATH 上没有 ffprobe）"]
            _emit(payload)
            return 1 if findings else 0
        if arguments.command == "render":
            findings = check_cuts(
                episode, cuts, project_root, probe=True, unused=unused
            )
            if findings:
                _emit({"findings": findings, "已渲染": False})
                return 1
            _emit(render(
                episode, project_root, cuts, delivery,
                burn_subtitles=delivery.burn_subtitles and not arguments.no_subtitles,
                renderer=arguments.subtitles,
                remotion_workspace=arguments.remotion_workspace,
                remotion_concurrency=arguments.remotion_concurrency,
            ))
            return 0
        _emit(verify(episode, cuts, delivery))
        return 0
    except EditError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
