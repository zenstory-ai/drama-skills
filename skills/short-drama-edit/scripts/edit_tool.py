#!/usr/bin/env python3
"""Assemble a short-drama episode from its cut list.

Three subcommands, deliberately separated so a report can never borrow one's
evidence for another's claim:

``check``   parse and cross-check ``剪辑单.md`` against the project. No rendering.
``render``  cut, join, burn subtitles and normalize loudness into 制作成果/成片/.
``verify``  measure an already-rendered film and print the numbers.

``verify`` prints measurements, never verdicts. Whether the film is any good is
a question for review or for the creator, and no number here answers it.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, NamedTuple, Optional, Sequence

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
    "src/Subtitles.tsx",
    "src/font.ts",
)
DEFAULT_REMOTION_WORKSPACE = Path.home() / ".cache" / "short-drama-edit" / "remotion"
REMOTION_COMPOSITION = "Subtitles"
# Remotion composites every frame in a headless browser and defaults its worker
# count to the machine's core count. On a 10-core / 8 GB laptop that is ten
# browsers each holding a full 1080x1920 frame, and a 48-second overlay took the
# machine down. Two workers finish the same job without competing for memory;
# raise it only on a machine with headroom to spare.
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
TOLERANCE = 0.005


class EditError(Exception):
    """A defect in the cut list or its inputs, reported rather than raised through."""


class Cut(NamedTuple):
    cut_id: str
    title: str
    motion: str
    media: str
    start: float
    end: float
    declared: float
    subtitles: tuple[tuple[Optional[float], Optional[float], str], ...]
    picture: dict[str, float]
    line_number: int


class Delivery(NamedTuple):
    target_seconds: Optional[float]
    loudness_lufs: Optional[float]
    burn_subtitles: bool
    frame_size: Optional[tuple[int, int]]
    fps: Optional[float]


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
        elif name == "画幅与帧率":
            size = re.search(r"([0-9]{2,5})\s*[×x*]\s*([0-9]{2,5})", value)
            if size:
                frame_size = (int(size.group(1)), int(size.group(2)))
            rate = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*fps", value, re.I)
            if rate:
                fps = float(rate.group(1))
    return Delivery(target, loudness, burn, frame_size, fps)


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
    if picture_raw is not None:
        text, where = picture_raw
        if text.strip() not in {"", "无", "不校"}:
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
                    "只认「亮度 <数>」「饱和 <数>」「色温 <数>」，不需要校正时写「无」"
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
    )


def _parse_subtitles(
    fields: dict[str, tuple[str, int]], *, cut_id: str, line: int
) -> tuple[tuple[Optional[float], Optional[float], str], ...]:
    """Read every subtitle a cut declares, in written order.

    A shot is not one line. The exchange "就是什么 / 就是少了点东西 / 少了什么" is a
    single over-shoulder shot carrying three, and a cut list that can hold only
    one of them silently drops the other two — the film then plays lines that
    never reach the screen, and nothing reports it.
    """

    numbered: list[tuple[int, str, int]] = []
    plain: Optional[tuple[str, int]] = None
    for key, (value, where) in fields.items():
        match = SUBTITLE_FIELD.match(key.strip())
        if not match:
            continue
        if match.group(1) is None:
            plain = (value, where)
        else:
            numbered.append((int(match.group(1)), value, where))

    if numbered and plain is not None:
        raise EditError(
            f"{CUT_LIST_NAME}:{line}: {cut_id} 同时写了「字幕」和「字幕 N」；"
            "一段用一种写法——一句用「字幕」，多句全部编号"
        )

    if numbered:
        numbered.sort()
        expected = list(range(1, len(numbered) + 1))
        if [item[0] for item in numbered] != expected:
            raise EditError(
                f"{CUT_LIST_NAME}:{line}: {cut_id} 的字幕编号要从 1 连续排到 "
                f"{len(numbered)}，当前是 {[item[0] for item in numbered]}"
            )
        cues: list[tuple[Optional[float], Optional[float], str]] = []
        for index, value, where in numbered:
            found = SUBTITLE_CUE.match(value)
            if not found:
                raise EditError(
                    f"{CUT_LIST_NAME}:{where}: {cut_id} 的「字幕 {index}」要写成"
                    "「<起>-<止> <台词>」，多句必须各自带时间"
                )
            cues.append((float(found.group(1)), float(found.group(2)), found.group(3)))
        for earlier, later in zip(cues, cues[1:]):
            if later[0] is not None and earlier[1] is not None and later[0] < earlier[1]:
                raise EditError(
                    f"{CUT_LIST_NAME}:{line}: {cut_id} 的字幕时间重叠：两句不能同时在屏上"
                )
        return tuple(cues)

    if plain is None or plain[0].strip() == "无":
        return ()
    window_raw = fields.get("字幕时间")
    if window_raw is None:
        return ((None, None, plain[0].strip()),)
    found = SUBTITLE_WINDOW.match(window_raw[0])
    if not found:
        raise EditError(
            f"{CUT_LIST_NAME}:{window_raw[1]}: {cut_id} 的字幕时间要写成「起-止」秒数"
        )
    return ((float(found.group(1)), float(found.group(2)), plain[0].strip()),)


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


def check_cuts(
    episode: Path, cuts: Sequence[Cut], project_root: Path, *, probe: bool
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
    else:
        findings.append(f"没有 {motion_path}，来源 MOTION 无法核对")

    screenplay = ""
    screenplay_path = episode / SCREENPLAY_DOCUMENT
    if screenplay_path.is_file():
        screenplay = screenplay_path.read_text(encoding="utf-8")

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
            available = probe_duration(media)
            if cut.end > available + TOLERANCE:
                findings.append(
                    f"{CUT_LIST_NAME}:{cut.line_number}: {cut.cut_id} 出点 {cut.end:.2f} "
                    f"超过素材实际时长 {available:.2f}"
                )
        for window_start, window_end, text in cut.subtitles:
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

    findings.extend(_overlap_findings(cuts))
    findings.extend(_stale_window_findings(episode, project_root, cuts))
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
        if not any(start is not None for start, _, _ in cut.subtitles):
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
                f"（{cut.media}）；这一段的字幕时间是按旧素材的发声区间反推的，"
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

    segments: list[Path] = []
    spans: list[float] = []
    for cut in cuts:
        media = _resolve_media(episode, project_root, cut.media)
        if media is None:
            raise EditError(f"{cut.cut_id} 的素材不存在: {cut.media}")
        segment = segments_root / f"{cut.cut_id}.mp4"
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{cut.start:.3f}", "-t", f"{cut.end - cut.start:.3f}", "-i", str(media),
        ]
        match = _shot_match_filter(cut)
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

        filters: list[str] = []
        subtitle_path = None
        styled_path = None
        overlay_path = None
        if burn_subtitles and any(cut.subtitles for cut in cuts):
            canvas = probe_stream(segments[0])
            cues = _subtitle_cues(cuts, spans)
            subtitle_path = output_root / "字幕.srt"
            subtitle_path.write_text(_build_srt(cues), encoding="utf-8")
            if renderer == "remotion":
                overlay_path = _render_remotion_overlay(
                    output_root, cues, canvas, sum(spans), remotion_workspace,
                    concurrency=remotion_concurrency,
                )
            else:
                styled = styled_path = output_root / "字幕.ass"
                styled.write_text(
                    _build_ass(cues, canvas["width"] or 1080, canvas["height"] or 1920),
                    encoding="utf-8",
                )
                escaped = (
                    str(styled).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
                )
                filters.append(f"ass='{escaped}'")

        final = output_root / "成片.mp4"
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(joined)]
        if overlay_path is not None:
            # VP8 carries its alpha as WebM block additions, so the decoder has
            # to be named: the default one drops it and the overlay arrives as
            # an opaque black rectangle.
            command += ["-c:v", "libvpx", "-i", str(overlay_path)]
            command += [
                "-filter_complex",
                "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
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
            command += ["-c:a", "aac", "-b:a", "192k"]
        else:
            command += ["-c:a", "copy"]
        command.append(str(final))
        _run(command)

    return {
        "成片": str(final),
        "分段": [str(segment) for segment in segments],
        "字幕": str(subtitle_path) if subtitle_path else None,
        "压制字幕": str(styled_path) if styled_path else None,
        "字幕叠层": str(overlay_path) if overlay_path else None,
        "字幕渲染": renderer if subtitle_path else None,
        "段数": len(segments),
        "各段时长之和": round(sum(cut.end - cut.start for cut in cuts), 2),
    }


def _shot_match_filter(cut: Cut) -> str:
    """Match one cut to its neighbours, using only what the cut list declared.

    Generated shots drift: two takes of the same person at the same table come
    back a stop apart and half a step of white balance away from each other, and
    the join reads as a mistake rather than a cut. The correction stays a stated
    creator decision — the tool never measures a clip and adjusts it on its own,
    because a correction nobody wrote down is one nobody can review.
    """

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


def _loudnorm_filter(ffmpeg: str, media: Path, target: float) -> str:
    """Two-pass EBU R128.

    One pass is a dynamic normalizer that lands several dB from the target; the
    delivered loudness would then be a number nobody chose. Measure first, feed
    the measurement back, and the second pass is linear.
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
    (workspace / "src").mkdir(parents=True, exist_ok=True)
    for name in REMOTION_SOURCE_FILES:
        source = REMOTION_SOURCE / name
        if not source.is_file():
            raise EditError(f"技能里缺少 Remotion 源文件: {name}")
        shutil.copyfile(source, workspace / name)
    return workspace


def _render_remotion_overlay(
    output_root: Path,
    cues: Sequence[tuple[float, float, str]],
    canvas: dict[str, Any],
    duration: float,
    workspace_root: Path,
    concurrency: int = DEFAULT_REMOTION_CONCURRENCY,
) -> Path:
    """Render the subtitle layer as a transparent video with Remotion.

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
    if not (workspace / "node_modules").is_dir():
        raise EditError(
            f"Remotion 还没安装。先运行一次：\n"
            f"  cd {workspace} && npm install\n"
            "或改用默认的 ffmpeg 字幕（去掉 --subtitles remotion）。\n"
            "注意 Remotion 有自己的许可证：个人与小团队免费，超出规模需要商业授权；"
            "本工具不会替你安装它。"
        )
    npx = _which("npx")
    if npx is None:
        raise EditError(
            "PATH 上没有 npx，无法运行 Remotion；装好 Node.js，或改用默认的 ffmpeg 字幕。"
        )
    props = output_root / "字幕.props.json"
    props.write_text(
        json.dumps(
            {
                "cues": [
                    {"start": round(start, 3), "end": round(end, 3), "text": text}
                    for start, end, text in cues
                ],
                "width": canvas["width"] or 1080,
                "height": canvas["height"] or 1920,
                "fps": canvas["fps"] or 24,
                "durationInSeconds": round(duration, 3),
                "fontScale": 0.034,
                "bottomScale": 0.055,
                "fontFamily": (
                    '"PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC", '
                    '"Microsoft YaHei", sans-serif'
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    overlay = output_root / "字幕叠层.webm"
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
) -> list[tuple[float, float, str]]:
    """Place each line in output time, measuring the segments that were written.

    A segment lands on a frame boundary, so it is a few milliseconds longer than
    the cut list declares. Accumulating the declared numbers instead drifts —
    a third of a second by the end of eight cuts here — and the subtitle leaves
    before the actor stops speaking. The rendered files are the timeline.
    """

    cues: list[tuple[float, float, str]] = []
    cursor = 0.0
    for cut, span in zip(cuts, spans):
        declared = cut.end - cut.start
        # The windows were authored against the declared span; hold them in
        # place proportionally rather than letting the tail slip out.
        scale = span / declared if declared > 0 else 1.0
        for window_start, window_end, text in cut.subtitles:
            start = 0.0 if window_start is None else window_start
            end = declared if window_end is None else window_end
            cues.append((cursor + start * scale, cursor + end * scale, text))
        cursor += span
    return cues


def _build_srt(cues: Sequence[tuple[float, float, str]]) -> str:
    """The text is the screenplay's, verbatim; only the timing is ours."""

    return "\n".join(
        f"{index}\n{_timecode(start)} --> {_timecode(end)}\n{text}\n"
        for index, (start, end, text) in enumerate(cues, start=1)
    )


def _build_ass(
    cues: Sequence[tuple[float, float, str]], width: int, height: int
) -> str:
    """Author the ASS directly so the type size is stated in frame pixels.

    Letting ffmpeg convert the SRT hands libass a 384-high canvas, and every
    size in the style is then scaled by height/384 on the way to the frame.
    Computing a FontSize from the real height on top of that scales it twice:
    the first attempt here produced type a third of the frame wide, sitting in
    the middle of the picture with both ends of the line cut off. Declaring
    PlayRes as the frame removes the conversion, so one unit is one pixel.
    """

    font_size = max(18, round(height * 0.034))
    outline = max(2, round(height * 0.0022))
    margin_v = max(24, round(height * 0.055))
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
        f"&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,{outline},1,2,"
        f"{margin_h},{margin_h},{margin_v},1\n"
        "\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    lines = [
        f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},正片,,0,0,0,,{_ass_text(text)}"
        for start, end, text in cues
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
    measurements["台词完整性"] = "未测（本工具不做转写；在成片上转写后逐句对《剧本.md》原文）"
    measurements["边界帧"] = "未测（抽剪辑点前后各一帧目视核对黑场/白场/半渲染帧）"
    return measurements


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
                episode, cuts, project_root, probe=_which("ffprobe") is not None
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
            findings = check_cuts(episode, cuts, project_root, probe=True)
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
