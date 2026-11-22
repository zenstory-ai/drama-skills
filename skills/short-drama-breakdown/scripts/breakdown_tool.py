#!/usr/bin/env python3
"""Measure reference and own video episodes on one deterministic yardstick.

Subcommands, each printing or writing measurements and never verdicts:

``measure``     probe reference (or own) video files: duration, picture size,
                detected cut points, shot lengths and a contact sheet with one
                frame per detected shot.
``transcript``  attach a timed transcript (SRT, WebVTT or JSON segments) to a
                measured episode, so speech numbers come from real timings.
``profile``     aggregate measured episodes per series into one table: the
                opening episodes apart from the rest, medians and the length
                regime.
``audio``       voiced intervals (silence detection) and loudness of an
                episode's sound track, so dialogue rhythm can be looked at
                before any transcript exists.
``shots``       cut one small clip and a first, middle and last frame per
                measured shot, with low-threshold candidate cuts inside each
                shot, for the per-shot reconstruction pass.
``subtitles``   when each burned-in subtitle appears and changes, with one
                crop per subtitle to read: line timing for a reconstruction.
``subtitle-sheet``  frames most covered by outlined text, with a ratio grid,
                and how often each height band shows and changes such text,
                so the agent can mark where a series puts its subtitles.

Cut detection is a frame-difference threshold. It misses slow dissolves and
counts flashes, whip pans and particle effects as cuts; a transcript counts
narration, system voice and dialogue alike; silence detection cannot tell
speech from music. The numbers say where to look. Whether a reference choice
suits this project is the creator's call. Nothing here watches or listens with
a model; that pass belongs to the agent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "short-drama-breakdown needs Python {}.{} or newer; this interpreter is {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )

MEASURE_SUFFIX = ".measure.json"
DEFAULT_SCENE_THRESHOLD = 0.28
# A detected cut this close to either end is the encoder settling or a fade
# tail, not a shot.
EDGE_IGNORE_SECONDS = 0.3
LONG_SHOT_SECONDS = 4.0
# Cue ends this far past the picture are rounding, not a recognition error.
OVERRUN_TOLERANCE_SECONDS = 0.5
# Episodes after the opening ones count as fixed length when the 10th and
# 90th percentiles sit this close.
FIXED_LENGTH_SPREAD_SECONDS = 3.0
# Strongest first: 第N集, then an EPISODE/EP/E marker that does not sit inside
# a word (``Love2026_EP001``, ``Season2_Episode03``), then a 第N that is not a
# season or a part.
EPISODE_MARKERS = (
    re.compile(r"第\s*0*(\d{1,4})\s*[集话話]"),
    re.compile(
        r"(?<![A-Za-z])(?:(?:EPISODE|EP)[\s._-]*|E\s*)0*(\d{1,4})(?!\d)",
        re.IGNORECASE,
    ),
    re.compile(r"第\s*0*(\d{1,4})(?![\d季部])"),
)
EPISODE_BARE = re.compile(r"(?<!\d)0*(\d{1,4})(?!\d)")
SRT_TIME = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})"
)
VTT_TIME = re.compile(
    r"(?:(\d+):)?(\d{2}):(\d{2})\.(\d{1,3})\s*-->\s*(?:(\d+):)?(\d{2}):(\d{2})\.(\d{1,3})"
)
AUDIO_SUFFIX = ".audio.json"
DEFAULT_SILENCE_DB = -35.0
DEFAULT_SILENCE_SECONDS = 0.3
# Shot clips for the per-shot pass: the short side is at most this many pixels.
SHOT_CLIP_SHORT_SIDE = 720
# A seek returns the first frame at or after the moment, so the last frame of
# a shot is sought one and a half frame durations before its end.
LAST_FRAME_LEAD_FRAMES = 1.5
SUBTITLE_SUFFIX = ".subtitles.json"
# The bottom-centre strip where burned-in subtitles sit: left, top, right, bottom.
DEFAULT_SUBTITLE_BAND = (0.08, 0.78, 0.92, 0.99)
DEFAULT_SUBTITLE_FPS = 10.0
# Subtitle glyphs are near-white; outlines and most backgrounds are darker.
DEFAULT_SUBTITLE_BRIGHT = 225
SUBTITLE_SAMPLE_WIDTH = 720
# Glyph outlines: a pixel this dark exactly this many pixels left or right of a bright one.
SUBTITLE_DARK = 80
SUBTITLE_OUTLINE_REACH = 2
# A frame shows text when this share of the band is bright; single-character cues ("是", "嗯") are small.
SUBTITLE_MIN_SHARE = 0.0007
# The text changed when this share of its bright pixels moved between frames.
SUBTITLE_CHANGE_SHARE = 0.5
SUBTITLE_MIN_SECONDS = 0.2
SUBTITLE_SHEET_PAGE_SIZE = 40
# --color: a pixel is the glyph colour when no channel is further off than this.
DEFAULT_COLOR_TOLERANCE = 60
# Calibration sheet: frames scanned per second, frames shown, picture width,
# and the minimum spacing between shown frames.
SUBTITLE_SHEET_FPS = 2.0
SUBTITLE_SHEET_FRAMES = 8
SUBTITLE_SHEET_WIDTH = 640
SUBTITLE_SHEET_SPACING_SECONDS = 3.0
# Row profile: the frame height in this many bands; a band shows glyphs in a
# frame when one of its rows has at least this share of its width outlined.
SUBTITLE_ROW_BANDS = 50
SUBTITLE_ROW_MIN_SHARE = 0.01
# Measured shots: frame-difference candidates at this lower threshold are
# listed inside each shot for the per-shot pass to confirm.
DEFAULT_INNER_THRESHOLD = 0.1
TAIL_CANDIDATE_THRESHOLD = 0.05
# A candidate this close to a shot's edge is the measured cut itself.
INNER_EDGE_SECONDS = 0.1
# Candidates closer than this belong to one flicker run.
CANDIDATE_RUN_SECONDS = 0.3

_GLYPH_5X7: Dict[str, Tuple[str, ...]] = {
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    ":": ("00000", "00100", "00100", "00000", "00100", "00100", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


class BreakdownError(Exception):
    pass


# ---------------------------------------------------------------- media


def _require(name: str) -> str:
    found = shutil.which(name)
    if found is None and os.environ.get("PATH", ""):
        for folder in (
            Path.home() / ".local" / "bin",
            Path("/opt/homebrew/bin"),
            Path("/usr/local/bin"),
        ):
            candidate = shutil.which(name, path=str(folder))
            if candidate is not None:
                return candidate
    if found is None:
        raise BreakdownError(
            f"PATH 上没有 {name}。请先安装 ffmpeg 与 ffprobe 后再测量真实视频。"
        )
    return found


def _format_stamp_clock(seconds: float) -> str:
    total = max(0.0, float(seconds))
    minutes = int(total // 60)
    rem = total - minutes * 60
    if rem >= 59.95:
        minutes += 1
        rem = 0.0
    return f"{minutes:02d}:{rem:04.1f}"


def _draw_bitmap_text(
    buf: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    text: str,
    scale: int = 2,
    color: bytes = b"\xff\xd4\x00",
) -> None:
    stride = width * 3
    cursor_x = x
    for char in text:
        glyph = _GLYPH_5X7.get(char, _GLYPH_5X7[" "])
        for gy, row_bits in enumerate(glyph):
            for gx, bit in enumerate(row_bits):
                if bit != "1":
                    continue
                for dy in range(scale):
                    py = y + gy * scale + dy
                    if not 0 <= py < height:
                        continue
                    row_offset = py * stride
                    for dx in range(scale):
                        px = cursor_x + gx * scale + dx
                        if 0 <= px < width:
                            at = row_offset + px * 3
                            buf[at : at + 3] = color
        cursor_x += 6 * scale


def _write_ppm_jpeg(ffmpeg: str, width: int, height: int, rgb: bytes, out: Path) -> bool:
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    if out.exists():
        out.unlink()
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "image2pipe",
            "-vcodec",
            "ppm",
            "-i",
            "-",
            "-frames:v",
            "1",
            "-q:v",
            "3",
            "-y",
            str(out),
        ],
        input=header + rgb,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0 and out.is_file()


def probe(video: Path) -> Dict[str, Any]:
    result = subprocess.run(
        [_require("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:stream_tags=rotate:stream_side_data=rotation:format=duration",
         "-of", "json", str(video)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise BreakdownError(f"ffprobe 读不出 {video}: {result.stderr.strip()}")
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams") or [{}]
    try:
        duration = float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError) as error:
        raise BreakdownError(f"{video} 没有可读时长") from error
    width, height = streams[0].get("width"), streams[0].get("height")
    # Phone footage is often stored landscape with a display rotation; report
    # the picture as shown, as the contact sheet frames are.
    rotation = (streams[0].get("tags") or {}).get("rotate")
    for side in streams[0].get("side_data_list") or []:
        rotation = side.get("rotation", rotation)
    try:
        quarter_turn = int(float(rotation or 0)) % 180 == 90
    except (TypeError, ValueError):
        quarter_turn = False
    if quarter_turn:
        width, height = height, width
    return {"duration": round(duration, 3), "width": width, "height": height}


def detect_cuts(video: Path, threshold: float) -> List[float]:
    result = subprocess.run(
        # The same first video track probe() reads, whatever ffmpeg would pick.
        [_require("ffmpeg"), "-hide_banner", "-nostats", "-i", str(video), "-map", "0:v:0",
         "-vf", f"scale=256:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise BreakdownError(f"ffmpeg 切点检测失败 {video}: {result.stderr.strip()[-300:]}")
    return [round(float(value), 3) for value in re.findall(r"pts_time:([\d.]+)", result.stderr)]


def shot_lengths(duration: float, cuts: Iterable[float]) -> List[float]:
    inner = sorted(
        cut for cut in cuts if EDGE_IGNORE_SECONDS < cut < duration - EDGE_IGNORE_SECONDS
    )
    bounds = [0.0, *inner, duration]
    return [round(bounds[index + 1] - bounds[index], 3) for index in range(len(bounds) - 1)]


def _detect_tail_candidates(
    video: Path, start: float, duration: float, threshold: float = TAIL_CANDIDATE_THRESHOLD
) -> List[float]:
    if duration - start <= 1.5:
        return []
    result = subprocess.run(
        [
            _require("ffmpeg"),
            "-hide_banner",
            "-nostats",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(video),
            "-map",
            "0:v:0",
            "-vf",
            f"scale=256:-2,select='gt(scene,{threshold})',showinfo",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    raw = [round(start + float(value), 3) for value in re.findall(r"pts_time:([\d.]+)", result.stderr)]
    return [
        run["at"]
        for run in candidate_runs(
            [cut for cut in raw if start + INNER_EDGE_SECONDS < cut < duration - INNER_EDGE_SECONDS]
        )
    ]


def contact_sheet(video: Path, lengths: Sequence[float], out: Path, columns: int = 8) -> None:
    if not lengths:
        return
    ffmpeg = _require("ffmpeg")
    info = probe(video)
    src_w = int(info.get("width") or 320)
    src_h = int(info.get("height") or 180)
    tile_w = 320
    tile_h = max(36, (int(round(tile_w * src_h / max(1, src_w))) // 2) * 2)
    frame_bytes = tile_w * tile_h * 3
    total = sum(lengths)
    digits = max(2, len(str(len(lengths))))
    moments: List[Tuple[float, str]] = []
    if lengths[0] >= 2.0:
        open_at = min(0.2, lengths[0] / 4)
        moments.append((open_at, f"OPEN {open_at:.1f}s"))
    start = 0.0
    for index, length in enumerate(lengths, 1):
        middle = start + length / 2
        moments.append((middle, f"S{index:0{digits}d} {start:.1f}-{start + length:.1f}s"))
        start += length
    if lengths[-1] >= 2.0:
        tail_at = max(0.0, total - 0.3)
        moments.append((tail_at, f"END {tail_at:.1f}s"))

    tiles: List[bytes] = []
    for moment, label in moments:
        raw = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-ss",
                f"{moment:.3f}",
                "-i",
                str(video),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-vf",
                f"scale={tile_w}:{tile_h}",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            capture_output=True,
            check=False,
        ).stdout
        if len(raw) != frame_bytes:
            continue
        tile = bytearray(raw)
        bar_h = min(tile_h, 18)
        bar_w = min(tile_w, 8 + len(label) * 12)
        for py in range(bar_h):
            row_start = py * tile_w * 3
            for px in range(bar_w):
                at = row_start + px * 3
                tile[at] //= 3
                tile[at + 1] //= 3
                tile[at + 2] //= 3
        _draw_bitmap_text(tile, tile_w, tile_h, 4, 2, label, scale=2)
        tiles.append(bytes(tile))
    if not tiles:
        return
    cols = min(columns, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    pad = 2
    grid_w = cols * tile_w + (cols - 1) * pad
    grid_h = rows * tile_h + (rows - 1) * pad
    canvas = bytearray(grid_w * grid_h * 3)
    for idx, tile_bytes in enumerate(tiles):
        r, c = divmod(idx, cols)
        ox = c * (tile_w + pad)
        oy = r * (tile_h + pad)
        for py in range(tile_h):
            dst = ((oy + py) * grid_w + ox) * 3
            src = py * tile_w * 3
            canvas[dst : dst + tile_w * 3] = tile_bytes[src : src + tile_w * 3]
    _write_ppm_jpeg(ffmpeg, grid_w, grid_h, bytes(canvas), out)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def measure_video(video: Path, out_dir: Path, threshold: float, sheet: bool) -> Path:
    info = probe(video)
    cuts = detect_cuts(video, threshold)
    lengths = shot_lengths(info["duration"], cuts)
    inner_cuts = [cut for cut in cuts if EDGE_IGNORE_SECONDS < cut < info["duration"] - EDGE_IGNORE_SECONDS]
    last_start = inner_cuts[-1] if inner_cuts else 0.0
    tail_candidates = _detect_tail_candidates(video, last_start, info["duration"])
    record = {
        "source": video.name,
        "episode": episode_number(video.stem),
        "kind": "footage",
        **info,
        "source_sha256": file_sha256(video),
        "scene_threshold": threshold,
        "cuts": inner_cuts,
        "shot_seconds": lengths,
        "tail_candidate_cuts": tail_candidates,
        "segments": None,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{video.stem}{MEASURE_SUFFIX}"
    if target.is_file():
        # Re-measuring the same file (a new threshold, a fresh sheet) keeps the
        # transcript already attached; a replaced cut needs its own transcript.
        earlier = json.loads(target.read_text(encoding="utf-8"))
        if earlier.get("segments") is not None:
            same = (earlier.get("source") == video.name
                    and earlier.get("source_sha256") == record["source_sha256"])
            if same:
                record["segments"] = earlier["segments"]
                record["transcript_source"] = earlier.get("transcript_source")
            else:
                print(f"注意：{video.name} 和上次测量的不是同一个文件，之前挂的转写已清除，请重新挂接",
                      file=sys.stderr)
    target.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    if sheet:
        contact_sheet(video, lengths, out_dir / f"{video.stem}.sheet.jpg")
    return target


# ----------------------------------------------------------------- audio


def has_audio(video: Path) -> bool:
    result = subprocess.run(
        [_require("ffprobe"), "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "json", str(video)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise BreakdownError(f"ffprobe 读不出 {video}: {result.stderr.strip()}")
    return bool(json.loads(result.stdout or "{}").get("streams"))


def audio_end(video: Path) -> Optional[float]:
    """Where the first audio stream stops, or ``None`` when the container does not say."""

    result = subprocess.run(
        [_require("ffprobe"), "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=start_time,duration", "-of", "json", str(video)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise BreakdownError(f"ffprobe 读不出 {video}: {result.stderr.strip()}")
    streams = json.loads(result.stdout or "{}").get("streams") or []
    try:
        stream = streams[0]
        return float(stream.get("start_time") or 0.0) + float(stream["duration"])
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def voiced_intervals(log: str, duration: float) -> List[List[float]]:
    """The complement of ffmpeg ``silencedetect``'s silences inside the picture."""

    silences: List[List[float]] = []
    for kind, value in re.findall(r"silence_(start|end):\s*(-?[\d.]+)", log):
        moment = min(max(float(value), 0.0), duration)
        if kind == "start":
            silences.append([moment, duration])
        elif silences:
            silences[-1][1] = moment
        else:
            # A silence already running when the track starts.
            silences.append([0.0, moment])
    voiced: List[List[float]] = []
    clock = 0.0
    for start, end in silences:
        if start > clock:
            voiced.append([round(clock, 3), round(start, 3)])
        clock = max(clock, end)
    if clock < duration:
        voiced.append([round(clock, 3), round(duration, 3)])
    return voiced


def loudness_summary(log: str) -> Dict[str, Optional[float]]:
    """Integrated loudness, loudness range and true peak from ``ebur128``'s summary."""

    summary = log.rsplit("Summary:", 1)[1] if "Summary:" in log else ""

    def number(pattern: str) -> Optional[float]:
        found = re.search(pattern, summary)
        value = float(found.group(1)) if found else None
        # A digitally silent track peaks at -inf, which strict JSON cannot hold.
        return value if value is not None and math.isfinite(value) else None

    return {"integrated_lufs": number(r"\bI[:]\s+(-?[\d.]+)\s+LUFS"),
            "loudness_range_lu": number(r"LRA:\s+(-?[\d.]+)\s+LU"),
            "true_peak_dbfs": number(r"Peak:\s+(-?[\d.]+|-inf)\s+dBFS")}


def measure_audio(video: Path, out_dir: Path, noise_db: float, min_silence: float) -> Path:
    info = probe(video)
    duration = info["duration"]
    record: Dict[str, Any] = {
        "source": video.name,
        "episode": episode_number(video.stem),
        "duration": duration,
        "source_sha256": file_sha256(video),
        "evidence": "measured",
        "method": {"silence_noise_db": noise_db, "silence_min_seconds": min_silence},
        "has_audio": has_audio(video),
        "blind_spot": "有声区间不分对白、旁白、配乐与音效；整段配乐铺底时几乎全程算有声",
    }
    if record["has_audio"]:
        result = subprocess.run(
            [_require("ffmpeg"), "-hide_banner", "-nostats", "-i", str(video), "-map", "0:a:0",
             "-af", f"silencedetect=noise={noise_db}dB:d={min_silence},ebur128=peak=true", "-f", "null", "-"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            raise BreakdownError(f"ffmpeg 读音轨失败 {video}: {result.stderr.strip()[-300:]}")
        # Past the end of a shorter audio track there is no sound, not unbroken voice.
        end = audio_end(video)
        voiced = voiced_intervals(result.stderr, min(duration, end) if end else duration)
        record.update(loudness_summary(result.stderr))
    else:
        voiced = []
        record.update(integrated_lufs=None, loudness_range_lu=None, true_peak_dbfs=None)
    seconds = round(sum(end - start for start, end in voiced), 3)
    record.update(voiced=voiced, voiced_seconds=seconds,
                  voiced_share=round(seconds / duration, 3) if duration else None)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{video.stem}{AUDIO_SUFFIX}"
    target.write_text(json.dumps(record, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    return target


# ----------------------------------------------------------------- shots


def measured_shots(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Shots between a measure's cuts, numbered ``S01`` onward."""

    duration = float(record["duration"])
    bounds = [0.0, *sorted(record.get("cuts") or []), duration]
    width = max(2, len(str(len(bounds) - 1)))
    return [{"id": f"S{index + 1:0{width}d}", "start": round(bounds[index], 3), "end": round(bounds[index + 1], 3)}
            for index in range(len(bounds) - 1) if bounds[index + 1] > bounds[index]]


def candidate_runs(cuts: Sequence[float], gap: float = CANDIDATE_RUN_SECONDS) -> List[Dict[str, Any]]:
    """Candidates closer together than ``gap`` are one run: a flash, a particle
    burst or a fast pan flickers across several frames, a hard cut is one."""

    runs: List[Dict[str, Any]] = []
    for cut in sorted(cuts):
        if runs and cut - runs[-1]["last"] < gap:
            runs[-1]["last"] = cut
            runs[-1]["frames"] += 1
        else:
            runs.append({"at": cut, "last": cut, "frames": 1})
    return [{"at": run["at"], "until": run["last"], "frames": run["frames"]} for run in runs]


def video_timing(video: Path) -> Tuple[float, Optional[float]]:
    """Frame rate and the video stream's own duration (a longer audio track
    stretches the container's)."""

    result = subprocess.run(
        [_require("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=avg_frame_rate,r_frame_rate,duration", "-of", "json", str(video)],
        capture_output=True, text=True, check=False,
    )
    stream: Dict[str, Any] = {}
    if result.returncode == 0:
        try:
            stream = (json.loads(result.stdout or "{}").get("streams") or [{}])[0]
        except ValueError:
            stream = {}
    fps = 0.0
    for key in ("avg_frame_rate", "r_frame_rate"):
        top, _, bottom = str(stream.get(key) or "0/0").partition("/")
        try:
            fps = float(top) / float(bottom or 1)
        except (ValueError, ZeroDivisionError):
            fps = 0.0
        if fps > 0:
            break
    try:
        length: Optional[float] = float(stream["duration"])
    except (KeyError, TypeError, ValueError):
        length = None
    return (fps if fps > 0 else 25.0), length


def _extract_frame(ffmpeg: str, video: Path, moment: float, vf: str, target: Path) -> bool:
    """One frame at ``moment``; a stale file from an earlier run never stands in."""

    if target.exists():
        target.unlink()
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", f"{moment:.3f}", "-i", str(video), "-map", "0:v:0",
         "-frames:v", "1", "-vf", vf, "-y", str(target)],
        capture_output=True, check=False,
    )
    return result.returncode == 0 and target.is_file()


SHOT_OUTPUT = re.compile(r"S\d{2,}(?:-(?:first|mid|last)\.jpg|\.mp4)")
SUBTITLE_CROP = re.compile(r"T\d{3,}\.png")


def _clear(folder: Path, written: "re.Pattern[str]") -> None:
    """Remove files an earlier run of this tool wrote, matched by exact name."""

    for stale in folder.iterdir():
        if stale.is_file() and not stale.is_symlink() and written.fullmatch(stale.name):
            stale.unlink()


def _refuse_source_folder(video: Path, out_dir: Path) -> None:
    folder = out_dir.resolve()
    source = video.resolve().parent
    if folder == source or folder in source.parents:
        raise BreakdownError(f"输出目录 {out_dir} 是原片所在目录或它的上级；换一个单独的目录")


def cut_shots(video: Path, measure: Path, out_dir: Path,
              inner_threshold: Optional[float] = DEFAULT_INNER_THRESHOLD) -> Path:
    record = json.loads(measure.read_text(encoding="utf-8"))
    if record.get("kind", "footage") != "footage" or record.get("duration") is None:
        raise BreakdownError(f"{measure} 不是成片的测量结果；shots 只按 measure 测出的切点切")
    expected = record.get("source_sha256")
    if expected and file_sha256(video) != expected:
        raise BreakdownError(f"{video.name} 和 {measure.name} 测量的不是同一个文件；先对这个文件重新 measure")
    ffmpeg = _require("ffmpeg")
    side = SHOT_CLIP_SHORT_SIDE
    scale = (f"scale='if(gt(iw,ih),-2,trunc(min({side},iw)/2)*2)':"
             f"'if(gt(iw,ih),trunc(min({side},ih)/2)*2,-2)'")
    _refuse_source_folder(video, out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _clear(out_dir, SHOT_OUTPUT)
    shots = measured_shots(record)
    fps, video_length = video_timing(video)
    picture_end = min(float(record["duration"]), video_length) if video_length else float(record["duration"])
    if shots and shots[-1]["end"] > picture_end > shots[-1]["start"]:
        # A longer audio track stretches the container; the last shot ends with the picture.
        shots[-1]["end"] = round(picture_end, 3)
    measured = record.get("scene_threshold")
    candidates: List[float] = []
    if inner_threshold is not None and (not isinstance(measured, (int, float)) or inner_threshold < measured):
        candidates = detect_cuts(video, inner_threshold)
    for shot in shots:
        start, end = shot["start"], shot["end"]
        clip = f"{shot['id']}.mp4"
        result = subprocess.run(
            [ffmpeg, "-v", "error", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{end - start:.3f}",
             "-map", "0:v:0", "-map", "0:a:0?", "-vf", scale, "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", "-y",
             str(out_dir / clip)],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            raise BreakdownError(f"ffmpeg 切镜失败 {shot['id']}: {result.stderr.strip()[-300:]}")
        frames = {}
        moments = {"first": start, "mid": (start + end) / 2,
                   "last": max(start, min(end, picture_end) - LAST_FRAME_LEAD_FRAMES / fps)}
        for name, moment in moments.items():
            frame = f"{shot['id']}-{name}.jpg"
            frames[name] = frame if _extract_frame(ffmpeg, video, moment, scale, out_dir / frame) else None
        inside = candidate_runs([cut for cut in candidates
                                 if start + INNER_EDGE_SECONDS < cut < end - INNER_EDGE_SECONDS])
        shot.update(seconds=round(end - start, 3), clip=clip, frames=frames, candidate_cuts=inside)
    manifest = {
        "source": record.get("source", video.name),
        "source_sha256": expected or file_sha256(video),
        "measure": measure.name,
        "scene_threshold": record.get("scene_threshold"),
        "inner_threshold": inner_threshold,
        "duration": record["duration"],
        "evidence": "measured",
        "note": ("镜头边界来自 measure 的帧差切点；烟雾、火光、闪白、慢溶这类过渡可能整段并在一镜里。"
                 "candidate_cuts 是低阈值下镜内的候选切点，相邻 0.3 秒内的并成一段（frames>1 多半是闪光、粒子或快摇），逐镜那一遍看片确认后才算切"),
        "shots": shots,
    }
    target = out_dir / "manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return target


# ------------------------------------------------------------- subtitles


def parse_color(text: str) -> Tuple[int, int, int]:
    value = text.strip().lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        raise BreakdownError(f"--color 要写成六位十六进制，例如 FFD400：{text}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _color_filter(color: Tuple[int, int, int], tolerance: int) -> str:
    """Pixels whose every channel is within ``tolerance`` of ``color`` turn 255, the rest 0."""

    red, green, blue = color
    near = (f"if(lte(max(max(abs(r(X,Y)-{red}),abs(g(X,Y)-{green})),abs(b(X,Y)-{blue})),{tolerance}),255,0)")
    return f"geq=r='{near}':g='{near}':b='{near}',format=gray"


def _band_frames(video: Path, crop: str, fps: Optional[float],
                 color: Optional[Tuple[int, int, int]] = None, tolerance: int = DEFAULT_COLOR_TOLERANCE) -> bytes:
    """Grey frames of the band; with ``color``, each frame is followed by an
    equally sized frame that is 255 where the picture has that colour."""

    rate = f"fps={fps:g}," if fps else ""
    chain = f"{rate}{crop},scale={SUBTITLE_SAMPLE_WIDTH}:-2"
    if color is None:
        chain += ",format=gray"
    else:
        # Both branches of a split share one pixel format: make it RGB, or the
        # colour branch would only ever see grey.
        chain += f",format=gbrp,split[grey][hue];[grey]format=gray[g];[hue]{_color_filter(color, tolerance)}[c];[g][c]vstack"
    result = subprocess.run(
        [_require("ffmpeg"), "-v", "error", "-i", str(video), "-map", "0:v:0"]
        + ([] if fps else ["-frames:v", "1"])
        + ["-vf", chain, "-f", "rawvideo", "-"],
        capture_output=True, check=False,
    )
    if result.returncode != 0 or not result.stdout:
        raise BreakdownError(f"ffmpeg 扫字幕区失败 {video}: {result.stderr.decode(errors='replace')[-300:]}")
    return result.stdout


def glyph_masks(data: bytes, size: int, bright: int, dark: int, reach: int, hue: bool = False) -> List[int]:
    """Per frame, a bit per pixel: bright with a dark pixel ``reach`` pixels to
    its left or right. Outlined subtitle glyphs are that; a white shirt or a
    lit screen behind the band mostly is not.

    With ``hue``, every grey frame of ``size`` bytes is followed by a colour
    frame of the same size, and "bright" means 255 there instead."""

    to_bright = bytes(ord("1") if value >= bright else ord("0") for value in range(256))
    to_dark = bytes(ord("1") if value <= dark else ord("0") for value in range(256))
    to_hue = bytes(ord("1") if value >= 128 else ord("0") for value in range(256))
    step = size * 2 if hue else size
    masks: List[int] = []
    for index in range(0, len(data) - step + 1, step):
        frame = data[index:index + size]
        lit = int((data[index + size:index + step].translate(to_hue) if hue else frame.translate(to_bright)), 2)
        shade = int(frame.translate(to_dark), 2)
        masks.append(lit & ((shade << reach) | (shade >> reach)))
    return masks


def _bits(value: int) -> int:
    return bin(value).count("1")


def subtitle_events(masks: Sequence[int], pixels: int, fps: float, duration: float, min_share: float,
                    change_share: float, min_seconds: float) -> List[Dict[str, Any]]:
    """Intervals in which one subtitle stays on screen.

    A frame shows text when enough of the band is outlined glyph; the text
    changes when the glyph pixels that moved are a large share of those shown.
    """

    events: List[Dict[str, float]] = []
    current: Optional[int] = None
    previous: Optional[int] = None
    for index, mask in enumerate(masks):
        lit = _bits(mask)
        shown = lit >= min_share * pixels
        changed = False
        if shown and previous is not None and current is not None:
            changed = _bits(mask ^ previous) > change_share * max(lit, _bits(previous))
        if current is not None and (not shown or changed):
            events.append({"start": current / fps, "end": index / fps})
            current = None
        if shown and current is None:
            current = index
        previous = mask if shown else None
    if current is not None:
        events.append({"start": current / fps, "end": min(len(masks) / fps, duration)})
    # Float slack: two samples at 10 fps meet a 0.2 s minimum wherever they fall (0.3 - 0.1 < 0.2).
    kept = [event for event in events if event["end"] - event["start"] >= min_seconds - 1e-6]
    width = max(3, len(str(len(kept))))
    return [{"id": f"T{number:0{width}d}", "start": round(event["start"], 2), "end": round(event["end"], 2)}
            for number, event in enumerate(kept, 1)]


def overlap_seconds(spans: Iterable[Sequence[float]], others: Iterable[Sequence[float]]) -> float:
    """Total time two sets of [start, end] spans share; each set must not overlap itself."""

    return sum(max(0.0, min(end, other_end) - max(start, other_start))
               for start, end in spans for other_start, other_end in others)


def _write_subtitle_sheets(
    ffmpeg: str,
    video_stem: str,
    out_dir: Path,
    events: Sequence[Dict[str, Any]],
    aspect_w: float,
    aspect_h: float,
) -> List[str]:
    sheet_re = re.compile(rf"{re.escape(video_stem)}\.subtitles\.sheet(?:-\d{{2,}})?\.jpg")
    _clear(out_dir, sheet_re)
    cropped = [event for event in events if event.get("crop")]
    if not cropped:
        return []
    crop_w = 640
    raw_h = int(round(crop_w * aspect_h / max(0.01, aspect_w)))
    row_h = max(42, (min(120, raw_h) // 2) * 2)
    gutter_w = 200
    total_w = gutter_w + crop_w
    frame_bytes = crop_w * row_h * 3
    pages = [
        cropped[idx : idx + SUBTITLE_SHEET_PAGE_SIZE]
        for idx in range(0, len(cropped), SUBTITLE_SHEET_PAGE_SIZE)
    ]
    written: List[str] = []
    for page_index, page in enumerate(pages, 1):
        rows_rgb: List[Tuple[Dict[str, Any], bytes]] = []
        for event in page:
            crop_file = out_dir / str(event["crop"])
            if not crop_file.is_file():
                continue
            raw = subprocess.run(
                [
                    ffmpeg,
                    "-v",
                    "error",
                    "-i",
                    str(crop_file),
                    "-frames:v",
                    "1",
                    "-vf",
                    f"scale={crop_w}:{row_h}",
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "rgb24",
                    "-",
                ],
                capture_output=True,
                check=False,
            ).stdout
            if len(raw) == frame_bytes:
                rows_rgb.append((event, raw))
        if not rows_rgb:
            continue
        sep = 2
        sheet_h = len(rows_rgb) * row_h + (len(rows_rgb) - 1) * sep
        canvas = bytearray(total_w * sheet_h * 3)
        for idx in range(0, len(canvas), 3):
            canvas[idx : idx + 3] = b"\x38\x3c\x48"
        for row_idx, (event, pic_bytes) in enumerate(rows_rgb):
            oy = row_idx * (row_h + sep)
            for py in range(row_h):
                line_start = (oy + py) * total_w * 3
                for px in range(gutter_w):
                    at = line_start + px * 3
                    canvas[at : at + 3] = b"\x18\x1a\x20"
                dst = line_start + gutter_w * 3
                src = py * crop_w * 3
                canvas[dst : dst + crop_w * 3] = pic_bytes[src : src + crop_w * 3]
            span_label = f"{_format_stamp_clock(event['start'])}-{_format_stamp_clock(event['end'])}"
            _draw_bitmap_text(canvas, total_w, sheet_h, 8, oy + 5, str(event["id"]), scale=2, color=b"\xff\xd4\x00")
            _draw_bitmap_text(canvas, total_w, sheet_h, 8, oy + 23, span_label, scale=2, color=b"\xe6\xe8\xec")
        name = (
            f"{video_stem}.subtitles.sheet.jpg"
            if len(pages) == 1
            else f"{video_stem}.subtitles.sheet-{page_index:02d}.jpg"
        )
        if _write_ppm_jpeg(ffmpeg, total_w, sheet_h, bytes(canvas), out_dir / name):
            written.append(name)
    return written


def scan_subtitles(video: Path, out_dir: Path, band: Tuple[float, float, float, float],
                   fps: float = DEFAULT_SUBTITLE_FPS, bright: int = DEFAULT_SUBTITLE_BRIGHT,
                   crops: bool = True, color: Optional[Tuple[int, int, int]] = None,
                   tolerance: int = DEFAULT_COLOR_TOLERANCE, audio: Optional[Path] = None,
                   min_share: float = SUBTITLE_MIN_SHARE,
                   change_share: float = SUBTITLE_CHANGE_SHARE) -> Path:
    left, top, right, bottom = band
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise BreakdownError("--band 要写成 左,上,右,下 四个 0–1 之间的比例，且左<右、上<下")
    if fps <= 0:
        raise BreakdownError("--fps 要大于 0")
    if not 0 < min_share <= 1:
        raise BreakdownError("--min-share 要在 (0, 1] 之间")
    if not 0 < change_share <= 1:
        raise BreakdownError("--change-share 要在 (0, 1] 之间")
    info = probe(video)
    crop = (f"crop=trunc(iw*{right - left:.4f}/2)*2:trunc(ih*{bottom - top:.4f}/2)*2:"
            f"trunc(iw*{left:.4f}):trunc(ih*{top:.4f})")
    size = len(_band_frames(video, crop, None))
    data = _band_frames(video, crop, fps, color, tolerance)
    masks = glyph_masks(data, size, bright, SUBTITLE_DARK, SUBTITLE_OUTLINE_REACH, hue=color is not None)
    events = subtitle_events(masks, size, fps, info["duration"], min_share, change_share,
                             SUBTITLE_MIN_SECONDS)
    shown = round(sum(event["end"] - event["start"] for event in events), 2)
    voiced_shown: Optional[float] = None
    voiced_file = audio / f"{video.stem}{AUDIO_SUFFIX}" if audio is not None else None
    if voiced_file is not None and voiced_file.is_file():
        voiced = json.loads(voiced_file.read_text(encoding="utf-8")).get("voiced") or []
        voiced_total = sum(end - start for start, end in voiced)
        if voiced_total > 0:
            spans = [(event["start"], event["end"]) for event in events]
            voiced_shown = round(overlap_seconds(voiced, spans) / voiced_total, 3)
    out_dir.mkdir(parents=True, exist_ok=True)
    sheets: List[str] = []
    if crops:
        ffmpeg = _require("ffmpeg")
        folder = out_dir / f"{video.stem}.subtitles"
        folder.mkdir(exist_ok=True)
        _clear(folder, SUBTITLE_CROP)
        for event in events:
            name = f"{event['id']}.png"
            kept = _extract_frame(ffmpeg, video, (event["start"] + event["end"]) / 2, crop, folder / name)
            event["crop"] = f"{folder.name}/{name}" if kept else None
        pic_w = float(info.get("width") or 1920) * (right - left)
        pic_h = float(info.get("height") or 1080) * (bottom - top)
        sheets = _write_subtitle_sheets(ffmpeg, video.stem, out_dir, events, pic_w, pic_h)
    record = {
        "source": video.name,
        "episode": episode_number(video.stem),
        "duration": info["duration"],
        "source_sha256": file_sha256(video),
        "evidence": "measured",
        "method": {"band": list(band), "fps": fps, "bright": None if color else bright,
                   "color": "{:02X}{:02X}{:02X}".format(*color) if color else None,
                   "color_tolerance": tolerance if color else None,
                   "dark": SUBTITLE_DARK, "min_share": min_share,
                   "change_share": change_share, "min_seconds": SUBTITLE_MIN_SECONDS},
        "blind_spot": ("只测字幕区里带深色描边的亮字（或指定颜色的字）何时出现、何时换；不认字，文字读 sheets 拼版或 crop。"
                       "字幕区里的白衣、亮背景、系统面板会多出事件；跨切镜背景明暗突变可能把同一句拆成相邻两条，"
                       "连说两句无空隙或同屏合排也可能并成一条；极小单字仍可能漏检；字幕时间不等于开口时间"),
        "shown_seconds": shown,
        "shown_share": round(shown / info["duration"], 3) if info["duration"] else None,
        "voiced_shown_share": voiced_shown,
        "sheets": sheets,
        "events": events,
    }
    target = out_dir / f"{video.stem}{SUBTITLE_SUFFIX}"
    target.write_text(json.dumps(record, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    return target


def row_profile(rows: Sequence[int], height: int, width: int, bands: int = SUBTITLE_ROW_BANDS,
                min_share: float = SUBTITLE_ROW_MIN_SHARE, change_share: float = SUBTITLE_CHANGE_SHARE,
                ) -> Tuple[List[Dict[str, float]], List[int]]:
    """From one glyph mask per picture row, frame after frame: for each height
    band, the share of frames showing outlined text there and the share of
    frame pairs in which that text changed; and each frame's glyph pixel count.

    Subtitles show often and change often; a watermark shows always and never
    changes; a name card or system panel shows now and then."""

    frames = len(rows) // height if height else 0
    least = max(1, int(width * min_share))
    shown = [0] * bands
    changed = [0] * bands
    totals: List[int] = []
    previous: Optional[List[int]] = None
    for frame in range(frames):
        masks = rows[frame * height:(frame + 1) * height]
        counts = [_bits(mask) for mask in masks]
        totals.append(sum(counts))
        hit = [False] * bands
        moved = [False] * bands
        for row, count in enumerate(counts):
            if count < least:
                continue
            band = row * bands // height
            hit[band] = True
            if previous is not None:
                before = previous[row]
                if _bits(masks[row] ^ before) > change_share * max(count, _bits(before)):
                    moved[band] = True
        for band in range(bands):
            shown[band] += hit[band]
            changed[band] += moved[band]
        previous = list(masks)
    profile = [{"top": round(band / bands, 3), "bottom": round((band + 1) / bands, 3),
                "shown": round(shown[band] / frames, 3) if frames else 0.0,
                "changed": round(changed[band] / (frames - 1), 3) if frames > 1 else 0.0}
               for band in range(bands)]
    return profile, totals


def pick_frames(totals: Sequence[int], fps: float, count: int, spacing: float) -> List[int]:
    """The frames with the most outlined text, at least ``spacing`` seconds
    apart, in time order; evenly spaced frames fill up when too few frames
    show any (yellow or unoutlined subtitles leave the count at zero)."""

    gap = max(1, int(round(spacing * fps)))
    chosen: List[int] = []
    for index in sorted(range(len(totals)), key=lambda item: (-totals[item], item)):
        if len(chosen) >= count or totals[index] == 0:
            break
        if all(abs(index - other) >= gap for other in chosen):
            chosen.append(index)
    for slot in range(count):
        if len(chosen) >= count:
            break
        index = int((slot + 0.5) * len(totals) / count)
        if index < len(totals) and all(abs(index - other) >= gap for other in chosen):
            chosen.append(index)
    return sorted(chosen)


def ruler_filter() -> str:
    """Ticks on all four edges, short every 0.05 and long every 0.1 of the
    picture, and a faint full-width line every 0.1 of its height."""

    boxes = []
    for step in range(1, 20):
        long_tick = step % 2 == 0
        tick = 28 if long_tick else 12
        at = f"{step}/20"
        boxes += [f"drawbox=x=0:y=ih*{at}-1:w={tick}:h=3:c=red:t=fill",
                  f"drawbox=x=iw-{tick}:y=ih*{at}-1:w={tick}:h=3:c=red:t=fill"]
        if long_tick:
            boxes += [f"drawbox=x=0:y=ih*{at}:w=iw:h=1:c=red@0.35:t=fill",
                      f"drawbox=x=iw*{at}-1:y=0:w=3:h={tick}:c=red:t=fill",
                      f"drawbox=x=iw*{at}-1:y=ih-{tick}:w=3:h={tick}:c=red:t=fill"]
    return ",".join(boxes)


def suggest_subtitle_band(
    rows: Sequence[int],
    height: int,
    width: int,
    profile: Sequence[Dict[str, float]],
) -> Optional[List[float]]:
    """Suggest [left, top, right, bottom] around the active lower-half subtitle rows."""

    if height <= 0 or width <= 0 or not profile:
        return None
    lower = [band for band in profile if band["top"] >= 0.5 and band["changed"] > 0]
    if not lower:
        return None
    peak = max(lower, key=lambda item: (item["changed"], item["shown"]))
    peak_mid = (peak["top"] + peak["bottom"]) / 2
    active = [
        band
        for band in lower
        if abs((band["top"] + band["bottom"]) / 2 - peak_mid) <= 0.12
        and band["changed"] >= max(0.01, peak["changed"] * 0.15)
    ] or [peak]
    raw_top = min(band["top"] for band in active)
    raw_bottom = max(band["bottom"] for band in active)
    top = round(max(0.5, raw_top - 0.03), 3)
    bottom = round(min(1.0, raw_bottom + 0.03), 3)

    r_start = max(0, int(math.floor(raw_top * height)))
    r_end = min(height, int(math.ceil(raw_bottom * height)))
    least = max(1, int(width * SUBTITLE_ROW_MIN_SHARE))
    frames = len(rows) // height
    x_lefts: List[int] = []
    x_rights: List[int] = []
    for frame in range(frames):
        base = frame * height
        frame_mask = 0
        for row_idx in range(r_start, r_end):
            mask = rows[base + row_idx]
            if _bits(mask) >= least:
                frame_mask |= mask
        if frame_mask > 0:
            x_lefts.append(max(0, width - frame_mask.bit_length()))
            trailing = (frame_mask & -frame_mask).bit_length() - 1
            x_rights.append(min(width - 1, width - 1 - trailing))
    if x_lefts:
        x_lefts.sort()
        x_rights.sort()
        trim = min(len(x_lefts) - 1, max(2, len(x_lefts) // 20)) if len(x_lefts) >= 6 else 0
        x_min = x_lefts[trim]
        x_max = x_rights[len(x_rights) - 1 - trim]
        left = round(max(0.0, min(DEFAULT_SUBTITLE_BAND[0], x_min / width - 0.03)), 3)
        right = round(min(1.0, max(DEFAULT_SUBTITLE_BAND[2], (x_max + 1) / width + 0.03)), 3)
    else:
        left, right = DEFAULT_SUBTITLE_BAND[0], DEFAULT_SUBTITLE_BAND[2]
    if left >= right or top >= bottom:
        return None
    return [left, top, right, bottom]


def subtitle_sheet(videos: Sequence[Path], out_dir: Path, frames: int = SUBTITLE_SHEET_FRAMES,
                   bright: int = DEFAULT_SUBTITLE_BRIGHT) -> Path:
    if frames < 1:
        raise BreakdownError("--frames 至少 1")
    ffmpeg = _require("ffmpeg")
    out_dir.mkdir(parents=True, exist_ok=True)
    per_video = max(1, math.ceil(frames / len(videos)))
    picked: List[Tuple[Path, float]] = []
    sources: List[Dict[str, Any]] = []
    suggestions: List[List[float]] = []
    portrait = False
    for video in videos:
        info = probe(video)
        portrait = portrait or (info["height"] or 0) > (info["width"] or 0)
        whole = "crop=iw:ih:0:0"
        size = len(_band_frames(video, whole, None))
        height = size // SUBTITLE_SAMPLE_WIDTH
        data = _band_frames(video, whole, SUBTITLE_SHEET_FPS)
        rows = glyph_masks(data, SUBTITLE_SAMPLE_WIDTH, bright, SUBTITLE_DARK, SUBTITLE_OUTLINE_REACH)
        profile, totals = row_profile(rows, height, SUBTITLE_SAMPLE_WIDTH)
        suggested = suggest_subtitle_band(rows, height, SUBTITLE_SAMPLE_WIDTH, profile)
        if suggested is not None:
            suggestions.append(suggested)
        moments = [index / SUBTITLE_SHEET_FPS
                   for index in pick_frames(totals, SUBTITLE_SHEET_FPS, per_video, SUBTITLE_SHEET_SPACING_SECONDS)]
        picked.extend((video, moment) for moment in moments)
        sources.append({"source": video.name, "source_sha256": file_sha256(video), "frames_at": moments,
                        "suggested_band": suggested, "rows": profile})
    picked = picked[:frames]
    grid = f"scale={SUBTITLE_SHEET_WIDTH}:-2," + ruler_filter()
    sheet = out_dir / "subtitle-sheet.jpg"
    if sheet.exists():
        sheet.unlink()
    with tempfile.TemporaryDirectory() as scratch:
        kept = 0
        for video, moment in picked:
            if _extract_frame(ffmpeg, video, moment, grid, Path(scratch) / f"f{kept + 1:03d}.png"):
                kept += 1
        if kept:
            columns = min(kept, 4 if portrait else 2)
            subprocess.run(
                [ffmpeg, "-v", "error", "-i", str(Path(scratch) / "f%03d.png"), "-frames:v", "1",
                 "-vf", f"tile={columns}x{math.ceil(kept / columns)}:padding=8:color=white", "-y", str(sheet)],
                capture_output=True, check=False,
            )
    merged_band: Optional[List[float]] = None
    if suggestions:
        merged_band = [
            round(min(item[0] for item in suggestions), 3),
            round(min(item[1] for item in suggestions), 3),
            round(max(item[2] for item in suggestions), 3),
            round(max(item[3] for item in suggestions), 3),
        ]
    record = {
        "evidence": "measured",
        "sheet": sheet.name if sheet.is_file() else None,
        "suggested_band": merged_band,
        "grid": "四边红色刻度：短的每 0.05，长的每 0.1；淡红横线每 0.1 画面高。最上沿、最左沿是 0",
        "method": {"fps": SUBTITLE_SHEET_FPS, "bright": bright, "dark": SUBTITLE_DARK,
                   "row_min_share": SUBTITLE_ROW_MIN_SHARE, "change_share": SUBTITLE_CHANGE_SHARE},
        "blind_spot": ("只认带深色描边的亮字；黄字、彩字、无描边字可能整段不出现，要看图。"
                       "shown 高、changed 近 0 的多是水印或台标；名条、系统面板也会出现在这里；"
                       "suggested_band 按下半屏描边亮字位置给出候选框，跑 subtitles 前要对照 subtitle-sheet.jpg 确认"),
        "videos": sources,
    }
    target = out_dir / "subtitle-rows.json"
    target.write_text(json.dumps(record, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    return target


# ----------------------------------------------------------- transcripts


def episode_number(stem: str) -> Optional[int]:
    for marker in (*EPISODE_MARKERS, EPISODE_BARE):
        found = marker.search(stem)
        if found:
            return int(found.group(1))
    return None


def _seconds(hours: Optional[str], minutes: str, seconds: str, fraction: str) -> float:
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(fraction.ljust(3, "0")) / 1000


def parse_transcript(text: str, suffix: str) -> List[Dict[str, Any]]:
    """Timed segments ``{"s", "e", "t"}`` from SRT, WebVTT, JSON segments or annotated ``*.subtitles.json``."""

    text = _normalize_text(text)
    suffix = suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise BreakdownError(f"JSON 转写无法解析：{error}") from error
        from_subtitles = isinstance(data, dict) and "events" in data and "segments" not in data
        items = (data.get("events") if from_subtitles else data.get("segments", data)) if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise BreakdownError("JSON 转写须为列表，或包含 segments / events 列表的对象")
        raw_segments: List[Dict[str, Any]] = []
        any_text_field = False
        for item in items:
            if not isinstance(item, dict):
                raise BreakdownError("JSON 转写的每段都须为对象")
            start = item.get("s", item.get("start"))
            end = item.get("e", item.get("end"))
            if "t" in item or "text" in item:
                any_text_field = True
            words = item.get("t", item.get("text", ""))
            if start is None or end is None:
                raise BreakdownError("JSON 转写的每段都要有 start/end（或 s/e）秒数")
            raw_segments.append({"s": float(start), "e": float(end), "t": str(words).strip()})
        if from_subtitles and items and not any_text_field:
            raise BreakdownError(
                "这份 *.subtitles.json 只有时间轴和裁图，还没有填写 text 台词文本；"
                "先对照字幕拼版填入每条事件的 text（跨镜碎段合并或非台词留空），再挂接"
            )
        segments = [segment for segment in raw_segments if segment["t"]]
        return _filter_valid_intervals(segments)
    pattern = SRT_TIME if suffix == ".srt" else VTT_TIME
    segments = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
        for index, line in enumerate(lines):
            found = pattern.search(line)
            if not found:
                continue
            groups = found.groups()
            start = _seconds(*groups[:4])
            end = _seconds(*groups[4:])
            words = " ".join(re.sub(r"<[^>]+>", "", item) for item in lines[index + 1:]).strip()
            if words:
                segments.append({"s": round(start, 3), "e": round(end, 3), "t": words})
            break
    if not segments:
        raise BreakdownError("没有读出任何带时间的字幕段；支持 .srt、.vtt 与 JSON segments")
    return _filter_valid_intervals(segments)


def _filter_valid_intervals(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not segments:
        return []
    valid: List[Dict[str, Any]] = []
    for segment in segments:
        start, end = segment["s"], segment["e"]
        if not (math.isfinite(start) and math.isfinite(end)):
            raise BreakdownError(
                f"转写里有一段时间不成立（{start}–{end} 秒）：开始与结束须为有限秒数"
            )
        if start < 0 or start >= end:
            print(
                f"注意：转写里有一段时间不成立（{start}–{end} 秒），已跳过该字幕行",
                file=sys.stderr,
            )
            continue
        valid.append(segment)
    if not valid:
        raise BreakdownError("转写里没有有效时间段（开始要不小于 0 且早于结束）；先修正字幕再挂接")
    return valid


_CUE_MAP_LINE_RE = re.compile(
    r"^T0*(\d+)(?:\s*[-–~]\s*T0*(\d+))?(?:[ \t\u3000]+|[ \t\u3000]*[：:][ \t\u3000]*)(.*)$",
    re.IGNORECASE,
)


def parse_subtitle_cue_map(cue_text: str, subtitles_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build timed segments from ``T001 台词`` / ``T005-T010 合并台词`` lines against ``*.subtitles.json``."""

    events = subtitles_data.get("events") if isinstance(subtitles_data, dict) else None
    if not isinstance(events, list):
        raise BreakdownError("--subtitles 需要传入 subtitles 子命令生成的 *.subtitles.json")
    by_number: Dict[int, Dict[str, Any]] = {}
    for item in events:
        if not isinstance(item, dict):
            continue
        found_id = re.fullmatch(r"T0*(\d+)", str(item.get("id") or "").strip(), re.IGNORECASE)
        if found_id and item.get("start") is not None and item.get("end") is not None:
            by_number[int(found_id.group(1))] = item

    segments: List[Dict[str, Any]] = []
    for line_no, raw_line in enumerate(_normalize_text(cue_text).split("\n"), 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        bare_id = re.fullmatch(r"T0*(\d+)(?:\s*[-–~]\s*T0*(\d+))?", stripped, re.IGNORECASE)
        if bare_id is not None:
            continue
        matched = _CUE_MAP_LINE_RE.match(stripped)
        if matched is None:
            raise BreakdownError(
                f"第 {line_no} 行格式不认得（应写为 'T001 台词' 或 'T005-T010 合并台词'）：{stripped}"
            )
        first_num = int(matched.group(1))
        last_num = int(matched.group(2) or first_num)
        if first_num > last_num:
            raise BreakdownError(f"第 {line_no} 行编号范围倒挂：T{first_num:03d}-T{last_num:03d}")
        missing = [num for num in range(first_num, last_num + 1) if num not in by_number]
        if missing:
            raise BreakdownError(
                f"第 {line_no} 行引用的字幕事件不存在：T{missing[0]:03d}"
            )
        words = matched.group(3).strip()
        if not words:
            continue
        span_events = [by_number[num] for num in range(first_num, last_num + 1)]
        start = min(float(item["start"]) for item in span_events)
        end = max(float(item["end"]) for item in span_events)
        segments.append({"s": round(start, 3), "e": round(end, 3), "t": words})
    return _filter_valid_intervals(segments)


def attach_transcript(measure: Path, transcript: Path, subtitles: Optional[Path] = None) -> None:
    record = json.loads(_normalize_text(measure.read_text(encoding="utf-8")))
    raw_text = transcript.read_text(encoding="utf-8")
    if subtitles is not None:
        subtitles_data = json.loads(_normalize_text(subtitles.read_text(encoding="utf-8")))
        segments = parse_subtitle_cue_map(raw_text, subtitles_data)
    else:
        segments = parse_transcript(raw_text, transcript.suffix)
    record["segments"] = sorted(segments, key=lambda segment: segment["s"])
    record["transcript_source"] = transcript.name
    if transcript_overrun(record):
        print(f"注意：{transcript.name} 的字幕时间超出片长 {record['duration']} 秒，超出部分不计入统计；"
              "多半是识别错误，抽查这一集", file=sys.stderr)
    measure.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")


# --------------------------------------------------------------- profile


def spoken_characters(text: str) -> int:
    """Letters and digits of any script; punctuation and spaces are not said."""

    return sum(1 for character in text if character.isalnum())


def _normalize_text(text: str) -> str:
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _median(values: Iterable[Optional[float]]) -> Optional[float]:
    present = [value for value in values if value is not None]
    return round(statistics.median(present), 2) if present else None


def episode_numbers(record: Dict[str, Any]) -> Dict[str, Optional[float]]:
    duration = record.get("duration")
    lengths = record.get("shot_seconds") or []
    numbers: Dict[str, Optional[float]] = {
        "duration": duration,
        "shots": len(lengths) or None,
        "avg_shot": round(duration / len(lengths), 2) if duration and lengths else None,
        "median_shot": round(statistics.median(lengths), 2) if lengths else None,
        "long_shot_share": round(sum(1 for value in lengths if value > LONG_SHOT_SECONDS) / len(lengths), 2)
        if lengths else None,
    }
    segments = verified_segments(record)
    if segments and duration:
        merged: List[List[float]] = []
        for segment in sorted(segments, key=lambda item: item["s"]):
            if merged and segment["s"] <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], segment["e"])
            else:
                merged.append([segment["s"], segment["e"]])
        speech = sum(end - start for start, end in merged)
        characters = sum(spoken_characters(segment["t"]) for segment in segments)
        edges = [0.0, *[value for interval in merged for value in interval], duration]
        gaps = [edges[index + 1] - edges[index] for index in range(0, len(edges), 2)]
        numbers.update(
            speech_share=round(speech / duration, 2),
            chars_per_speech_second=round(characters / speech, 2) if speech else None,
            chars_per_second=round(characters / duration, 2),
            first_line_at=round(merged[0][0], 2),
            tail_after_last_line=round(max(0.0, duration - merged[-1][1]), 2),
            longest_silence=round(max(gaps), 2) if gaps else None,
        )
    elif duration and record.get("segments") == [] and record.get("transcript_source"):
        # Footage whose transcript has no speech is known to be silent, not
        # unmeasured, and pulls the series medians down rather than dropping out.
        numbers.update(speech_share=0.0, chars_per_second=0.0, longest_silence=round(duration, 2))
    return numbers


def verified_segments(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Transcript cues inside the picture.

    A cue running past the picture is a recognition error, not speech: its
    timing and its text are both unverified, so every count leaves it out.
    """

    duration = record.get("duration")
    segments = record.get("segments") or []
    if not segments or not duration:
        return list(segments)
    return [{**segment, "e": min(segment["e"], duration)} for segment in segments
            if segment["s"] < duration and segment["e"] <= duration + OVERRUN_TOLERANCE_SECONDS]


def transcript_overrun(record: Dict[str, Any]) -> bool:
    duration = record.get("duration")
    segments = record.get("segments") or []
    return bool(duration and segments
                and max(segment["e"] for segment in segments) > duration + OVERRUN_TOLERANCE_SECONDS)


def profile(records: Sequence[Dict[str, Any]], opening: int) -> Dict[str, Any]:
    unnumbered = [record for record in records if record.get("episode") is None]
    ordered = sorted(
        (record for record in records if record.get("episode") is not None),
        key=lambda record: (int(record["episode"]), str(record.get("source") or "")),
    )
    counts_by_episode: Dict[int, int] = {}
    for record in ordered:
        ep = int(record["episode"])
        counts_by_episode[ep] = counts_by_episode.get(ep, 0) + 1

    entries: List[Tuple[int, str, Dict[str, Optional[float]]]] = []
    seen_occurrence: Dict[int, int] = {}
    duplicate_sources: Dict[int, List[str]] = {}
    for record in ordered:
        ep = int(record["episode"])
        row = episode_numbers(record)
        if counts_by_episode[ep] == 1:
            label = str(ep)
        else:
            occ = seen_occurrence.get(ep, 0) + 1
            seen_occurrence[ep] = occ
            source_name = str(record.get("source") or "")
            duplicate_sources.setdefault(ep, []).append(source_name or f"#{occ}")
            label = f"{ep}#{occ}"
        entries.append((ep, label, row))

    warnings: List[str] = []
    for ep, names in sorted(duplicate_sources.items()):
        warnings.append(
            f"集号 {ep} 重复出现 {len(names)} 次（{', '.join(names)}）；"
            "已全部保留未覆盖，请核对文件名或集号解析"
        )
    if unnumbered:
        names = [str(record.get("source") or "未命名") for record in unnumbered]
        warnings.append(
            f"有 {len(unnumbered)} 份记录未识别出集号（{', '.join(names)}），"
            "未计入按集分组统计；请核对文件名"
        )

    keys = sorted({key for _, _, row in entries for key in row})

    def group(selector: Callable[[int], bool]) -> Dict[str, Any]:
        chosen = [row for episode, _, row in entries if selector(episode)]
        return {"episodes": len(chosen), **{key: _median(row.get(key) for row in chosen) for key in keys}}

    later: List[float] = [
        float(row["duration"] or 0) for episode, _, row in entries if episode > opening and row.get("duration")
    ]
    regime: Dict[str, Any] = {
        "opening_durations": [row["duration"] for episode, _, row in entries if episode <= opening]
    }
    if len(later) >= 5:
        ranked = sorted(later)
        low, high = ranked[len(ranked) // 10], ranked[(9 * len(ranked)) // 10]
        regime.update(later_p10=round(low, 1), later_p90=round(high, 1),
                      later_fixed_length=high - low <= FIXED_LENGTH_SPREAD_SECONDS)
    sources = sorted({record.get("kind", "footage") for record in ordered})
    return {
        "sources": sources,
        "transcript_overruns": [record["episode"] for record in ordered if transcript_overrun(record)],
        "warnings": warnings,
        "opening": group(lambda episode: episode <= opening),
        "later": group(lambda episode: episode > opening),
        "all": group(lambda episode: True),
        "length_regime": regime,
        "per_episode": {label: row for _, label, row in entries},
    }


def load_records(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    records = []
    for path in paths:
        files = sorted(path.glob(f"*{MEASURE_SUFFIX}")) if path.is_dir() else [path]
        for file in files:
            records.append(json.loads(_normalize_text(file.read_text(encoding="utf-8"))))
    if not records:
        raise BreakdownError("没有找到 *.measure.json；先运行 measure")
    return records


def render_table(profiles: Dict[str, Dict[str, Any]]) -> str:
    columns = [
        ("duration", "集长s"), ("avg_shot", "平均镜长"), ("median_shot", "中位镜长"),
        ("long_shot_share", ">4s镜占比"), ("speech_share", "有声占比"),
        ("chars_per_speech_second", "字/发声秒"), ("chars_per_second", "字/秒"),
        ("first_line_at", "首句s"), ("tail_after_last_line", "末句后s"),
        ("longest_silence", "最长静默s"),
    ]
    lines = ["| 系列 | 分组 | 集数 | " + " | ".join(label for _, label in columns) + " |",
             "|" + "---|" * (len(columns) + 3)]
    for name, result in profiles.items():
        for label in ("opening", "later"):
            row = result[label]
            if not row["episodes"]:
                continue
            cells = ["—" if row.get(key) is None else f"{row[key]:g}" for key, _ in columns]
            lines.append(f"| {name} | {label} | {row['episodes']} | " + " | ".join(cells) + " |")
    lines.append("")
    for name, result in profiles.items():
        regime = result["length_regime"]
        fixed = regime.get("later_fixed_length")
        lines.append(
            f"- {name}：开头几集时长 {regime['opening_durations']}"
            + (f"；之后 p10–p90 为 {regime['later_p10']}–{regime['later_p90']} 秒"
               + ("（近似定长）" if fixed else "") if "later_p10" in regime else "")
            + (f"；转写超出片长的集：{result['transcript_overruns']}，超出部分未计入" if result["transcript_overruns"] else "")
        )
        for warning in result.get("warnings") or []:
            lines.append(f"- 注意（{name}）：{warning}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ CLI


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    measure = sub.add_parser("measure", help="测量视频：时长、切点、镜长与代表帧拼图")
    measure.add_argument("videos", nargs="+", type=Path)
    measure.add_argument("--out", type=Path, required=True)
    measure.add_argument("--scene-threshold", type=float, default=DEFAULT_SCENE_THRESHOLD)
    measure.add_argument("--no-sheet", action="store_true", help="不出代表帧拼图")

    transcript = sub.add_parser("transcript", help="把带时间的转写挂到已测量的一集上")
    transcript.add_argument("measure", type=Path)
    transcript.add_argument("transcript", type=Path)
    transcript.add_argument("--subtitles", type=Path,
                            help="配 T001/T005-T010 文本映射文件时传入同集 *.subtitles.json，自动合并区间起止时间")

    prof = sub.add_parser("profile", help="按系列汇总已测量的集")
    prof.add_argument("series", nargs="+", help="名称=目录，例如 REF-A=输入/对标/REF-A/measure")
    prof.add_argument("--opening", type=int, default=3, help="单列统计的开头集数（默认 3）")
    prof.add_argument("--json", action="store_true", help="输出完整 JSON 而不是表格")

    audio = sub.add_parser("audio", help="测音轨：有声区间与响度（不分对白和配乐）")
    audio.add_argument("videos", nargs="+", type=Path)
    where = audio.add_mutually_exclusive_group(required=True)
    where.add_argument("--measure", type=Path, help="写在这份 *.measure.json 旁边（只能配一个视频）")
    where.add_argument("--out", type=Path, help="写进这个目录")
    audio.add_argument("--noise-db", type=float, default=DEFAULT_SILENCE_DB,
                       help=f"低于这个电平算静音（默认 {DEFAULT_SILENCE_DB:g} dB）")
    audio.add_argument("--min-silence", type=float, default=DEFAULT_SILENCE_SECONDS,
                       help=f"静音至少持续这么多秒才算（默认 {DEFAULT_SILENCE_SECONDS:g}）")

    shots = sub.add_parser("shots", help="按测量切点切出每镜小段与首、中、尾三帧，写 manifest.json")
    shots.add_argument("video", type=Path)
    shots.add_argument("measure", type=Path)
    shots.add_argument("--out", type=Path, help="默认 <REF-ID>/shots/<集名>/，与 measure 目录同级")
    shots.add_argument("--inner-threshold", type=float, default=DEFAULT_INNER_THRESHOLD,
                       help=f"列镜内候选切点用的低阈值（默认 {DEFAULT_INNER_THRESHOLD:g}；不低于测量阈值时不列）")
    subs = sub.add_parser("subtitles", help="扫烧录字幕区：每句字幕的出现与消失时间，并存字幕裁图与分页拼版")
    subs.add_argument("videos", nargs="+", type=Path)
    subs.add_argument("--out", type=Path, required=True)
    subs.add_argument("--band", default=",".join(f"{value:g}" for value in DEFAULT_SUBTITLE_BAND),
                      help="字幕区：左,上,右,下 的画面比例（默认底部居中 %(default)s）")
    subs.add_argument("--fps", type=float, default=DEFAULT_SUBTITLE_FPS,
                      help=f"每秒采样帧数（默认 {DEFAULT_SUBTITLE_FPS:g}，时间精度约 1/fps 秒）")
    subs.add_argument("--bright", type=int, default=DEFAULT_SUBTITLE_BRIGHT,
                      help=f"白亮字形的亮度下限 0–255（默认 {DEFAULT_SUBTITLE_BRIGHT}；黄字、彩字改用 --color）")
    subs.add_argument("--color", help="字色，六位十六进制（如黄字 FFD400）；给了就按颜色找字形，不再看 --bright")
    subs.add_argument("--color-tolerance", type=int, default=DEFAULT_COLOR_TOLERANCE,
                      help=f"每个通道与字色最多差多少仍算字形（默认 {DEFAULT_COLOR_TOLERANCE}）")
    subs.add_argument("--min-share", type=float, default=SUBTITLE_MIN_SHARE,
                      help=f"描边亮像素占裁剪框比例下限（默认 {SUBTITLE_MIN_SHARE:g}；单字仍漏检时可再调低）")
    subs.add_argument("--change-share", type=float, default=SUBTITLE_CHANGE_SHARE,
                      help=f"相邻帧字形像素变动超过这个比例算换句（默认 {SUBTITLE_CHANGE_SHARE:g}）")
    subs.add_argument("--audio", type=Path,
                      help="audio 子命令的输出目录；给了就记下有声时间里有字幕的比例 voiced_shown_share")
    subs.add_argument("--no-crops", action="store_true", help="不存字幕裁图与字幕拼版")

    sheet = sub.add_parser("subtitle-sheet",
                           help="字幕区校准图：描边字最多的几帧叠比例网格，加各高度出现与变化描边字的比例")
    sheet.add_argument("videos", nargs="+", type=Path, help="同一部剧的几集，帧从各集平均抽")
    sheet.add_argument("--out", type=Path, required=True)
    sheet.add_argument("--frames", type=int, default=SUBTITLE_SHEET_FRAMES,
                       help=f"图里放几帧（默认 {SUBTITLE_SHEET_FRAMES}）")
    sheet.add_argument("--bright", type=int, default=DEFAULT_SUBTITLE_BRIGHT, help="字形亮度下限 0–255")

    args = parser.parse_args(argv)
    try:
        if args.command == "measure":
            for video in args.videos:
                print(measure_video(video, args.out, args.scene_threshold, not args.no_sheet))
        elif args.command == "transcript":
            attach_transcript(args.measure, args.transcript, args.subtitles)
            print(args.measure)
        elif args.command == "audio":
            if args.measure is not None and len(args.videos) > 1:
                raise BreakdownError("--measure 只能配一个视频；多个视频用 --out 指定目录")
            out_dir = args.measure.parent if args.measure is not None else args.out
            for video in args.videos:
                print(measure_audio(video, out_dir, args.noise_db, args.min_silence))
        elif args.command == "shots":
            here = args.measure.resolve().parent
            out_dir = args.out or (here.parent if here.name == "measure" else here) / "shots" / args.video.stem
            print(cut_shots(args.video, args.measure, out_dir, args.inner_threshold))
        elif args.command == "subtitles":
            try:
                band = tuple(float(value) for value in args.band.split(","))
            except ValueError:
                band = ()
            if not 0 <= args.bright <= 255:
                raise BreakdownError("--bright 要在 0–255 之间")
            if len(band) != 4:
                raise BreakdownError("--band 要写成 左,上,右,下 四个 0–1 之间的比例，例如 0.08,0.78,0.92,0.99")
            color = parse_color(args.color) if args.color else None
            if not 0 <= args.color_tolerance <= 255:
                raise BreakdownError("--color-tolerance 要在 0–255 之间")
            for video in args.videos:
                print(scan_subtitles(video, args.out, band, args.fps, args.bright, not args.no_crops,
                                     color, args.color_tolerance, args.audio, args.min_share, args.change_share))
        elif args.command == "subtitle-sheet":
            if not 0 <= args.bright <= 255:
                raise BreakdownError("--bright 要在 0–255 之间")
            print(subtitle_sheet(args.videos, args.out, args.frames, args.bright))
        else:
            results = {}
            for item in args.series:
                name, _, folder = item.partition("=")
                if not folder:
                    raise BreakdownError(f"系列要写成 名称=目录：{item}")
                results[name] = profile(load_records([Path(folder)]), args.opening)
            if args.json:
                print(json.dumps(results, ensure_ascii=False, indent=1))
            else:
                print(render_table(results), end="")
    except BreakdownError as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
