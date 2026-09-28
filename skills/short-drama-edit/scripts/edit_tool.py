#!/usr/bin/env python3
"""Assemble a short-drama episode from its cut list.

Three subcommands, deliberately separated so a report can never borrow one's
evidence for another's claim:

``check``   parse and cross-check ``剪辑单.md`` against the project. No rendering.
``render``  cut video and draw stills, join, mix sound effects and voice lines,
            burn subtitles and screen text, and normalize loudness into
            制作成果/成片/.
``verify``  measure an already-rendered film and print the numbers.

``verify`` prints measurements, never verdicts. Whether the film is any good is
a question for review or for the creator, and no number here answers it.
"""

from __future__ import annotations

import argparse
from array import array
import json
import operator
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable, NamedTuple, Optional, Sequence, Union

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
# alike; a plain slash would collide with the path itself. A still cut -- the
# static 漫剧 route, keyframes and voiceover -- names the storyboard shot or the
# image prompt its picture answers to instead.
SOURCE = re.compile(r"^((?:MOTION|SHOT|IMG)-\S+)\s*·\s*(.+?)\s*$")
IMAGE_DOCUMENT = "图片提示词.md"
IMAGE_HEADING = re.compile(r"^##\s+(IMG-[^\s·]+)")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
# A still holds the screen for as long as it is written to; shorter than this
# it reads as a flash frame rather than a shot.
STILL_MINIMUM = 0.50
# 「运镜：推近 8%」 moves the frame across a still. Past 30% the picture is
# being re-framed, not moved, and the upscale starts to show.
CAMERA_MOVES = ("推近", "拉远", "左移", "右移", "上移", "下移")
CAMERA_MOVE = re.compile(r"^(" + "|".join(CAMERA_MOVES) + r")\s*([0-9]+)\s*[%％]$")
# 「推近 2.5%/秒」: a speed rather than a distance, so a scene's cuts can share
# one and the move runs on through the cut instead of settling at every one.
CAMERA_RATE = re.compile(
    r"^(" + "|".join(CAMERA_MOVES) + r")\s*([0-9]+(?:\.[0-9]+)?)\s*[%％]\s*[/／]\s*秒$"
)
CAMERA_HOLD = "固定"
CAMERA_MOVE_LIMITS = (1, 30)
CAMERA_RATE_LIMITS = (0.1, 10.0)
# A move that starts or stops from rest ramps its speed over this long.
CAMERA_EASE = 0.5
CAMERA_OPPOSITES = {"推近": "拉远", "拉远": "推近", "左移": "右移", "右移": "左移", "上移": "下移", "下移": "上移"}
# Adjacent moves in one scene whose speeds differ by more than this read as a lurch.
CAMERA_SPEED_NOTICE = 0.30
# 「环境声：[<起>] <文件>」 lays a room under the film from this cut on, looping the
# file, until the next 环境声 line (「无」 stops it).
BED_FIELD = "环境声"
BED = re.compile(r"^\s*(?:(-?[0-9]+(?:\.[0-9]+)?)\s+)?(.+?)\s*$")
BED_FADE = 0.3
# The silent track under a still when there is no video audio to match.
STILL_AUDIO = (48000, "stereo")
# 「配音 N：<起> <文件>」 plays a voice file to its end, from its cut's start plus
# 起. It may run on over the cuts after it (an L-cut), and 起 may be negative, as
# far back as the previous cut's start (a J-cut): the line is part of the film's
# sound, not of one picture.
VOICE_FIELD = re.compile(r"^配音(?:\s*(\d+))?$")
VOICE = re.compile(r"^\s*(-?[0-9]+(?:\.[0-9]+)?)\s+(.+?)\s*$")
VOICE_OVERRUN = 0.05
# A sound line's trailing 「（起点：<秒>；增益：<dB>）」, either or both, in any order.
SOUND_OPTIONS = re.compile(r"[（(]\s*((?:起点|增益)[：:][^（）()]*)[）)]\s*$")
SOUND_OPTION = re.compile(r"^(起点|增益)[：:]\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*(dB)?$", re.I)
# What counts as audible in a voice file: a 20 ms window within this many dB of
# its loudest window. TTS pads each line with a breath of silence at both ends;
# measured on the files, the checks would keep two lines 0.4 s apart that are
# not overlapping at all.
AUDIBLE_RANGE_DB = 40.0
AUDIBLE_WINDOW = 0.02
AUDIBLE_RATE = 8000
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
    # 「起点」: where in the file playback begins.
    offset: float = 0.0


class CameraMove(NamedTuple):
    """「运镜」 on a still: 固定, a push, pull or pan of `amount` percent, or at `rate` %/s."""

    kind: str = CAMERA_HOLD
    amount: float = 0
    rate: Optional[float] = None


class Bed(NamedTuple):
    """One 「环境声」 line: from `start` seconds into its cut, `path` looping; None is 「无」."""

    start: float
    path: Optional[str]
    gain_db: float = 0.0
    offset: float = 0.0


class Placed(NamedTuple):
    """A sound laid on the film: output start and length, the file, and how it is played."""

    start: float
    duration: float
    path: str
    gain_db: float = 0.0
    offset: float = 0.0
    loop: bool = False
    fade_in: float = 0.0
    fade_out: float = 0.05


class Voice(NamedTuple):
    """One 「配音」 line: the file from `offset` to its end, `start` seconds into the cut."""

    start: float
    path: str
    gain_db: float = 0.0
    offset: float = 0.0


class Audible(NamedTuple):
    """A sound file's length and the span inside it that is not silence, in seconds."""

    duration: float
    head: float
    tail: float


class Cut(NamedTuple):
    cut_id: str
    title: str
    # The source ID: MOTION-... for a video cut, SHOT-... or IMG-... for a still.
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
    # Stills only; None on a video cut.
    move: Optional[CameraMove] = None
    voices: tuple[Voice, ...] = ()
    bed: Optional[Bed] = None

    @property
    def still(self) -> bool:
        return not self.motion.startswith("MOTION-")


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
            name = field.group(1).strip()
            if name in current["fields"]:
                raise EditError(_repeated_field(name, current["cut_id"], number))
            current["fields"][name] = (field.group(2).strip(), number)
    close(current)
    return _parse_delivery(preamble), cuts, unused


def _repeated_field(name: str, cut_id: str, line: int) -> str:
    """A field written twice in one cut: the second would silently replace the first."""

    where = f"{CUT_LIST_NAME}:{line}: {cut_id} 的「{name}」写了两遍"
    for pattern, label in (
        (SUBTITLE_FIELD, "字幕"), (SCREEN_TEXT_FIELD, "画面文字"), (SOUND_EFFECT_FIELD, "音效"),
        (VOICE_FIELD, "配音"),
    ):
        if pattern.match(name):
            return f"{where}；一段有多条{label}时全部编号，且编号不重复：「{label} 1」「{label} 2」…"
    return f"{where}；这一项一段只写一次"


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
            f"「MOTION-... · 项目相对路径」，静帧写「SHOT-... · 图片路径」或「IMG-... · 图片路径」，"
            f"当前是 {source_raw!r}"
        )
    still = not source.group(1).startswith("MOTION-")
    if still != (Path(source.group(2)).suffix.lower() in IMAGE_SUFFIXES):
        raise EditError(
            f"{CUT_LIST_NAME}:{source_line}: {cut_id} 的来源 {source.group(1)} 与文件类型不符；"
            "视频素材写 MOTION-...，静帧（" + "/".join(sorted(IMAGE_SUFFIXES))
            + "）写 SHOT-... 或 IMG-..."
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
        move=_parse_move(fields, cut_id=cut_id, still=still),
        voices=_parse_voices(fields, cut_id=cut_id, line=line),
        bed=_parse_bed(fields, cut_id=cut_id),
    )


def _parse_bed(fields: dict[str, tuple[str, int]], *, cut_id: str) -> Optional[Bed]:
    """Read 「环境声：[<起>] <文件>（起点：<秒>；增益：<dB>）」 or 「环境声：[<起>] 无」."""

    raw = fields.get(BED_FIELD)
    if raw is None:
        return None
    value, gain, offset = _sound_options(raw[0], BED_FIELD, cut_id=cut_id, where=raw[1])
    found = BED.match(value)
    # A bed has a start, not a window: it runs until the next 环境声 line.
    if not found or SUBTITLE_CUE.match(value):
        raise EditError(
            f"{CUT_LIST_NAME}:{raw[1]}: {cut_id} 的「环境声」要写成「[<起>] <项目相对路径>」或「[<起>] 无」"
        )
    path = found.group(2)
    return Bed(float(found.group(1) or 0.0), None if path == "无" else path, gain, offset)


def _parse_move(
    fields: dict[str, tuple[str, int]], *, cut_id: str, still: bool
) -> Optional[CameraMove]:
    """Read 「运镜：固定|推近 <n>%|拉远|左移|右移|上移|下移」. Stills only; default 固定."""

    raw = fields.get("运镜")
    if raw is None:
        return CameraMove() if still else None
    value, where = raw[0].strip(), raw[1]
    if not still:
        raise EditError(
            f"{CUT_LIST_NAME}:{where}: {cut_id} 是视频段，「运镜」只写在静帧段上；"
            "视频的运镜在生成时就定了"
        )
    if value == CAMERA_HOLD:
        return CameraMove()
    paced = CAMERA_RATE.match(value)
    if paced:
        low, high = CAMERA_RATE_LIMITS
        rate = float(paced.group(2))
        if not low <= rate <= high:
            raise EditError(
                f"{CUT_LIST_NAME}:{where}: {cut_id} 的运镜速度 {rate:g}%/秒 超出 {low:g}–{high:g}"
            )
        return CameraMove(paced.group(1), 0, rate)
    found = CAMERA_MOVE.match(value)
    low, high = CAMERA_MOVE_LIMITS
    if not found or not low <= int(found.group(2)) <= high:
        raise EditError(
            f"{CUT_LIST_NAME}:{where}: {cut_id} 的运镜要写成「{CAMERA_HOLD}」、"
            f"「{'/'.join(CAMERA_MOVES)} <{low}–{high}>%」或「… <速度>%/秒」，当前是 {value!r}"
        )
    return CameraMove(found.group(1), int(found.group(2)))


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


def _sound_options(
    value: str, label: str, *, cut_id: str, where: int
) -> tuple[str, float, float]:
    """Split 「（起点：<秒>；增益：<dB>）」 off a sound line: (rest, dB, 起点 seconds)."""

    stated = SOUND_OPTIONS.search(value)
    if not stated:
        return value, 0.0, 0.0
    options: dict[str, float] = {}
    for part in re.split(r"[；;]", stated.group(1)):
        found = SOUND_OPTION.match(part.strip())
        if not found or found.group(1) in options or (found.group(3) and found.group(1) != "增益"):
            raise EditError(
                f"{CUT_LIST_NAME}:{where}: {cut_id} 的「{label}」括号里只写「起点：<秒>」"
                f"和「增益：<dB>」，各至多一次，用「；」分隔，当前是 {part.strip()!r}"
            )
        options[found.group(1)] = float(found.group(2))
    gain, offset = options.get("增益", 0.0), options.get("起点", 0.0)
    low, high = GAIN_LIMITS
    if not low <= gain <= high:
        raise EditError(
            f"{CUT_LIST_NAME}:{where}: {cut_id} 的「{label}」增益 {gain:g} dB "
            f"超出 {low:g} 到 {high:g}"
        )
    if offset < 0:
        raise EditError(f"{CUT_LIST_NAME}:{where}: {cut_id} 的「{label}」起点不能为负")
    return value[: stated.start()], gain, offset


def _parse_sound_effects(
    fields: dict[str, tuple[str, int]], *, cut_id: str, line: int
) -> tuple[SoundEffect, ...]:
    """Read 「音效 N：<起>-<止> <文件>（起点：<秒>；增益：<dB>）」 lines."""

    _, entries = _field_entries(fields, SOUND_EFFECT_FIELD, "音效", cut_id=cut_id, line=line)
    effects: list[SoundEffect] = []
    for index, value, where in entries:
        if value.strip() == "无":
            continue
        value, gain, offset = _sound_options(value, f"音效 {index}", cut_id=cut_id, where=where)
        found = SUBTITLE_CUE.match(value)
        if not found:
            raise EditError(
                f"{CUT_LIST_NAME}:{where}: {cut_id} 的「音效 {index}」要写成"
                "「<起>-<止> <项目相对路径>」"
            )
        effects.append(SoundEffect(
            float(found.group(1)), float(found.group(2)), found.group(3), gain, offset
        ))
    return tuple(effects)


def _parse_voices(
    fields: dict[str, tuple[str, int]], *, cut_id: str, line: int
) -> tuple[Voice, ...]:
    """Read 「配音 N：<起> <文件>（起点：<秒>；增益：<dB>）」 lines. The file plays to its end."""

    _, entries = _field_entries(fields, VOICE_FIELD, "配音", cut_id=cut_id, line=line)
    voices: list[Voice] = []
    for index, value, where in entries:
        if value.strip() == "无":
            continue
        value, gain, offset = _sound_options(value, f"配音 {index}", cut_id=cut_id, where=where)
        found = VOICE.match(value)
        if not found:
            raise EditError(
                f"{CUT_LIST_NAME}:{where}: {cut_id} 的「配音 {index}」要写成"
                "「<起> <项目相对路径>」，从起点放到文件结束"
            )
        voices.append(Voice(float(found.group(1)), found.group(2), gain, offset))
    return tuple(voices)


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
        stray = [
            word for word in words if word not in text or not _display_line(word)
        ]
        if stray:
            raise EditError(
                f"{CUT_LIST_NAME}:{where}: {cut_id} 的字幕重点词不在这句里或只有标点: {stray}"
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


def _excused(unused: Sequence[str]) -> set[str]:
    """IDs listed under 「未采用镜头」 with a non-empty reason."""

    excused = set()
    for note in unused:
        match = re.fullmatch(
            r"((?:MOTION|SHOT|IMG)-[\w-]+)\s*[（(]理由[：:]\s*(.+?)[）)]", note.strip()
        )
        if match and match.group(2).strip():
            excused.add(match.group(1))
    return excused


def probe_audio(media: Path) -> Optional[tuple[int, str]]:
    """(sample rate, channel layout) of the first audio stream; None when it has none."""

    probe = _require("ffprobe")
    result = subprocess.run(
        [probe, "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=sample_rate,channels,channel_layout", "-of", "json", str(media)],
        capture_output=True, text=True, check=False,
    )
    streams = json.loads(result.stdout or "{}").get("streams") if result.returncode == 0 else None
    if not streams:
        return None
    stream = streams[0]
    layout = stream.get("channel_layout") or ("mono" if stream.get("channels") == 1 else "stereo")
    return int(stream.get("sample_rate") or STILL_AUDIO[0]), layout


def _unaccounted_shots(
    known: set[str],
    cuts: Sequence[Cut],
    unused: Sequence[str],
    *,
    accounted: Iterable[str] = (),
) -> list[str]:
    """Require each source to be used, accounted for another way, or omitted with a reason."""

    used = {cut.motion for cut in cuts} | set(accounted)
    missing = sorted(known - used - _excused(unused))
    if not missing:
        return []
    return [
        f"{CUT_LIST_NAME}: 以下镜头未采用，且缺少「未采用镜头」及理由："
        + "、".join(missing)
    ]


def _headings(path: Path, heading: re.Pattern[str]) -> Optional[set[str]]:
    """The IDs a document declares as `##` headings; None when it does not exist."""

    if not path.is_file():
        return None
    return {
        match.group(1)
        for match in map(heading.match, path.read_text(encoding="utf-8").splitlines())
        if match
    }


def _motion_shots(episode: Path) -> dict[str, str]:
    """`{MOTION-...: SHOT-...}` from each video prompt's 「分镜」 line."""

    fields = _heading_fields(episode / MOTION_DOCUMENT, MOTION_HEADING, "分镜")
    return {
        motion: found.group(0)
        for motion, value in fields.items()
        for found in [SHOT_REFERENCE.search(value)]
        if found
    }


def _source_findings(episode: Path, cuts: Sequence[Cut], unused: Sequence[str]) -> list[str]:
    """Each source ID exists in its document, and each shot is in the film or excused.

    Video prompts are held to coverage when the list has a video cut, storyboard
    shots when it has a SHOT- still. Across the two, a shot counts once however
    it reached the film: a MOTION whose storyboard shot went in as a still is
    accounted for, and so is a SHOT whose MOTION was used or excused.
    """

    findings: list[str] = []
    documents = (
        ("MOTION-", MOTION_DOCUMENT, MOTION_HEADING),
        ("SHOT-", STORYBOARD_DOCUMENT, SHOT_HEADING),
        ("IMG-", IMAGE_DOCUMENT, IMAGE_HEADING),
    )
    known: dict[str, Optional[set[str]]] = {}
    for prefix, name, heading in documents:
        using = [cut for cut in cuts if cut.motion.startswith(prefix)]
        declared = known[prefix] = _headings(episode / name, heading) if using else None
        if not using:
            continue
        if declared is None:
            findings.append(f"没有 {episode / name}，来源 {prefix[:-1]} 无法核对")
            continue
        findings.extend(
            f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的来源 "
            f"{cut.motion} 不在《{name}》中"
            for cut in using if cut.motion not in declared
        )

    shot_of = _motion_shots(episode)
    used = {cut.motion for cut in cuts}
    motions, shots = known["MOTION-"], known["SHOT-"]
    if motions is not None:
        findings.extend(_unaccounted_shots(
            motions, cuts, unused, accounted={m for m in motions if shot_of.get(m) in used},
        ))
    if shots is not None:
        findings.extend(_unaccounted_shots(
            shots, cuts, unused,
            accounted={shot_of[m] for m in used | _excused(unused) if m in shot_of},
        ))
    return findings


def probe_audible(media: Path) -> Audible:
    """A sound file's length and where its sound starts and stops, decoded small and mono."""

    ffmpeg = _require("ffmpeg")
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(media), "-ac", "1", "-ar", str(AUDIBLE_RATE),
         "-f", "s16le", "-"],
        capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise EditError(f"ffmpeg 读不出声音: {media} ({result.stderr.decode(errors='replace').strip()})")
    samples = array("h")
    samples.frombytes(result.stdout[: len(result.stdout) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    return _audible_span(samples, AUDIBLE_RATE)


def _audible_span(samples: Sequence[int], rate: int) -> Audible:
    """The first and last 20 ms window within AUDIBLE_RANGE_DB of the loudest one."""

    size = max(1, round(rate * AUDIBLE_WINDOW))
    energies = [
        sum(value * value for value in samples[at:at + size]) / len(samples[at:at + size])
        for at in range(0, len(samples), size)
    ]
    duration = len(samples) / rate
    loudest = max(energies, default=0.0)
    if loudest <= 0:
        return Audible(duration, 0.0, 0.0)
    floor = loudest * 10 ** (-AUDIBLE_RANGE_DB / 10)
    heard = [index for index, energy in enumerate(energies) if energy >= floor]
    return Audible(duration, heard[0] * size / rate, min(duration, (heard[-1] + 1) * size / rate))


def _voice_sounds(episode: Path, project_root: Path, cuts: Sequence[Cut]) -> dict[str, Audible]:
    """Every 「配音」 file, measured, keyed as written. Raises when one cannot be read."""

    sounds: dict[str, Audible] = {}
    for cut in cuts:
        for voice in cut.voices:
            if voice.path in sounds:
                continue
            media = _resolve_media(episode, project_root, voice.path)
            if media is None:
                raise EditError(f"配音文件不存在或不在项目目录内: {voice.path}")
            sounds[voice.path] = probe_audible(media)
    return sounds


def _voice_spans(
    cuts: Sequence[Cut], sounds: dict[str, Audible], lengths: Sequence[float]
) -> list[tuple[float, float, Cut, Voice]]:
    """Each voice line's audible span in film seconds, cuts laid end to end at `lengths`."""

    spans: list[tuple[float, float, Cut, Voice]] = []
    for cut, cursor, length in _timeline(cuts, lengths):
        for voice in cut.voices:
            sound = sounds[voice.path]
            # Where the file's own second zero lands on the film.
            zero = _at(cut, cursor, length, voice.start) - voice.offset
            spans.append((zero + max(sound.head, voice.offset), zero + sound.tail, cut, voice))
    return sorted(spans, key=lambda span: span[0])


def _voice_findings(
    cuts: Sequence[Cut], sounds: dict[str, Audible], lengths: Sequence[float]
) -> list[str]:
    """A voice line is heard inside the film and never over another line, across cuts too."""

    total = sum(lengths)
    findings: list[str] = []
    latest: Optional[tuple[float, float, Cut, Voice]] = None
    for span in _voice_spans(cuts, sounds, lengths):
        start, end, cut, voice = span
        where = f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id}"
        if end <= start:
            findings.append(f"{where} 的配音 {voice.path} 起点 {voice.offset:g} 秒之后没有声音")
            continue
        if end > total + VOICE_OVERRUN:
            findings.append(
                f"{where} 的配音 {voice.path} 在成片 {start:.2f} 秒开口、{end:.2f} 秒才说完，"
                f"超出成片结尾 {total:.2f}；加长末几段或提前起点"
            )
        if latest is not None and start < latest[1] - TOLERANCE:
            findings.append(
                f"{where} 的配音 {voice.path}（成片 {start:.2f} 秒开口）压在 {latest[2].cut_id} 的"
                f"配音 {latest[3].path} 上（说到 {latest[1]:.2f} 秒）"
            )
        if latest is None or end > latest[1]:
            latest = span
    return findings


def _subtitle_findings(cuts: Sequence[Cut], lengths: Sequence[float]) -> list[str]:
    """A subtitle may run on past its cut, but stays in the film and off every other subtitle."""

    total = sum(lengths)
    placed: list[tuple[float, float, Cut]] = []
    findings: list[str] = []
    for cut, cursor, length in _timeline(cuts, lengths):
        for window_start, window_end, _, _ in cut.subtitles:
            start = 0.0 if window_start is None else window_start
            end = cut.declared if window_end is None else window_end
            shown = (_at(cut, cursor, length, start), _at(cut, cursor, length, end))
            if not 0 <= start < min(end, cut.declared) or shown[1] > total + TOLERANCE:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的字幕时间要从本段内开始、"
                    f"在成片结尾之前结束: {start:g}-{end:g}"
                )
            placed.append((*shown, cut))
    placed.sort(key=lambda item: item[0])
    for (_, end, earlier), (start, _, later) in zip(placed, placed[1:]):
        if earlier is not later and start < end - TOLERANCE:
            findings.append(
                f"{CUT_LIST_NAME}:{later.line_number}: {later.cut_id} 的字幕与 {earlier.cut_id} "
                f"跨过来的字幕同时在屏上（成片 {start:.2f} 秒）"
            )
    return findings


def check_cuts(
    episode: Path,
    cuts: Sequence[Cut],
    project_root: Path,
    *,
    probe: bool,
    unused: Sequence[str] = (),
    delivery: Optional[Delivery] = None,
    listen: Optional[bool] = None,
) -> list[str]:
    """Every mechanical cross-check the cut list can be held to. Returns findings.

    `probe` reads media with ffprobe; `listen` (default: `probe`) decodes voice
    files with ffmpeg to find where they are audible.
    """

    if listen is None:
        listen = probe

    findings: list[str] = []
    if not cuts:
        findings.append(f"{CUT_LIST_NAME}: 没有 CUT 条目")
        return findings

    seen: set[str] = set()
    for cut in cuts:
        if cut.cut_id in seen:
            findings.append(f"{CUT_LIST_NAME}:{cut.line_number}: CUT ID 重复: {cut.cut_id}")
        seen.add(cut.cut_id)

    findings.extend(_source_findings(episode, cuts, unused))
    # Stills are drawn at the delivery frame; video in the same film must match it.
    spec: Optional[tuple[Any, Any, float]] = None
    if any(cut.still for cut in cuts):
        if delivery is None or delivery.frame_size is None or delivery.fps is None:
            findings.append(
                f"{CUT_LIST_NAME}: 有静帧段时，交付规格必须写「画幅与帧率」"
                "（如 1080×1920 · 24fps）；静帧按它出画"
            )
        else:
            spec = (*delivery.frame_size, round(delivery.fps, 3))
            if any(side % 2 for side in delivery.frame_size):
                findings.append(
                    f"{CUT_LIST_NAME}: 交付画幅 {delivery.frame_size[0]}×{delivery.frame_size[1]} "
                    "有奇数边；静帧按它编码成 4:2:0，宽高都要是偶数"
                )

    screenplay = ""
    screenplay_path = episode / SCREENPLAY_DOCUMENT
    if screenplay_path.is_file():
        screenplay = screenplay_path.read_text(encoding="utf-8")

    media_format: Optional[tuple[Any, Any, float]] = None
    voiced = True
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
        if cut.still and abs(cut.start) > TOLERANCE:
            findings.append(
                f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 是静帧，入点必须是 0.00，"
                "出点等于时长"
            )
        if cut.still and cut.declared < STILL_MINIMUM - TOLERANCE:
            findings.append(
                f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 是静帧，时长 "
                f"{cut.declared:.2f} 短于 {STILL_MINIMUM:.2f} 秒"
            )
        media = _resolve_media(episode, project_root, cut.media)
        if media is None:
            findings.append(
                f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的素材不存在或不在项目目录内: {cut.media}"
            )
        elif probe and cut.still:
            try:
                probe_stream(media)
            except EditError as error:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的图片读不出: {error}"
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
            if spec is not None and current_format != spec:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的画幅或帧率 "
                    f"{current_format} 与交付规格 {spec} 不一致；静帧按交付规格出画，"
                    "同一条片里的视频段须与之相同"
                )
            if cut.end > available + TOLERANCE:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 出点 {cut.end:.2f} "
                    f"超过素材实际时长 {available:.2f}"
                )
        for _, _, text, _ in cut.subtitles:
            if screenplay and _normalize(text) not in _normalize(screenplay):
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的字幕在《"
                    f"{SCREENPLAY_DOCUMENT}》里找不到原文: {text}"
                )
        for effect in cut.sound_effects:
            if not 0 <= effect.start < effect.end <= span + TOLERANCE:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的音效时间超出本段区间"
                    f": {effect.start:g}-{effect.end:g}"
                )
            effect_media = _resolve_media(episode, project_root, effect.path)
            if effect_media is None:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的音效文件不存在或不在项目目录内: "
                    f"{effect.path}"
                )
            elif probe and effect.offset > 0:
                try:
                    available_sound = probe_duration(effect_media)
                    if effect.offset >= available_sound:
                        findings.append(
                            f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的音效起点 "
                            f"{effect.offset:g} 必须小于 {effect.path} 的实际时长 {available_sound:g}"
                        )
                except EditError as error:
                    findings.append(f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的音效读不出: {error}")
        for voice in cut.voices:
            if _resolve_media(episode, project_root, voice.path) is None:
                voiced = False
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的配音文件不存在或不在项目目录内: "
                    f"{voice.path}"
                )

    # The film's rate: the spec's, else the one the probe loop read off the video.
    fps = delivery.fps if delivery is not None and delivery.fps else (media_format or (0, 0, 0.0))[2]
    lengths = _film_spans(cuts, fps)
    for index, cut in enumerate(cuts):
        where = f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id}"
        if cut.move is not None and cut.move.rate is not None:
            reach = cut.move.rate * lengths[index]
            if reach > CAMERA_MOVE_LIMITS[1]:
                findings.append(
                    f"{where} 的运镜 {cut.move.rate:g}%/秒 走完这一段是 {reach:.0f}%，"
                    f"超过 {CAMERA_MOVE_LIMITS[1]}%；放慢或缩短这一段"
                )
        if cut.bed is not None:
            earliest = -lengths[index - 1] if index else 0.0
            if not earliest - TOLERANCE <= cut.bed.start < cut.end - cut.start:
                findings.append(
                    f"{where} 的环境声起点 {cut.bed.start:g} 要在 {earliest:g}（上一段开头）到本段结尾之间"
                )
            if cut.bed.path is not None and _resolve_media(episode, project_root, cut.bed.path) is None:
                findings.append(f"{where} 的环境声文件不存在或不在项目目录内: {cut.bed.path}")
        for voice in cut.voices:
            # A J-cut reaches back at most to the previous cut's start.
            earliest = -lengths[index - 1] if index else 0.0
            if not earliest - TOLERANCE <= voice.start < cut.end - cut.start:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的配音起点 {voice.start:g} "
                    f"要在 {earliest:g}（上一段开头）到本段结尾之间"
                )
    findings.extend(_subtitle_findings(cuts, lengths))
    if listen and voiced and any(cut.voices for cut in cuts):
        try:
            findings.extend(_voice_findings(cuts, _voice_sounds(episode, project_root, cuts), lengths))
        except EditError as error:
            findings.append(f"{CUT_LIST_NAME}: {error}")

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
            or cut.voices
        )
        if not timed:
            continue
        # A still's timings were measured on its voice files, not on the picture.
        written = [voice.path for voice in cut.voices] + ([] if cut.still else [cut.media])
        for relative in written:
            media = _resolve_media(episode, project_root, relative)
            if media is None:
                continue
            try:
                changed = media.stat().st_mtime
            except OSError:
                continue
            if changed > authored + 1.0:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 的素材比剪辑单新"
                    f"（{relative}）；这一段的字幕、画面文字与音效时间是按旧素材反推的，"
                    "重出之后必须重测再改，不能沿用"
                )
    return findings


def _overlap_findings(cuts: Sequence[Cut]) -> list[str]:
    """Two cuts drawn from one file must not reuse the same frames (EDT-06)."""

    findings: list[str] = []
    by_media: dict[str, list[Cut]] = {}
    for cut in cuts:
        # A keyframe reused in a shot/reverse-shot is a choice, not repeated footage.
        if not cut.still:
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
    """The file a cut list names, against the episode then the project; None if absent.

    A path that leaves the project (`../`, an absolute path, a link out) is
    treated as absent: the cut list describes this project's material only.
    """

    root = project_root.resolve()
    for base in (episode, project_root):
        candidate = (base / relative).resolve()
        if candidate.is_file() and (candidate == root or root in candidate.parents):
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
        if media is None:
            return None
        if cut.still:
            return None if delivery.frame_size is None else _still_stats(
                ffmpeg, media, delivery.frame_size
            )
        return _channel_stats(ffmpeg, media, cut.start, cut.end - cut.start)

    scenes = _scene_keys(episode, cuts)
    pictures, auto = _picture_plan(cuts, scenes, measure, enabled=delivery.shot_match)
    silence = _silent_track(episode, project_root, cuts, delivery)
    sounds = _voice_sounds(episode, project_root, cuts)
    fps = _film_fps(episode, project_root, cuts, delivery, probe=True)
    spans = _film_spans(cuts, fps)

    eases = _move_ease(cuts, scenes)
    segments: list[Path] = []
    for cut, match, length, ease in zip(cuts, pictures, spans, eases):
        media = _resolve_media(episode, project_root, cut.media)
        if media is None:
            raise EditError(f"{cut.cut_id} 的素材不存在或不在项目目录内: {cut.media}")
        segment = segments_root / f"{cut.cut_id}.mp4"
        if cut.still:
            command = _still_command(ffmpeg, media, cut, delivery, silence, match, length, ease)
        else:
            # Read enough source for the whole frames the film gives this cut.
            span = max(cut.end - cut.start, length)
            command = [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{cut.start:.3f}", "-t", f"{span:.3f}", "-i", str(media),
            ]
            if probe_audio(media) is None:
                rate, layout = silence
                command += [
                    "-f", "lavfi", "-t", f"{span:.3f}", "-i", f"anullsrc=r={rate}:cl={layout}",
                    "-map", "0:v", "-map", "1:a",
                ]
            if match:
                command += ["-vf", match]
            if fps:
                command += ["-frames:v", str(round(length * fps)), "-t", f"{length:.6f}"]
        command += [
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-ar", str(silence[0]), "-channel_layout", silence[1],
            "-c:a", "aac", "-b:a", "192k", str(segment),
        ]
        _run(command)
        segments.append(segment)
        # Everything after this cut is placed by `spans`; a segment that came
        # out short (the source ran out of frames) would shift all of it.
        rendered = probe_duration(segment)
        if fps and abs(rendered - length) > 1.5 / fps:
            raise EditError(
                f"{cut.cut_id} 渲染出 {rendered:.3f} 秒，按 {fps:g} fps 应为 {length:.3f} 秒；"
                "素材在出点附近可能不够帧，先把出点提前一帧"
            )

    with tempfile.TemporaryDirectory() as scratch:
        listing = Path(scratch) / "segments.txt"
        listing.write_text(
            "".join(f"file '{segment.as_posix()}'\n" for segment in segments), encoding="utf-8"
        )
        joined = output_root / "成片-未混音.mp4"
        # AAC encoder priming starts before zero. Keep that timestamp rather
        # than shifting the video by one audio packet (and duplicating a frame
        # when downstream tools decode at the delivery frame rate).
        _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-copyts",
              "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)])

        effects: list[Placed] = []
        placed = (
            _placed_sound_effects(cuts, spans) + _placed_voices(cuts, sounds, spans)
            + _placed_beds(cuts, spans)
        )
        for sound in placed:
            resolved = _resolve_media(episode, project_root, sound.path)
            if resolved is None:
                raise EditError(f"音效、配音或环境声文件不存在或不在项目目录内: {sound.path}")
            effects.append(sound._replace(path=str(resolved)))
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
        "音效": sum(len(cut.sound_effects) for cut in cuts),
        "配音": sum(len(cut.voices) for cut in cuts),
        "环境声": len(_placed_beds(cuts, spans)),
        "静帧段": sum(cut.still for cut in cuts),
        "自动接镜": _shot_match_report(auto, scenes, enabled=delivery.shot_match),
        "段数": len(segments),
        "各段时长之和": round(sum(cut.end - cut.start for cut in cuts), 2),
    }


def _silent_track(
    episode: Path, project_root: Path, cuts: Sequence[Cut], delivery: Delivery
) -> tuple[int, str]:
    """Shared (sample rate, layout) for every rendered segment.

    Segments are joined by stream copy, so every segment needs an audio track
    encoded like the first video audio beside it, including audible clips: a
    segment without one shifts every sound after it, and a mismatched one
    decodes wrong. 48 kHz stereo when no clip has sound.
    """

    if any(cut.still for cut in cuts) and (delivery.frame_size is None or delivery.fps is None):
        raise EditError("有静帧段时，交付规格必须写「画幅与帧率」；静帧按它出画")
    for cut in cuts:
        media = None if cut.still else _resolve_media(episode, project_root, cut.media)
        heard = probe_audio(media) if media is not None else None
        if heard is not None:
            return heard
    return STILL_AUDIO


def _move_ease(
    cuts: Sequence[Cut], scenes: Sequence[Optional[tuple[str, ...]]]
) -> list[tuple[bool, bool]]:
    """(ease in, ease out) per cut: a move ramps only where it starts or stops from rest.

    Two adjacent rate moves (「%/秒」) in the same direction and the same scene
    run straight through the cut between them: the camera does not stop at the
    join. A move eases in where the cut before it is in another scene, is 固定,
    or moves some other way, and eases out likewise. The percentage form always
    eases at both ends: it states where the move ends, not how fast it goes.
    """

    def continues(earlier: int, later: int) -> bool:
        first, second = cuts[earlier].move, cuts[later].move
        return (
            first is not None and second is not None
            and first.rate is not None and second.rate is not None
            and first.kind == second.kind != CAMERA_HOLD
            and scenes[earlier] is not None and scenes[earlier] == scenes[later]
        )

    last = len(cuts) - 1
    return [
        (not (index and continues(index - 1, index)), not (index < last and continues(index, index + 1)))
        for index in range(len(cuts))
    ]


def _move_progress(
    move: CameraMove, frames: int, fps: float, ease: tuple[bool, bool]
) -> tuple[str, float]:
    """How far the move has gone at output frame `on`, in percent, and how far it goes in all.

    A rate move cruises at its speed and ramps (a half cosine, CAMERA_EASE long)
    only at the ends `ease` names, so where it does not ease its speed at the
    cut equals the next cut's. The percentage form eases over the whole cut.
    """

    last = max(frames - 1, 1)
    if move.rate is None:
        return f"({move.amount}*(1-cos(PI*on/{last}))/2)", float(move.amount)
    span = last / fps
    ramp_in = min(CAMERA_EASE, span / 2) if ease[0] else 0.0
    ramp_out = min(CAMERA_EASE, span / 2) if ease[1] else 0.0
    t = f"(on/{fps:g})"
    terms = [t]
    # Distance lost to each ramp so far: the integral of (1 - speed / cruise).
    if ramp_in:
        a = f"min({t},{ramp_in:.6f})"
        terms.append(f"-({a}+{ramp_in / 3.141592653589793:.6f}*sin(PI*{a}/{ramp_in:.6f}))/2")
    if ramp_out:
        b = f"max(0,{t}-{span - ramp_out:.6f})"
        terms.append(f"-({b}-{ramp_out / 3.141592653589793:.6f}*sin(PI*{b}/{ramp_out:.6f}))/2")
    total = move.rate * (span - ramp_in / 2 - ramp_out / 2)
    return f"({move.rate:g}*({''.join(terms)}))", total


def _still_filter(
    move: CameraMove, width: int, height: int, frames: int,
    fps: float = 24.0, ease: tuple[bool, bool] = (True, True),
) -> str:
    """Cover-fit a still to the frame and move across it on an eased curve.

    The move is a window over the fitted picture, `1/zoom` of it on each side,
    whose corners `perspective` samples per frame at sub-pixel positions.
    zoompan and crop place the window on whole pixels, which is what makes a
    slow push judder. Measured on 1080×1920 renders, the frame-to-frame motion
    of a push wavered 0.34 px rms with zoompan, 0.14 px with zoompan at 4×
    internal scale and 0.10 px here; of a pan, 0.84, 0.23 and 0.11 px. This
    route also renders no slower than the 4× one.
    """

    fitted = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={width}:{height},setsar=1"
    )
    if move.kind == CAMERA_HOLD:
        return fitted
    gone, total = _move_progress(move, frames, fps, ease)
    reach = total / 100
    # Share of the move done, 0 to 1.
    eased = f"({gone}/{total:.6f})" if total > 0 else "0"
    zoom = {
        "推近": f"(1+{reach:.6f}*{eased})",
        "拉远": f"(1+{reach:.6f}*(1-{eased}))",
    }.get(move.kind, f"{1 + reach:.6f}")
    across, down = f"(W/{zoom})", f"(H/{zoom})"
    room_x, room_y = f"(W-{across})", f"(H-{down})"
    # A camera move: 左移 slides the window left, so the picture drifts right.
    x = {"左移": f"{room_x}*(1-{eased})", "右移": f"{room_x}*{eased}"}.get(move.kind, f"{room_x}/2")
    y = {"上移": f"{room_y}*(1-{eased})", "下移": f"{room_y}*{eased}"}.get(move.kind, f"{room_y}/2")
    corners = ((x, y), (f"{x}+{across}", y), (x, f"{y}+{down}"), (f"{x}+{across}", f"{y}+{down}"))
    points = ":".join(f"x{i}='{cx}':y{i}='{cy}'" for i, (cx, cy) in enumerate(corners))
    return f"{fitted},perspective={points}:interpolation=cubic:eval=frame"


def _still_command(
    ffmpeg: str,
    image: Path,
    cut: Cut,
    delivery: Delivery,
    silence: tuple[int, str],
    match: str,
    seconds: float,
    ease: tuple[bool, bool] = (True, True),
) -> list[str]:
    """The input half of a still segment's command: picture, move, correction and silence.

    `seconds` is the cut's span from `_film_spans`, a whole number of frames.
    """

    assert delivery.frame_size is not None and delivery.fps is not None
    width, height = delivery.frame_size
    frames = max(1, round(seconds * delivery.fps))
    chain = _still_filter(cut.move or CameraMove(), width, height, frames, delivery.fps, ease)
    rate, layout = silence
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-framerate", f"{delivery.fps:g}", "-i", str(image),
        "-f", "lavfi", "-t", f"{seconds:.3f}", "-i", f"anullsrc=r={rate}:cl={layout}",
        "-vf", ",".join(filter(None, [chain, match])),
        "-map", "0:v", "-map", "1:a", "-frames:v", str(frames), "-t", f"{seconds:.3f}",
    ]


def _placed_voices(
    cuts: Sequence[Cut], sounds: dict[str, Audible], spans: Sequence[float]
) -> list[Placed]:
    """Each voice line in the form `_placed_sound_effects` gives, for the same mix.

    Its start follows the rendered cut positions, like an effect's. Its length
    does not: an effect's window is a stretch of its cut and scales with the
    frame rounding, but a voice plays its file from 起点 to the end, and
    scaling that would clip the line. It is laid at its cut's start plus 起
    however far past the cut it runs, which is what makes an L-cut.
    """

    return [
        Placed(max(0.0, _at(cut, cursor, length, voice.start)), sounds[voice.path].duration - voice.offset,
               voice.path, voice.gain_db, voice.offset)
        for cut, cursor, length in _timeline(cuts, spans)
        for voice in cut.voices
    ]


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

    A SHOT- still starts at the SHOT. A shot drawing on two scenes keys on both,
    so it matches neither neighbour. None where the chain breaks (an IMG- still
    names no shot); such a cut is never matched.
    """

    shots = _motion_shots(episode)
    sources = _heading_fields(episode / STORYBOARD_DOCUMENT, SHOT_HEADING, "来源")
    keys: list[Optional[tuple[str, ...]]] = []
    for cut in cuts:
        shot = cut.motion if cut.motion.startswith("SHOT-") else shots.get(cut.motion)
        scenes = tuple(SCENE_ID.findall(sources.get(shot, ""))) if shot else ()
        keys.append(scenes or None)
    return keys


def move_notices(
    cuts: Sequence[Cut], scenes: Sequence[Optional[tuple[str, ...]]], lengths: Sequence[float]
) -> list[str]:
    """Joins inside one scene that will read as a jolt: a speed jump or a reversed move.

    Not errors: a deliberate change of pace is the creator's to make.
    """

    def speed(cut: Cut, length: float) -> Optional[float]:
        move = cut.move
        if move is None or move.kind == CAMERA_HOLD:
            return None
        return move.rate if move.rate is not None else move.amount / length if length else None

    notices: list[str] = []
    for index in range(1, len(cuts)):
        before, after = cuts[index - 1], cuts[index]
        if scenes[index - 1] is None or scenes[index - 1] != scenes[index]:
            continue
        first, second = speed(before, lengths[index - 1]), speed(after, lengths[index])
        if first is None or second is None or before.move is None or after.move is None:
            continue
        pair = f"{before.cut_id}（{before.move.kind} 约 {first:.1f}%/秒）→ {after.cut_id}（{after.move.kind} 约 {second:.1f}%/秒）"
        if CAMERA_OPPOSITES[before.move.kind] == after.move.kind:
            notices.append(f"{pair}：同一场里镜头来回反向，切过去像晃了一下；改成同向，或让其中一段固定")
        elif max(first, second) > (1 + CAMERA_SPEED_NOTICE) * min(first, second):
            notices.append(
                f"{pair}：同一场里运镜速度差了 {max(first, second) / min(first, second) - 1:.0%}，"
                "切过去像换了一台机器；同一场用一个速度，写成「%/秒」最省事"
            )
    return notices


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
    """One `lutrgb` stage on 8-bit RGB; the lookup clips to 0-255 itself.

    The numbers were measured on a 0-255 scale. Left to negotiate, a 10-bit
    source runs the lookup at 16 bits a channel and the offsets barely move it.
    """

    return "format=rgb24,lutrgb=" + ":".join(
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

    return _sampled_stats([
        ffmpeg, "-v", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
        "-i", str(media), "-vf", SHOT_MATCH_SAMPLE,
    ])


def _still_stats(ffmpeg: str, image: Path, frame_size: tuple[int, int]) -> Optional[ChannelStats]:
    """Per-channel mean and spread of a still as the frame shows it, cover-fitted.

    An image has no timeline: `fps` drops its only frame, and a seek on a JPEG
    returns none, so it is read once, whole.
    """

    width, height = frame_size
    return _sampled_stats([
        ffmpeg, "-v", "error", "-i", str(image), "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},scale=64:-2",
    ])


def _sampled_stats(command: list[str]) -> Optional[ChannelStats]:
    result = subprocess.run(
        command + ["-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True, check=False
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
    """Place each line in film seconds, on the frame-rounded spans the segments are rendered at.

    A segment lands on a frame boundary, so it runs a few milliseconds off the
    length the cut list declares. Accumulating the declared numbers instead
    drifts -- a third of a second by the end of eight cuts here -- and the
    subtitle leaves before the actor stops speaking.
    """

    cues: list[tuple[float, float, str, tuple[str, ...]]] = []
    for cut, cursor, length in _timeline(cuts, spans):
        for window_start, window_end, text, words in cut.subtitles:
            start = 0.0 if window_start is None else window_start
            end = cut.declared if window_end is None else window_end
            cues.append((_at(cut, cursor, length, start), _at(cut, cursor, length, end), text, words))
    return cues


def _film_spans(cuts: Sequence[Cut], fps: Optional[float]) -> list[float]:
    """How long each cut runs in the film: its declared length rounded to whole frames.

    render writes every segment as exactly this many frames, and everything
    that places or checks something on the film -- subtitles, screen text,
    effects, voices, the film's end -- lays the cuts end to end at these spans.
    Nothing re-derives timing from the declared lengths, so no path can drift
    from the picture by the frame rounding. Without a known rate, the declared
    lengths are all there is.
    """

    if not fps:
        return [cut.declared for cut in cuts]
    return [max(1, round(cut.declared * fps)) / fps for cut in cuts]


def _film_fps(
    episode: Path, project_root: Path, cuts: Sequence[Cut], delivery: Optional[Delivery], *, probe: bool
) -> Optional[float]:
    """The film's frame rate: the delivery spec's, else the first video cut's."""

    if delivery is not None and delivery.fps:
        return delivery.fps
    if probe:
        for cut in cuts:
            media = None if cut.still else _resolve_media(episode, project_root, cut.media)
            if media is not None:
                return probe_stream(media)["fps"] or None
    return None


def _timeline(
    cuts: Sequence[Cut], spans: Sequence[float]
) -> list[tuple[Cut, float, float]]:
    """Each cut with its start in the film and its span there."""

    placed: list[tuple[Cut, float, float]] = []
    cursor = 0.0
    for cut, span in zip(cuts, spans):
        placed.append((cut, cursor, span))
        cursor += span
    return placed


def _at(cut: Cut, cursor: float, span: float, seconds: float) -> float:
    """A time written against a cut, in film seconds.

    Inside the cut it keeps its place relative to the cut's rendered length, so
    a window written to end with the cut still does. Before or past the cut --
    a J-cut's start, an L-cut subtitle's end -- it is plain seconds from the
    cut's start, the same clock a voice file plays on.
    """

    if 0 <= seconds <= cut.declared and cut.declared > 0:
        return cursor + seconds * span / cut.declared
    return cursor + seconds


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


def _split_display(
    text: str, limit: int = SUBTITLE_MAX_VISIBLE, keep: Sequence[str] = ()
) -> list[str]:
    """Break a displayed line into one-line pieces of at most `limit` characters.

    Pieces break at the line's own pauses (the full-width spaces, and after ？！)
    and are packed back together while they fit. A single phrase longer than
    the limit is cut into near-equal parts, which is the only place a break
    falls where the screenplay has no pause. No break falls inside a word in
    `keep`: a highlight is looked up in the piece it lands in, and half a word
    matches nothing.
    """

    if _visible(text) <= limit:
        return [text]
    held = {
        at
        for word in keep if word
        for found in re.finditer(re.escape(word), text)
        for at in range(found.start() + 1, found.end())
    }
    phrases: list[tuple[int, int]] = []
    for found in re.finditer(r"[^　？！?!]+[？！?!]*|[？！?!]+", text):
        start, end = found.span()
        if phrases and any(at in held for at in range(phrases[-1][1], start + 1)):
            phrases[-1] = (phrases[-1][0], end)
        else:
            phrases.append((start, end))

    def even_parts(start: int, end: int) -> list[tuple[int, int]]:
        count = _visible(text[start:end])
        if count <= limit:
            return [(start, end)]
        free = [at for at in range(start + 1, end) if at not in held]
        first: Optional[list[tuple[int, int]]] = None
        for parts in range(-(-count // limit), count + 1):
            size = -(-count // parts)
            cuts = [start]
            for index in range(1, parts):
                ideal = start + index * size
                later = [at for at in free if at > cuts[-1]]
                if not later:
                    break
                cuts.append(min(later, key=lambda at: (abs(at - ideal), at)))
            spans = list(zip(cuts, cuts[1:] + [end]))
            if all(_visible(text[a:b]) <= limit for a, b in spans):
                return spans
            first = first or spans
        return first or [(start, end)]

    packed: list[tuple[int, int]] = []
    for start, end in (span for phrase in phrases for span in even_parts(*phrase)):
        # Joining by slicing the line keeps whatever stood between the pieces.
        if packed and _visible(text[packed[-1][0]:end]) <= limit:
            packed[-1] = (packed[-1][0], end)
        else:
            packed.append((start, end))
    return [text[start:end].strip(" 　") for start, end in packed]


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
        # Highlights are matched in their burned form: 「十万，现金」 shows as 「十万　现金」.
        burned = tuple(_display_line(word) for word in words)
        pieces = _split_display(_display_line(text), keep=burned)
        # A line that is all punctuation ("……") has nothing left to show.
        pieces = [piece for piece in pieces if _visible(piece)]
        lost = [word for word in burned if not word or not any(word in p for p in pieces)]
        if lost:
            raise EditError(f"字幕「{text}」的重点词在压制后的字幕里找不到: {lost}")
        total = sum(_visible(piece) for piece in pieces)
        cursor = start
        for piece in pieces:
            length = (end - start) * _visible(piece) / total
            keys = tuple(word for word in burned if word in piece)
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
    for cut, cursor, length in _timeline(cuts, spans):
        for text in sorted(cut.screen_texts, key=lambda item: item.start):
            start = _at(cut, cursor, length, text.start)
            end = _at(cut, cursor, length, text.end)
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


def _placed_sound_effects(cuts: Sequence[Cut], spans: Sequence[float]) -> list[Placed]:
    """Each effect in output seconds, with its path as written."""

    return [
        Placed(max(0.0, _at(cut, cursor, length, effect.start)),
               _at(cut, cursor, length, effect.end) - _at(cut, cursor, length, effect.start),
               effect.path, effect.gain_db, effect.offset)
        for cut, cursor, length in _timeline(cuts, spans)
        for effect in cut.sound_effects
    ]


def _placed_beds(cuts: Sequence[Cut], spans: Sequence[float]) -> list[Placed]:
    """Each 「环境声」 run, looping its file with no break at the cuts it spans.

    A run starts at its line's cut plus 起 and lasts until the next 环境声 line:
    to that line's cut start, or to its 起 when that is later. A negative 起
    therefore overlaps the two rooms across the cut, a sound bridge. It fades
    only at its own two ends.
    """

    lines = [
        (_at(cut, cursor, length, cut.bed.start), cursor, cut.bed)
        for cut, cursor, length in _timeline(cuts, spans) if cut.bed is not None
    ]
    total = sum(spans)
    placed: list[Placed] = []
    for index, (start, _, bed) in enumerate(lines):
        if bed.path is None:
            continue
        end = total if index + 1 == len(lines) else max(lines[index + 1][0], lines[index + 1][1])
        start = max(0.0, start)
        if end - start > TOLERANCE:
            placed.append(Placed(start, end - start, bed.path, bed.gain_db, bed.offset,
                                 loop=True, fade_in=BED_FADE, fade_out=BED_FADE))
    return placed


def _sound_effect_command(
    ffmpeg: str,
    film: Path,
    effects: Sequence[Union[Placed, tuple[Any, ...]]],
    output: Path,
) -> list[str]:
    """Lay each effect, voice and bed into the film's own audio at its output time.

    `normalize=0` keeps the dialogue at its level: amix's default divides every
    input by the input count, and the film would get quieter each time a chime
    is added. A short fade closes each sound so a trimmed tail does not click;
    a bed loops its file and fades in and out only at its own ends.
    """

    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(film)]
    # The film's channel layout is left as it is: forcing mono dialogue up to
    # stereo costs it 3 dB, and the effects are converted to match instead.
    stages = ["[0:a]aformat=sample_rates=48000[a0]"]
    labels = ["[a0]"]
    for index, raw in enumerate(effects, start=1):
        sound = Placed(*raw)
        command += (["-stream_loop", "-1"] if sound.loop else []) + ["-i", str(sound.path)]
        fade_in = min(sound.fade_in, sound.duration / 2)
        fade_out = min(sound.fade_out, sound.duration / 2)
        stages.append(
            f"[{index}:a]atrim=start={sound.offset:.3f}:duration={sound.duration:.3f},asetpts=PTS-STARTPTS,"
            + (f"afade=t=in:st=0:d={fade_in:.3f}," if fade_in else "")
            + f"afade=t=out:st={sound.duration - fade_out:.3f}:d={fade_out:.3f},volume={sound.gain_db:g}dB,"
            "aformat=sample_rates=48000,"
            f"adelay={round(sound.start * 1000)}:all=1[s{index}]"
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


def verify(
    episode: Path, cuts: Sequence[Cut], delivery: Delivery, project_root: Optional[Path] = None
) -> dict[str, Any]:
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
    # The same spans render placed everything on; the film's own rate when no spec states one.
    spans = _film_spans(cuts, delivery.fps or stream["fps"])
    if any(cut.screen_texts or cut.sound_effects for cut in cuts):
        measurements.update(_placements_for_sampling(cuts, spans))
    beds = _placed_beds(cuts, spans)
    if beds:
        measurements["环境声落点"] = [
            {"起": round(bed.start, 2), "止": round(bed.start + bed.duration, 2), "文件": bed.path}
            for bed in beds
        ]
    if any(cut.voices for cut in cuts):
        measurements["配音落点"] = _voice_placements(
            episode, project_root or episode, cuts, spans
        )
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
        placed = _placed_layers(cuts, spans)
        entrances = [] if isinstance(placed, str) else [layer["start"] for layer in placed]
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


def _placed_layers(cuts: Sequence[Cut], spans: Sequence[float]) -> Union[list[dict[str, Any]], str]:
    """The screen text layers, or why they cannot be placed: verify reports, it does not stop."""

    try:
        return _screen_text_layers(cuts, spans)
    except EditError as error:
        return f"未测（{error}）"


def _placements_for_sampling(cuts: Sequence[Cut], spans: Optional[Sequence[float]]) -> dict[str, Any]:
    """Where the screen text and effects landed in the film, from the rendered segments.

    These are the frames and moments to sample; whether the text reads and the
    chime sits right is still for someone to look and listen.
    """

    if spans is None:
        reason = "未测（分段缺失，无法换算成片时间）"
        return {"画面文字落点": reason, "音效落点": reason}
    placed = _placed_layers(cuts, spans)
    return {
        "画面文字落点": placed if isinstance(placed, str) else [
            {
                "起": round(layer["start"], 2),
                "止": round(layer["end"], 2),
                "样式": next(
                    label for label, key in SCREEN_TEXT_STYLES.items() if key == layer["style"]
                ),
                "文字": SCREEN_TEXT_ITEM_SEPARATOR.join(item["text"] for item in layer["items"]),
            }
            for layer in placed
        ],
        "音效落点": _sound_placements(cuts, spans),
    }


def _sound_placements(cuts: Sequence[Cut], spans: Sequence[float]) -> list[dict[str, Any]]:
    return [
        {"起": round(start, 2), "止": round(start + duration, 2), "文件": written}
        for start, duration, written, *_ in _placed_sound_effects(cuts, spans)
    ]


def _voice_placements(
    episode: Path, project_root: Path, cuts: Sequence[Cut], spans: Optional[Sequence[float]]
) -> Union[list[dict[str, Any]], str]:
    """Where each 「配音」 line is heard in the film, for listening back."""

    if spans is None:
        return "未测（分段缺失，无法换算成片时间）"
    try:
        sounds = _voice_sounds(episode, project_root, cuts)
    except EditError as error:
        return f"未测（{error}）"
    return [
        {"起": round(start, 2), "止": round(end, 2), "段": cut.cut_id, "文件": voice.path}
        for start, end, cut, voice in _voice_spans(cuts, sounds, spans)
    ]


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
                probe=_which("ffprobe") is not None, unused=unused, delivery=delivery,
                listen=_which("ffmpeg") is not None,
            )
            payload: dict[str, Any] = {
                "段数": len(cuts),
                "各段时长之和": round(sum(cut.end - cut.start for cut in cuts), 2),
                "目标时长": delivery.target_seconds,
                "未采用镜头": unused,
                "findings": findings,
            }
            notices = move_notices(cuts, _scene_keys(episode, cuts), _film_spans(cuts, delivery.fps))
            if notices:
                payload["提醒"] = notices
            unmeasured = []
            if _which("ffprobe") is None:
                unmeasured.append("区间是否超过素材实际时长（PATH 上没有 ffprobe）")
            if _which("ffmpeg") is None and any(cut.voices for cut in cuts):
                unmeasured.append("配音是否越过成片结尾、是否互相重叠（PATH 上没有 ffmpeg）")
            if unmeasured:
                payload["未测"] = unmeasured
            _emit(payload)
            return 1 if findings else 0
        if arguments.command == "render":
            findings = check_cuts(
                episode, cuts, project_root, probe=True, unused=unused, delivery=delivery
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
        _emit(verify(episode, cuts, delivery, project_root))
        return 0
    except EditError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
