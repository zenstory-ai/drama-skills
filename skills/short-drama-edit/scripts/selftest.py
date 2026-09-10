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

from edit_tool import EditError, check_cuts, parse_cut_list  # noqa: E402

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("selftest.py requires Python 3.9 or newer")

MOTION = """# EP001 视频提示词

## MOTION-EP001-010 · 手指停在发布键上

## MOTION-EP001-011 · 认证弹窗展开
"""

SCREENPLAY = """# EP001

## EP001-SC003 内 · 剪辑室 · 夜

江尘：诸君，且听龙吟。
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
- 字幕：诸君，且听龙吟
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


def main() -> int:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        episode = build(root, CUT_LIST)
        delivery, cuts, unused = parse_cut_list(episode / "剪辑单.md")
        require(delivery.target_seconds == 5.0, "目标时长没有解析出来")
        require(delivery.loudness_lufs == -16.0, "交付响度没有解析出来")
        require(len(cuts) == 2, f"应解析出 2 段，实际 {len(cuts)}")
        require(len(unused) == 1, "未采用镜头没有解析出来")
        require(cuts[1].subtitle == "诸君，且听龙吟", "字幕文字没有解析出来")

        clean = check_cuts(episode, cuts, root, probe=False)
        require(not clean, f"完好的剪辑单不该有 findings: {clean}")

        # 出点 - 入点 与声明时长不符必须抓到。
        drifted = CUT_LIST.replace("- 时长：3.00", "- 时长：2.50")
        (episode / "剪辑单.md").write_text(drifted, encoding="utf-8")
        _, cuts, _ = parse_cut_list(episode / "剪辑单.md")
        findings = check_cuts(episode, cuts, root, probe=False)
        require(any("与「时长" in item for item in findings), f"时长漂移没抓到: {findings}")

        # 字幕必须能在剧本里找到原文；转写猜出来的字不行。
        invented = CUT_LIST.replace("字幕：诸君，且听龙吟", "字幕：朱军且听龙银")
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

    print("short-drama-edit self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
