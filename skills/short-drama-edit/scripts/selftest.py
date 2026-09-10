#!/usr/bin/env python3
"""Offline self-test for cut-list parsing and mechanical checks.

Runs without ffmpeg: every assertion here is about the document, not the media.
The media-dependent paths are exercised by the suite's tests instead.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edit_tool import (  # noqa: E402
    EditError,
    _ass_text,
    _build_ass,
    _shot_match_filter,
    _subtitle_cues,
    check_cuts,
    parse_cut_list,
)

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("selftest.py requires Python 3.9 or newer")

MOTION = """# EP001 视频提示词

## MOTION-EP001-010 · 手指停在发布键上

## MOTION-EP001-011 · 认证弹窗展开
"""

SCREENPLAY = """# EP001

## EP001-SC003 内 · 房间 · 夜

角色甲：这条路我自己走。
"""

CUT_LIST = """# EP001 剪辑单

- 成片目标时长：5.00 秒
- 交付响度：-16 LUFS
- 未采用镜头：MOTION-EP001-009（理由：文件缺失——尚未生产）

## CUT-EP001-001 · 手指停在发布键上

- 来源：MOTION-EP001-010 · media/010.mp4
- 入点：0.60
- 出点：3.60
- 时长：3.00
- 取舍：入点=手指已经在下压；出点=界面开始响应
- 声音：保留原声
- 字幕：无

## CUT-EP001-002 · 那句话

- 来源：MOTION-EP001-011 · media/011.mp4
- 入点：0.00
- 出点：2.00
- 时长：2.00
- 取舍：入点=文件起点；出点=句尾收音后
- 声音：保留原声
- 字幕：这条路我自己走
"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build(root: Path, cut_list: str) -> Path:
    episode = root / "剧集" / "EP001"
    (episode / "media").mkdir(parents=True)
    (episode / "视频提示词.md").write_text(MOTION, encoding="utf-8")
    (episode / "剧本.md").write_text(SCREENPLAY, encoding="utf-8")
    (episode / "剪辑单.md").write_text(cut_list, encoding="utf-8")
    for name in ("010.mp4", "011.mp4"):
        (episode / "media" / name).write_bytes(b"")
    return episode


def check_subtitle_geometry() -> None:
    """FontSize is already in PlayRes units; scaling it by the frame twice ruins it.

    Letting ffmpeg convert an SRT hands libass a 384-high canvas and every size
    is then multiplied by height/384 on the way to the frame. Computing the size
    from the real height on top of that produced type a third of the frame wide,
    sitting in the middle of the picture with both ends of the line cut off — and
    it shipped, because the render after the style change was checked with
    numbers instead of a frame.
    """

    width, height = 768, 1344
    ass = _build_ass([(1.0, 2.0, "这条路我自己走")], width, height)
    require(f"PlayResX: {width}" in ass, "PlayResX 必须等于画面宽")
    require(f"PlayResY: {height}" in ass, "PlayResY 必须等于画面高")
    style = next(line for line in ass.splitlines() if line.startswith("Style:"))
    fields = style.split(":", 1)[1].split(",")
    font_size = float(fields[2])
    require(
        height * 0.02 <= font_size <= height * 0.06,
        f"字号 {font_size} 不在画面高度的 2%–6% 之间",
    )
    margin_v = float(fields[21])
    require(margin_v < height * 0.2, f"底边距 {margin_v} 会把字幕推离安全区")
    margin_h = float(fields[19])
    require(margin_h > 0, "左右边距为 0 时长句会顶到画面边缘")
    require("这条路我自己走" in ass, "台词原文必须原样进 ASS")


def check_subtitle_timing() -> None:
    """Cues follow the segments that were written, not the numbers in the document.

    Each segment lands on a frame boundary, so it runs a few milliseconds past
    its declared length. Accumulating the declared numbers drifts, and the
    subtitle leaves before the actor stops speaking.
    """

    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        episode = build(root, CUT_LIST)
        _, cuts, _ = parse_cut_list(episode / "剪辑单.md")
        declared = [cut.end - cut.start for cut in cuts]
        measured = [span + 0.04 for span in declared]

        drifting = _subtitle_cues(cuts, declared)
        真实 = _subtitle_cues(cuts, measured)
        require(len(真实) == 1, f"应有一条字幕，实际 {len(真实)}")
        require(
            真实[0][0] > drifting[0][0],
            "分段比声明更长时，后面的字幕必须相应后移",
        )
        require(
            abs(真实[0][0] - (drifting[0][0] + 0.04)) < 1e-6,
            "位移必须等于前面各段的实测差之和",
        )


def check_shot_match() -> None:
    """A declared correction is applied; an undeclared one never is.

    Generated shots drift a stop apart, so the join reads as a mistake. The
    correction has to be visible in the document — a tool that measured clips
    and adjusted them on its own would be changing pictures nobody could review.
    """

    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        episode = build(root, CUT_LIST)
        _, cuts, _ = parse_cut_list(episode / "剪辑单.md")
        require(_shot_match_filter(cuts[0]) == "", "没写画面的段不得被改动")

        listed = CUT_LIST.replace(
            "- 声音：保留原声\n- 字幕：无",
            "- 声音：保留原声\n- 画面：亮度 +0.06；色温 -6\n- 字幕：无", 1)
        (episode / "剪辑单.md").write_text(listed, encoding="utf-8")
        _, cuts, _ = parse_cut_list(episode / "剪辑单.md")
        chain = _shot_match_filter(cuts[0])
        require("brightness=0.06" in chain, f"亮度没进滤镜链: {chain}")
        require("colorbalance" in chain and "rm=-0.06" in chain, f"色温没进滤镜链: {chain}")

        # ffmpeg 的 eq 只接受 0..3 的饱和度；负数在文档里通过、渲染时才炸。
        negative = CUT_LIST.replace(
            "- 声音：保留原声\n- 字幕：无",
            "- 声音：保留原声\n- 画面：饱和 -1.5\n- 字幕：无", 1)
        (episode / "剪辑单.md").write_text(negative, encoding="utf-8")
        try:
            parse_cut_list(episode / "剪辑单.md")
        except EditError as error:
            require("超出允许范围" in str(error), f"负饱和度报错不对: {error}")
        else:
            raise AssertionError("饱和 -1.5 应当被拒绝——ffmpeg 不接受负饱和度")

        # 超出范围是重新调色，不是接镜，必须挡住。
        wild = CUT_LIST.replace(
            "- 声音：保留原声\n- 字幕：无",
            "- 声音：保留原声\n- 画面：亮度 +0.9\n- 字幕：无", 1)
        (episode / "剪辑单.md").write_text(wild, encoding="utf-8")
        try:
            parse_cut_list(episode / "剪辑单.md")
        except EditError as error:
            require("超出允许范围" in str(error), f"越界报错不对: {error}")
        else:
            raise AssertionError("亮度 +0.9 应当被拒绝")

        # 写了内容却没有可执行项，是写错了，不能静默当成不校正。
        vague = CUT_LIST.replace(
            "- 声音：保留原声\n- 字幕：无",
            "- 声音：保留原声\n- 画面：调暖一点\n- 字幕：无", 1)
        (episode / "剪辑单.md").write_text(vague, encoding="utf-8")
        try:
            parse_cut_list(episode / "剪辑单.md")
        except EditError as error:
            require("没有可执行的项" in str(error), f"含混报错不对: {error}")
        else:
            raise AssertionError("「调暖一点」应当被拒绝")


def check_multi_subtitle() -> None:
    """A shot can carry several lines, and all of them must reach the screen.

    The exchange "就是什么 / 就是少了点东西 / 少了什么" is one over-shoulder shot.
    A cut list that holds only one subtitle per cut silently drops the other
    two: the film plays lines that never appear, and nothing reports it.
    """

    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        episode = build(root, CUT_LIST)
        (episode / "剧本.md").write_text(
            SCREENPLAY + "\n角色甲：就是什么。\n角色甲：就是少了点东西。\n角色甲：少了什么。\n",
            encoding="utf-8",
        )
        multi = CUT_LIST.replace(
            "- 字幕：这条路我自己走",
            "- 字幕 1：0.10-0.60 就是什么\n"
            "- 字幕 2：0.80-1.40 就是少了点东西\n"
            "- 字幕 3：1.50-1.90 少了什么",
        )
        (episode / "剪辑单.md").write_text(multi, encoding="utf-8")
        _, cuts, _ = parse_cut_list(episode / "剪辑单.md")
        require(len(cuts[1].subtitles) == 3, f"三句应全部解析，实际 {len(cuts[1].subtitles)}")
        require(cuts[1].subtitles[2][2] == "少了什么", "字幕顺序错了")
        require(not check_cuts(episode, cuts, root, probe=False), "三句合法字幕不该报错")
        cues = _subtitle_cues(cuts, [cut.end - cut.start for cut in cuts])
        require(len(cues) == 3, f"三句应各自成为一条 cue，实际 {len(cues)}")

        # 编号必须连续：跳号意味着有一句被漏掉了。
        gap = CUT_LIST.replace(
            "- 字幕：这条路我自己走",
            "- 字幕 1：0.10-0.60 就是什么\n- 字幕 3：1.50-1.90 少了什么",
        )
        (episode / "剪辑单.md").write_text(gap, encoding="utf-8")
        try:
            parse_cut_list(episode / "剪辑单.md")
        except EditError as error:
            require("连续" in str(error), f"跳号报错不对: {error}")
        else:
            raise AssertionError("字幕编号跳号应当被拒绝")

        # 两句不能同时在屏上。
        overlap = CUT_LIST.replace(
            "- 字幕：这条路我自己走",
            "- 字幕 1：0.10-1.00 就是什么\n- 字幕 2：0.80-1.40 就是少了点东西",
        )
        (episode / "剪辑单.md").write_text(overlap, encoding="utf-8")
        try:
            parse_cut_list(episode / "剪辑单.md")
        except EditError as error:
            require("重叠" in str(error), f"重叠报错不对: {error}")
        else:
            raise AssertionError("字幕时间重叠应当被拒绝")

        # 多句时每句必须自带时间，否则无从摆放。
        untimed = CUT_LIST.replace(
            "- 字幕：这条路我自己走",
            "- 字幕 1：就是什么\n- 字幕 2：0.80-1.40 就是少了点东西",
        )
        (episode / "剪辑单.md").write_text(untimed, encoding="utf-8")
        try:
            parse_cut_list(episode / "剪辑单.md")
        except EditError as error:
            require("各自带时间" in str(error), f"缺时间报错不对: {error}")
        else:
            raise AssertionError("多句字幕缺时间应当被拒绝")


def check_stale_window() -> None:
    """Regenerating a shot invalidates every subtitle window bound to it.

    The windows were reverse-engineered from the old take's audio. Nothing else
    notices the change: the numbers stay in range, the render still succeeds,
    and the subtitle appears at a moment when nobody is speaking.
    """

    import os
    import time

    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        timed = CUT_LIST.replace(
            "- 字幕：诸君，且听龙吟",
            "- 字幕：诸君，且听龙吟\n- 字幕时间：0.30-1.60",
        )
        episode = build(root, timed)
        _, cuts, _ = parse_cut_list(episode / "剪辑单.md")
        require(
            not check_cuts(episode, cuts, root, probe=False),
            "素材不比剪辑单新时不该报陈旧",
        )

        media = episode / "media" / "011.mp4"
        listing = episode / "剪辑单.md"
        newer = listing.stat().st_mtime + 60
        os.utime(media, (newer, newer))
        findings = check_cuts(episode, cuts, root, probe=False)
        require(
            any("素材比剪辑单新" in item for item in findings),
            f"重出后的陈旧字幕时间没抓到: {findings}",
        )

        # 改过剪辑单之后就不再报——那正是「重测并改」的动作。
        time.sleep(0.01)
        listing.write_text(timed, encoding="utf-8")
        later = newer + 60
        os.utime(listing, (later, later))
        _, cuts, _ = parse_cut_list(listing)
        require(
            not any("素材比剪辑单新" in item for item in check_cuts(episode, cuts, root, probe=False)),
            "改过剪辑单之后不该继续报陈旧",
        )


def check_ass_escaping() -> None:
    """A quoted line keeps every character it had in 剧本.md.

    `{`…`}` is an override block in ASS: unescaped, libass drops the braces and
    everything between them, on screen, with no error anywhere. EDT-05 exists to
    keep the burned text equal to the screenplay's character for character.
    """

    line = "他念出来：{姓名}，请签字。"
    escaped = _ass_text(line)
    require("\\{" in escaped and "\\}" in escaped, f"花括号没有转义: {escaped}")
    require("姓名" in escaped, "转义把字弄丢了")
    ass = _build_ass([(1.0, 2.0, line)], 1080, 1920)
    dialogue = [row for row in ass.splitlines() if row.startswith("Dialogue")][0]
    require(dialogue.endswith(escaped), f"Dialogue 行没有用转义后的正文: {dialogue}")
    require(
        _ass_text("反斜杠 \\N 不是换行").count("\\\\") == 1,
        "反斜杠没有转义，\\N 会被当成换行",
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        episode = build(root, CUT_LIST)
        delivery, cuts, unused = parse_cut_list(episode / "剪辑单.md")
        require(delivery.target_seconds == 5.0, "目标时长没有解析出来")
        require(delivery.loudness_lufs == -16.0, "交付响度没有解析出来")
        require(len(cuts) == 2, f"应解析出 2 段，实际 {len(cuts)}")
        require(len(unused) == 1, "未采用镜头没有解析出来")
        require(cuts[1].subtitles[0][2] == "这条路我自己走", "字幕文字没有解析出来")

        clean = check_cuts(episode, cuts, root, probe=False)
        require(not clean, f"完好的剪辑单不该有 findings: {clean}")

        # 出点 - 入点 与声明时长不符必须抓到。
        drifted = CUT_LIST.replace("- 时长：3.00", "- 时长：2.50")
        (episode / "剪辑单.md").write_text(drifted, encoding="utf-8")
        _, cuts, _ = parse_cut_list(episode / "剪辑单.md")
        findings = check_cuts(episode, cuts, root, probe=False)
        require(any("与「时长" in item for item in findings), f"时长漂移没抓到: {findings}")

        # 字幕必须能在剧本里找到原文；转写猜出来的字不行。
        invented = CUT_LIST.replace("字幕：这条路我自己走", "字幕：这条陆我自己走")
        (episode / "剪辑单.md").write_text(invented, encoding="utf-8")
        _, cuts, _ = parse_cut_list(episode / "剪辑单.md")
        findings = check_cuts(episode, cuts, root, probe=False)
        require(any("找不到原文" in item for item in findings), f"编造的字幕没抓到: {findings}")

        # 未知 MOTION 必须抓到。
        unknown = CUT_LIST.replace("MOTION-EP001-011", "MOTION-EP001-099")
        (episode / "剪辑单.md").write_text(unknown, encoding="utf-8")
        _, cuts, _ = parse_cut_list(episode / "剪辑单.md")
        findings = check_cuts(episode, cuts, root, probe=False)
        require(any("不在《视频提示词.md》中" in item for item in findings), f"未知 MOTION 没抓到: {findings}")

        # 素材缺失必须抓到。
        (episode / "media" / "011.mp4").unlink()
        (episode / "剪辑单.md").write_text(CUT_LIST, encoding="utf-8")
        _, cuts, _ = parse_cut_list(episode / "剪辑单.md")
        findings = check_cuts(episode, cuts, root, probe=False)
        require(any("素材不存在" in item for item in findings), f"缺素材没抓到: {findings}")

        # 同一素材上的两段不得重叠。
        overlapping = CUT_LIST.replace(
            "- 来源：MOTION-EP001-011 · media/011.mp4", "- 来源：MOTION-EP001-011 · media/010.mp4"
        ).replace("- 入点：0.00", "- 入点：1.00").replace("- 出点：2.00", "- 出点：3.00")
        (episode / "media" / "011.mp4").write_bytes(b"")
        (episode / "剪辑单.md").write_text(overlapping, encoding="utf-8")
        _, cuts, _ = parse_cut_list(episode / "剪辑单.md")
        findings = check_cuts(episode, cuts, root, probe=False)
        require(any("区间重叠" in item for item in findings), f"同源重叠没抓到: {findings}")

        # 缺字段是文档缺陷，报出来而不是崩掉。
        (episode / "剪辑单.md").write_text(
            CUT_LIST.replace("- 出点：3.60\n", ""), encoding="utf-8"
        )
        try:
            parse_cut_list(episode / "剪辑单.md")
        except EditError as error:
            require("出点" in str(error), f"缺字段的报错没点名字段: {error}")
        else:
            raise AssertionError("缺「出点」应当报错")

    check_subtitle_geometry()
    check_subtitle_timing()
    check_shot_match()
    check_ass_escaping()
    check_multi_subtitle()
    check_stale_window()
    print("short-drama-edit self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
