#!/usr/bin/env python3
"""Offline self-test for breakdown measurement; needs no ffmpeg."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from breakdown_tool import MEASURE_SUFFIX, load_records, parse_transcript, plan_episode, profile

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("selftest.py requires Python 3.9 or newer")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def episode(number: int, duration: float, lines: list) -> dict:
    return {
        "episode": number,
        "duration": duration,
        "shot_seconds": [duration / 4] * 4,
        "segments": [{"s": start, "e": end, "t": text} for start, end, text in lines],
    }


def main() -> int:
    srt = "1\n00:00:00,500 --> 00:00:02,000\n站住。\n\n2\n00:00:02,200 --> 00:00:04,000\n<i>你凭什么</i>\n"
    segments = parse_transcript(srt, ".srt")
    require([segment["s"] for segment in segments] == [0.5, 2.2], "srt timings")
    require(segments[1]["t"] == "你凭什么", "srt markup stripped")

    records = [
        episode(1, 120.0, [(0.0, 3.0, "你被开除了"), (116.0, 119.5, "门外那辆车是谁的")]),
        episode(2, 50.0, [(0.2, 2.0, "那是我的车"), (46.0, 49.8, "你有种再说一遍")]),
        episode(3, 50.0, [(0.1, 2.0, "你有种再说一遍试试"), (47.0, 49.9, "走")]),
    ]
    result = profile(records, opening=1)
    require(result["opening"]["duration"] == 120.0, "opening episode measured apart")
    require(result["later"]["avg_shot"] == 12.5, "later episodes averaged")
    require(result["reprise_pairs"] == {"checked": 2, "replayed": 1}, "reprise counted per adjacent pair")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        ep = root / "剧集" / "EP001"
        ep.mkdir(parents=True)
        (ep / "分镜.md").write_text(
            "## SHOT-EP001-001 · 门口\n\n- 时长：3s\n\n## SHOT-EP001-002 · 回头\n\n- 时长：2s\n",
            encoding="utf-8",
        )
        (ep / "剧本.md").write_text(
            "## EP001-SC001 内 · 门口 · 日\n\n他推门。\n\n林舟：开门。\n\n[VO] 林舟：我回来了。\n",
            encoding="utf-8",
        )
        planned = plan_episode(ep)
        require(planned["duration"] == 5.0 and planned["shot_seconds"] == [3.0, 2.0], "plan durations")
        require(planned["spoken_characters"] == 6 and planned["vo_characters"] == 5, "plan spoken characters")
        (root / f"EP001{MEASURE_SUFFIX}").write_text(json.dumps(planned, ensure_ascii=False), encoding="utf-8")
        require(len(load_records([root])) == 1, "plan record loads like footage")

    print("8 self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
