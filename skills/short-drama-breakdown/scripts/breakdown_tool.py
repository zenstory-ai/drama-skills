#!/usr/bin/env python3
"""Measure reference episodes and a project's own plan on one yardstick.

Subcommands, each printing or writing measurements and never verdicts:

``measure``     probe reference (or own) video files: duration, picture size,
                detected cut points, shot lengths and a contact sheet with one
                frame per detected shot.
``transcript``  attach a timed transcript (SRT, WebVTT or JSON segments) to a
                measured episode, so speech numbers come from real timings.
``plan``        read a project's ``剧集/<EP>/分镜.md`` and ``剧本.md`` and record the
                planned durations, shot count and spoken characters in the same
                shape, so a plan can sit next to a reference in one table.
``profile``     aggregate measured episodes per series into one table: the
                opening episodes apart from the rest, medians, the length regime
                and whether an episode opens by replaying the previous ending.

Cut detection is a frame-difference threshold. It misses slow dissolves and
counts flashes, whip pans and particle effects as cuts; a transcript counts
narration, system voice and dialogue alike. The numbers say where to look.
Whether a reference choice suits this project is the creator's call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

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
# A one-off "名字：" opener longer than this, or opening with a pronoun, reads
# as action with a colon in it rather than a speaker.
NAME_MAX_CHARACTERS = 4
PRONOUNS = ("他", "她", "它", "我", "你", "这", "那")
# Cue ends this far past the picture are rounding, not a recognition error.
OVERRUN_TOLERANCE_SECONDS = 0.5
# Opening this many seconds of the next episode is compared with the closing
# seconds of the previous one.
REPRISE_WINDOW_SECONDS = 12.0
REPRISE_MIN_SHARED_UNITS = 6
# Episodes after the opening ones count as fixed length when the 10th and
# 90th percentiles sit this close.
FIXED_LENGTH_SPREAD_SECONDS = 3.0
# Scripts written with spaces between words are timed and compared by the
# word; every other pronounced character is one unit, as in the write stage.
WORD_SCRIPTS = ("LATIN", "CYRILLIC", "GREEK")
WORD_JOINERS = frozenset("'’-")
# Strongest first: 第N集, then an EP/E marker that does not sit inside a word
# (``Love2026_EP001``), then a 第N that is not a season or a part.
EPISODE_MARKERS = (
    re.compile(r"第\s*0*(\d{1,4})\s*[集话話]"),
    re.compile(r"(?<![A-Za-z])(?:EP|E)\s*0*(\d{1,4})(?!\d)", re.IGNORECASE),
    re.compile(r"第\s*0*(\d{1,4})(?![\d季部])"),
)
EPISODE_BARE = re.compile(r"(?<!\d)0*(\d{1,4})(?!\d)")
SHOT_DURATION = re.compile(r"^- 时长：\s*([\d.]+)\s*(?:s|秒)", re.MULTILINE)
SHOT_HEADING = re.compile(r"^## SHOT-[^\s]+", re.MULTILINE)
ON_SCREEN_TEXT_TAG = "[画面文字]"
# A performance note inside a line, ``走。（压低声音）``, is not spoken.
DIRECTION = re.compile(r"（[^（）]*）|\([^()]*\)")
CUE_LINE = re.compile(r"^(?:\[(VO|OS)\]\s*)?([^\s：:（(\[]{1,40})(?:（[^）]*）|\([^)]*\))?[：:]\s*(.+)$")
SRT_TIME = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})"
)
VTT_TIME = re.compile(
    r"(?:(\d+):)?(\d{2}):(\d{2})\.(\d{1,3})\s*-->\s*(?:(\d+):)?(\d{2}):(\d{2})\.(\d{1,3})"
)


class BreakdownError(Exception):
    pass


# ---------------------------------------------------------------- media


def _require(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise BreakdownError(
            f"PATH 上没有 {name}。测量真实视频需要 ffmpeg 与 ffprobe；没有它就没有可报告的数字，"
            "先安装，不用别的手段近似。"
        )
    return found


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


def contact_sheet(video: Path, lengths: Sequence[float], out: Path, columns: int = 8) -> None:
    ffmpeg = _require("ffmpeg")
    with tempfile.TemporaryDirectory() as tmp:
        start = 0.0
        for index, length in enumerate(lengths):
            middle = start + length / 2
            start += length
            subprocess.run(
                [ffmpeg, "-v", "error", "-ss", f"{middle:.3f}", "-i", str(video), "-map", "0:v:0",
                 "-frames:v", "1", "-vf", "scale=320:-2", "-y", f"{tmp}/{index:04d}.jpg"],
                check=False,
            )
        frames = sorted(Path(tmp).glob("*.jpg"))
        if not frames:
            return
        rows = (len(frames) + columns - 1) // columns
        subprocess.run(
            [ffmpeg, "-v", "error", "-framerate", "1", "-i", f"{tmp}/%04d.jpg",
             "-vf", f"tile={columns}x{rows}:padding=2", "-frames:v", "1", "-y", str(out)],
            check=False,
        )


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
    record = {
        "source": video.name,
        "episode": episode_number(video.stem),
        "kind": "footage",
        **info,
        "source_sha256": file_sha256(video),
        "scene_threshold": threshold,
        "cuts": [cut for cut in cuts if EDGE_IGNORE_SECONDS < cut < info["duration"] - EDGE_IGNORE_SECONDS],
        "shot_seconds": lengths,
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
    """Timed segments ``{"s", "e", "t"}`` from SRT, WebVTT or JSON."""

    suffix = suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
        items = data.get("segments", data) if isinstance(data, dict) else data
        segments = []
        for item in items:
            start = item.get("s", item.get("start"))
            end = item.get("e", item.get("end"))
            words = item.get("t", item.get("text", ""))
            if start is None or end is None:
                raise BreakdownError("JSON 转写的每段都要有 start/end（或 s/e）秒数")
            segments.append({"s": float(start), "e": float(end), "t": str(words).strip()})
        segments = [segment for segment in segments if segment["t"]]
        _check_intervals(segments)
        return segments
    pattern = SRT_TIME if suffix == ".srt" else VTT_TIME
    segments = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
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
    _check_intervals(segments)
    return segments


def _check_intervals(segments: List[Dict[str, Any]]) -> None:
    for segment in segments:
        start, end = segment["s"], segment["e"]
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
            raise BreakdownError(f"转写里有一段时间不成立（{start}–{end} 秒）：开始要不小于 0 且早于结束；先修正这段再挂接")


def attach_transcript(measure: Path, transcript: Path) -> None:
    record = json.loads(measure.read_text(encoding="utf-8"))
    segments = parse_transcript(transcript.read_text(encoding="utf-8"), transcript.suffix)
    record["segments"] = sorted(segments, key=lambda segment: segment["s"])
    record["transcript_source"] = transcript.name
    if transcript_overrun(record):
        print(f"注意：{transcript.name} 的字幕时间超出片长 {record['duration']} 秒，超出部分不计入统计；"
              "多半是识别错误，抽查这一集", file=sys.stderr)
    measure.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ plan


def spoken_characters(text: str) -> int:
    """Letters and digits of any script; punctuation and spaces are not said."""

    return sum(1 for character in text if character.isalnum())


def dialogue_characters(text: str) -> int:
    """The VO share's own count: punctuation included, as the rhythm profile
    defines it in the write stage."""

    return len(re.sub(r"\s", "", text))


def readable_characters(text: str) -> int:
    """Characters a viewer reads in an on-screen text block, carrier included."""

    return sum(1 for character in re.sub(r"\s", "", text) if not unicodedata.category(character).startswith("P"))


def project_pacing(episode_dir: Path) -> Optional[Dict[str, Optional[float]]]:
    """The project's declared speaking and action rates, when it has them."""

    for folder in (episode_dir, *list(episode_dir.parents)[:3]):
        config = folder / "short-drama.json"
        if not config.is_file():
            continue
        try:
            pacing = (json.loads(config.read_text(encoding="utf-8")).get("format") or {}).get("pacing") or {}
        except (OSError, ValueError):
            return None

        def rate(name: str) -> Optional[float]:
            value = pacing.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                return float(value)
            return None

        action = pacing.get("seconds_per_action_paragraph")
        if not isinstance(action, (int, float)) or isinstance(action, bool) or action < 0:
            return None
        rates = {"characters": rate("spoken_characters_per_second"), "words": rate("spoken_words_per_second"),
                 "action": float(action), "reading": rate("on_screen_text_characters_per_second")}
        return rates if rates["characters"] or rates["words"] else None
    return None


def blocks(text: str) -> List[str]:
    """Screenplay blocks: blank-line separated, comments and heading lines dropped.

    A heading line ends a block, so a scene written straight under its heading
    keeps its content.
    """

    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"(?m)^[ \t]*#.*$", "", text)
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def _is_word_letter(character: str) -> bool:
    if not character.isalpha():
        return False
    name = unicodedata.name(character, "")
    return any(script in name for script in WORD_SCRIPTS)


def units(text: str) -> List[Tuple[str, bool]]:
    """Pronounced units in order: a word-script word is one unit, any other
    pronounced character is one, punctuation and marks are none.

    A run of bare digits is one word in a line that is all words and one unit
    per digit wherever characters are spoken, as the write stage reads it.
    """

    text = unicodedata.normalize("NFC", text)
    found: List[Tuple[str, bool]] = []
    digit_runs: List[Tuple[int, str]] = []
    position, length = 0, len(text)
    while position < length:
        character = text[position]
        if _is_word_letter(character) or character.isdigit():
            end, has_letter = position, False
            while end < length:
                current = text[end]
                if _is_word_letter(current):
                    has_letter = True
                elif not (unicodedata.category(current).startswith("M") or current.isdigit() or (
                        current in WORD_JOINERS and end + 1 < length
                        and (_is_word_letter(text[end + 1]) or text[end + 1].isdigit()))):
                    break
                end += 1
            if has_letter:
                found.append((text[position:end].casefold(), True))
            else:
                digit_runs.append((len(found), text[position:end]))
                found.append(("", False))
            position = end
            continue
        if not character.isspace() and unicodedata.category(character)[0] not in "PMZ":
            found.append((character, False))
        position += 1
    has_words = any(word for _, word in found)
    has_characters = any(unit and not word for unit, word in found)
    for index, digits in reversed(digit_runs):
        found[index:index + 1] = ([(digits, True)] if has_words and not has_characters
                                  else [(digit, False) for digit in digits])
    return found


def voiced_units(text: str) -> Tuple[int, int]:
    """(characters, words) a speaker pronounces."""

    found = units(text)
    words = sum(1 for _, word in found if word)
    return len(found) - words, words


def speech_seconds(words: str, pacing: Dict[str, Optional[float]]) -> Optional[float]:
    """Seconds for one line in the project's own units; None when a unit has no rate."""

    characters, latin = voiced_units(words)
    by_character, by_word = pacing["characters"], pacing["words"]
    if (characters and not by_character) or (latin and not by_word):
        return None
    return (characters / by_character if characters and by_character else 0.0) + (
        latin / by_word if latin and by_word else 0.0)


def spoken_lines(text: str, speakers: Set[str]) -> List[Tuple[Optional[str], str]]:
    """Each spoken block as (VO/OS tag, words said), notes and comments removed."""

    lines = []
    for block in blocks(text):
        found = cue(block.split("\n", 1)[0], speakers)
        if found:
            words = DIRECTION.sub("", " ".join([found.group(3), *block.split("\n")[1:]])).strip()
            lines.append((found.group(1), words))
    return lines


def beat_text(block: str, speakers: Set[str]) -> str:
    """What a block puts on screen or in the ear: the words of a line, without
    its speaker and notes, or the action itself."""

    found = cue(block.split("\n", 1)[0], speakers)
    if found:
        return DIRECTION.sub("", " ".join([found.group(3), *block.split("\n")[1:]]))
    return block


def cue(line: str, speakers: Set[str]) -> Optional[Any]:
    """A dialogue cue whose speaker is known; anything else is action."""

    found = CUE_LINE.match(line.strip())
    if found and (found.group(1) or found.group(2) in speakers):
        return found
    return None


def screenplay_speakers(text: str, named: Iterable[str] = ()) -> Set[str]:
    """Names that are surely speakers, so a colon inside action is not a line.

    A name counts when the creator names it, when it carries a VO/OS tag or a
    performance note, when it opens two or more blocks, or when it is short
    enough to be a name (four characters at most) and does not open with a
    pronoun. ``他写下两个字：军宣。`` stays action; ``检验员：合格。`` is a line.
    """

    counts: Dict[str, int] = {}
    speakers = set(named)
    for block in blocks(text):
        found = CUE_LINE.match(block.split("\n", 1)[0])
        if not found:
            continue
        name = found.group(2)
        counts[name] = counts.get(name, 0) + 1
        head = block.split("：", 1)[0].split(":", 1)[0]
        if found.group(1) or "（" in head or "(" in head:
            speakers.add(name)
    return speakers | {name for name, count in counts.items()
                       if count >= 2 or (len(name) <= NAME_MAX_CHARACTERS and not name.startswith(PRONOUNS))}


def script_timeline(text: str, pacing: Dict[str, Optional[float]],
                    length: Optional[float] = None, speakers: Optional[Set[str]] = None) -> Optional[Dict[str, Any]]:
    """Lay the screenplay out in time with the project's own rates.

    Each action paragraph takes the declared seconds; a line takes its speech
    at the declared rate for its unit (characters or words). On-screen text
    takes its reading time when the project declares a reading rate; headings
    and other production tags take no time, as in the write stage's own
    estimate. Given the storyboard's ``length``, the silent time
    stretches to fill it and the speaking rate stays as declared. Speech in a
    unit the project has no rate for leaves the timeline unknown.
    """

    known = screenplay_speakers(text) if speakers is None else speakers
    items: List[Any] = []
    for block in blocks(text):
        found = cue(block.split("\n", 1)[0], known)
        if found:
            words = DIRECTION.sub("", " ".join([found.group(3), *block.split("\n")[1:]])).strip()
            seconds = speech_seconds(words, pacing)
            if seconds is None:
                return None
            items.append((seconds, words))
        elif block.startswith(ON_SCREEN_TEXT_TAG):
            if pacing.get("reading"):
                body = block[len(ON_SCREEN_TEXT_TAG):]
                items.append((readable_characters(body) / float(pacing["reading"] or 1.0), None))
        elif not block.startswith("["):
            items.append((float(pacing["action"] or 0.0), None))
    speech = sum(seconds for seconds, words in items if words is not None)
    silent = sum(seconds for seconds, words in items if words is None)
    if length and speech > length:
        # More speech than the storyboard has time for is a plan conflict to
        # report, not something to squeeze.
        return {"duration": round(speech + silent, 2), "segments": [], "overflow": round(speech - length, 2)}
    # Speech that exactly fills the storyboard leaves no time for silence.
    stretch = (length - speech) / silent if length and silent else 1.0
    clock = 0.0
    segments = []
    for seconds, words in items:
        if words is None:
            clock += seconds * stretch
        else:
            segments.append({"s": round(clock, 2), "e": round(clock + seconds, 2), "t": words})
            clock += seconds
    return {"duration": round(clock, 2), "segments": segments}


def paragraphs(text: str, speakers: Set[str]) -> List[str]:
    """Action and spoken beats; production tags other than VO/OS are not beats.

    A line is compared by its words alone, so two lines that share only a
    speaker and a delivery note do not read as a replay.
    """

    return [beat_text(block, speakers) for block in blocks(text)
            if not block.startswith("[") or block.startswith(("[VO]", "[OS]"))]


def plan_episode(episode_dir: Path, named_speakers: Iterable[str] = ()) -> Dict[str, Any]:
    storyboard = episode_dir / "分镜.md"
    screenplay = episode_dir / "剧本.md"
    record: Dict[str, Any] = {
        "source": episode_dir.name,
        "episode": episode_number(episode_dir.name),
        "kind": "plan",
        "width": None,
        "height": None,
        "cuts": None,
        "shot_seconds": None,
        "duration": None,
        "segments": None,
    }
    if storyboard.is_file():
        text = storyboard.read_text(encoding="utf-8")
        lengths = [float(value) for value in SHOT_DURATION.findall(text)]
        shots = len(SHOT_HEADING.findall(text))
        if lengths and len(lengths) == shots:
            record["shot_seconds"] = lengths
            record["duration"] = round(sum(lengths), 3)
            record["duration_source"] = "storyboard"
        else:
            record["plan_problem"] = f"分镜.md 有 {shots} 个镜头标题、{len(lengths)} 条时长；对不上就不算镜长"
    if screenplay.is_file():
        text = screenplay.read_text(encoding="utf-8")
        speakers = screenplay_speakers(text, named_speakers)
        spoken = dialogue = vo = 0
        for tag, words in spoken_lines(text, speakers):
            spoken += spoken_characters(words)
            dialogue += dialogue_characters(words)
            if tag == "VO":
                vo += dialogue_characters(words)
        record["spoken_characters"] = spoken
        record["dialogue_characters"] = dialogue
        record["vo_characters"] = vo
        # A plan's opening and closing beats include action, so a replayed
        # gesture is caught as well as a replayed line.
        body = paragraphs(text, speakers)
        record["opening_text"] = "".join(body[:3])
        record["closing_text"] = "".join(body[-3:])
        pacing = project_pacing(episode_dir)
        if pacing is not None:
            timeline = script_timeline(text, pacing, record["duration"], speakers)
            if timeline is None:
                record["plan_problem"] = "剧本里有项目没声明语速单位的台词（字或词），台词时间不估算"
                return record
            if timeline.get("overflow"):
                record["plan_problem"] = (f"按项目语速，台词比分镜总长多 {timeline['overflow']} 秒；"
                                          "先在写作或分镜里解决，台词时间不估算")
                return record
            if not record["duration"] and timeline["duration"]:
                record["duration"] = timeline["duration"]
                record["duration_source"] = "script_estimate"
            record["segments"] = timeline["segments"]
            record["timing"] = "script_estimate"
    return record


# --------------------------------------------------------------- profile


def _median(values: Iterable[Optional[float]]) -> Optional[float]:
    present = [value for value in values if value is not None]
    return round(statistics.median(present), 2) if present else None


def episode_numbers(record: Dict[str, Any]) -> Dict[str, Optional[float]]:
    duration = record.get("duration")
    lengths = record.get("shot_seconds") or []
    segments = record.get("segments") or []
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
    elif duration and record.get("segments") == [] and (record.get("timing") or record.get("transcript_source")):
        # A timed plan with no lines, or footage whose transcript has no
        # speech, is known to be silent, not unmeasured, and has to pull the
        # series medians down rather than drop out.
        numbers.update(speech_share=0.0, chars_per_second=0.0, longest_silence=round(duration, 2))
    elif record.get("spoken_characters") is not None and duration:
        numbers.update(chars_per_second=round(record["spoken_characters"] / duration, 2))
    if record.get("dialogue_characters"):
        numbers.update(vo_share=round(record["vo_characters"] / record["dialogue_characters"], 2))
    return numbers


def verified_segments(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Transcript cues inside the picture.

    A cue running past the picture is a recognition error, not speech: its
    timing and its text are both unverified, so every count leaves it out.
    """

    duration = record.get("duration")
    segments = record.get("segments") or []
    if not segments or not duration or record.get("kind") == "plan":
        return list(segments)
    return [{**segment, "e": min(segment["e"], duration)} for segment in segments
            if segment["s"] < duration and segment["e"] <= duration + OVERRUN_TOLERANCE_SECONDS]


def transcript_overrun(record: Dict[str, Any]) -> bool:
    duration = record.get("duration")
    segments = record.get("segments") or []
    return bool(duration and segments
                and max(segment["e"] for segment in segments) > duration + OVERRUN_TOLERANCE_SECONDS)


def _shared_run(tail: List[str], head: List[str]) -> int:
    return SequenceMatcher(None, tail, head, autojunk=False).find_longest_match(0, len(tail), 0, len(head)).size


def reprise(previous: Dict[str, Any], following: Dict[str, Any]) -> Optional[int]:
    """Longest run of units (characters, or words for word scripts) the next
    opening shares with the previous ending."""

    if previous.get("closing_text") and following.get("opening_text"):
        return _shared_run([unit for unit, _ in units(previous["closing_text"])],
                           [unit for unit, _ in units(following["opening_text"])])
    tail_segments = verified_segments(previous)
    head_segments = verified_segments(following)
    if not tail_segments or not head_segments or not previous.get("duration"):
        return None
    tail = [unit for unit, _ in units(" ".join(
        segment["t"] for segment in tail_segments
        if segment["e"] > previous["duration"] - REPRISE_WINDOW_SECONDS
    ))]
    head = [unit for unit, _ in units(" ".join(
        segment["t"] for segment in head_segments if segment["s"] < REPRISE_WINDOW_SECONDS
    ))]
    if not tail or not head:
        return 0
    return _shared_run(tail, head)


def profile(records: Sequence[Dict[str, Any]], opening: int) -> Dict[str, Any]:
    ordered = sorted(
        (record for record in records if record.get("episode") is not None),
        key=lambda record: record["episode"],
    )
    rows = {record["episode"]: episode_numbers(record) for record in ordered}
    keys = sorted({key for row in rows.values() for key in row})

    def group(selector) -> Dict[str, Any]:
        chosen = [row for episode, row in rows.items() if selector(episode)]
        return {"episodes": len(chosen), **{key: _median(row.get(key) for row in chosen) for key in keys}}

    later: List[float] = [
        float(row["duration"] or 0) for episode, row in rows.items() if episode > opening and row.get("duration")
    ]
    regime: Dict[str, Any] = {"opening_durations": [rows[episode]["duration"] for episode in rows if episode <= opening]}
    if len(later) >= 5:
        ranked = sorted(later)
        low, high = ranked[len(ranked) // 10], ranked[(9 * len(ranked)) // 10]
        regime.update(later_p10=round(low, 1), later_p90=round(high, 1),
                      later_fixed_length=high - low <= FIXED_LENGTH_SPREAD_SECONDS)
    pairs = []
    by_episode = {record["episode"]: record for record in ordered}
    for episode, record in by_episode.items():
        following = by_episode.get(episode + 1)
        if following is None:
            continue
        shared = reprise(record, following)
        if shared is not None:
            pairs.append(shared >= REPRISE_MIN_SHARED_UNITS)
    sources = sorted({record.get("kind", "footage") for record in ordered})
    return {
        "sources": sources,
        "transcript_overruns": [record["episode"] for record in ordered if transcript_overrun(record)],
        "opening": group(lambda episode: episode <= opening),
        "later": group(lambda episode: episode > opening),
        "all": group(lambda episode: True),
        "length_regime": regime,
        "reprise_pairs": {"checked": len(pairs), "replayed": sum(pairs)},
        "per_episode": {str(episode): row for episode, row in rows.items()},
    }


def load_records(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    records = []
    for path in paths:
        files = sorted(path.glob(f"*{MEASURE_SUFFIX}")) if path.is_dir() else [path]
        for file in files:
            records.append(json.loads(file.read_text(encoding="utf-8")))
    if not records:
        raise BreakdownError("没有找到 *.measure.json；先运行 measure 或 plan")
    return records


def render_table(profiles: Dict[str, Dict[str, Any]]) -> str:
    columns = [
        ("duration", "集长s"), ("avg_shot", "平均镜长"), ("median_shot", "中位镜长"),
        ("long_shot_share", ">4s镜占比"), ("speech_share", "有声占比"),
        ("chars_per_speech_second", "字/发声秒"), ("chars_per_second", "字/秒"),
        ("vo_share", "VO占比"), ("first_line_at", "首句s"), ("tail_after_last_line", "末句后s"),
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
        pairs = result["reprise_pairs"]
        fixed = regime.get("later_fixed_length")
        lines.append(
            f"- {name}：开头几集时长 {regime['opening_durations']}；"
            + (f"之后 p10–p90 为 {regime['later_p10']}–{regime['later_p90']} 秒"
               + ("（近似定长）" if fixed else "") + "；" if "later_p10" in regime else "")
            + (f"相邻集开头重放上一集结尾 {pairs['replayed']}/{pairs['checked']}" if pairs["checked"]
               else "相邻集开头是否重放上一集结尾：无数据（缺相邻集或缺台词时间）")
            + ("；计划值，台词时间按项目语速估算" if "plan" in result["sources"] else "")
            + (f"；转写超出片长的集：{result['transcript_overruns']}，超出部分未计入" if result["transcript_overruns"] else "")
        )
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

    plan = sub.add_parser("plan", help="读项目自己的分镜与剧本，按同一口径记录计划值")
    plan.add_argument("project", type=Path)
    plan.add_argument("--out", type=Path, required=True)
    plan.add_argument("--speaker", action="append", default=[],
                      help="只出场一次、没有表演注的说话人，可重复；否则「名字：」开头的一次性段落按动作计")

    prof = sub.add_parser("profile", help="按系列汇总已测量的集")
    prof.add_argument("series", nargs="+", help="名称=目录，例如 REF-A=输入/对标/REF-A/measure")
    prof.add_argument("--opening", type=int, default=3, help="单列统计的开头集数（默认 3）")
    prof.add_argument("--json", action="store_true", help="输出完整 JSON 而不是表格")

    args = parser.parse_args(argv)
    try:
        if args.command == "measure":
            for video in args.videos:
                print(measure_video(video, args.out, args.scene_threshold, not args.no_sheet))
        elif args.command == "transcript":
            attach_transcript(args.measure, args.transcript)
            print(args.measure)
        elif args.command == "plan":
            if (args.project / "分镜.md").is_file() or (args.project / "剧本.md").is_file():
                episodes = [args.project]
            else:
                episodes = sorted(path for path in (args.project / "剧集").glob("*") if path.is_dir())
            if not episodes:
                raise BreakdownError(f"{args.project} 既不是一集的目录，{args.project / '剧集'} 下也没有分集目录")
            args.out.mkdir(parents=True, exist_ok=True)
            for episode in episodes:
                target = args.out / f"{episode.name}{MEASURE_SUFFIX}"
                target.write_text(
                    json.dumps(plan_episode(episode, args.speaker), ensure_ascii=False, indent=1), encoding="utf-8"
                )
                print(target)
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
