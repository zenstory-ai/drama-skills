from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = ROOT / "skills/short-drama/scripts/creator_markdown_check.py"
VIEWS_SCRIPT = ROOT / "skills/short-drama/scripts/creator_views.py"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


check = _load_module("test_core_creator_markdown_check", CHECK_SCRIPT)
views = _load_module("test_core_creator_views", VIEWS_SCRIPT)


def _minimal_episode_texts(
    *,
    motion_duration: str = "6s",
    motion_prompt: str,
    shot_duration: str | None = None,
    shot_framing: str = "近景，平视",
) -> dict[str, str]:
    board_duration = shot_duration or motion_duration
    return {
        "剧本.md": (
            "# EP001 · 测试集\n\n"
            "## EP001-SC001 内 · 茶室 · 白天\n\n"
            "林岚推门进来。\n\n"
            "林岚：先坐下说。\n"
        ),
        "视觉设定.md": (
            "# EP001 视觉设定\n\n"
            "- 制作形态：实拍\n\n"
            "## 人物 · 林岚\n"
            "- 外观特征：黑长发、米色风衣。\n"
            "- 角色声线：清亮平稳女声。\n"
            "- 提示词名称：林岚, Lin Lan\n\n"
            "## 地点 · 茶室\n"
            "- 空间特征：木桌与落地窗。\n"
        ),
        "图片提示词.md": (
            "# EP001 图片提示词\n\n"
            "## IMG-LINLAN-SHEET · 林岚角色板\n"
            "- 用途：角色设定\n"
            "- 参考：无外部参考\n\n"
            "### 可复制提示词\n"
            "> 林岚站在茶室木桌旁，米色风衣，自然光。\n"
        ),
        "分镜.md": (
            "# EP001 分镜\n\n"
            "## SHOT-EP001-001 · 茶室开场\n"
            "- 来源：EP001-SC001\n"
            f"- 时长：{board_duration}\n"
            "- 目的：交代谈话开场。\n"
            f"- 景别/机位：{shot_framing}\n"
            "- 运镜：固定。\n"
            "- 起点：林岚推门进屋。\n"
            "- 动作：林岚落座开口。\n"
            "- 终点：林岚直视对面。\n"
            "- 图片提示词项：IMG-LINLAN-SHEET《林岚角色板》（控制：外貌与风衣）\n"
            "- 输入参考图：无（文生视频）\n"
            "- 出场设定：《视觉设定.md》·人物「林岚」（控制：外貌）；地点「茶室」（控制：木桌与窗光）\n"
            "- 声音：林岚现场对白。\n\n"
            "### 首帧提示词\n"
            "> 茶室木桌旁，林岚穿米色风衣平视前方，自然窗光。\n"
        ),
        "视频提示词.md": (
            "# EP001 视频提示词\n\n"
            "## MOTION-EP001-001 · 茶室开场\n"
            "- 分镜：SHOT-EP001-001\n"
            f"- 时长：{motion_duration}\n"
            "- 生成方式：文生视频\n"
            "- 输入参考图：无（文生视频）\n"
            "- 开场画面：茶室木桌旁，林岚穿米色风衣平视前方，自然窗光。\n"
            "- 起始帧：林岚站在木桌旁。\n"
            "- 动作过程：林岚落座开口说话。\n"
            "- 终点：林岚直视对面。\n\n"
            "### 可复制提示词\n"
            f"> {motion_prompt}\n"
        ),
    }


def _write_project(
    root: Path,
    texts: dict[str, str],
    manifest: dict[str, object] | None,
) -> Path:
    episode = root / "剧集/EP001"
    episode.mkdir(parents=True, exist_ok=True)
    for name, body in texts.items():
        (episode / name).write_text(body, encoding="utf-8")
    if manifest is not None:
        (root / "short-drama.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return episode


class SpeechRateSoftGateTests(unittest.TestCase):
    """F-10: soft-gate single-shot speech-rate warning against declared pacing."""

    def test_normal_and_slightly_brisk_shots_emit_zero_warnings(self) -> None:
        # 4.2 chars/sec * 6s = 25.2 chars; 28 chars => 6.67s => 1.11x (<= 1.35x).
        prompt = (
            "固定近景，林岚落座抬眼，{林岚用中文说：“先坐下把桌上的合同看清，"
            "我们今天只谈这一件事，别绕弯子了。”}，无字幕叠加。"
        )
        manifest = {
            "format": {
                "prompt_language": "zh-CN",
                "pacing": {"spoken_characters_per_second": 4.2},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode = _write_project(
                root,
                _minimal_episode_texts(motion_duration="6s", motion_prompt=prompt),
                manifest,
            )
            result = check.validate_episode_with_warnings(episode, root)
            self.assertEqual(result.errors, [])
            self.assertEqual(result.warnings, [])

    def test_overloaded_chinese_shot_warns_softly_and_exits_zero(self) -> None:
        # 64 Chinese chars in 6s at 4.2 chars/sec => ~15.2s (2.54x) -> soft WARNING.
        prompt = (
            "固定近景，林岚语气急促，{林岚用中文说：“这份合同里所有条款我都逐页核对过了，"
            "你们上个月临时改掉的违约金比例、交付节点和回款顺序全都和当初会议纪要完全对不上，"
            "今天必须当场改回原版！”}，无字幕叠加。"
        )
        manifest = {
            "format": {
                "prompt_language": "zh-CN",
                "pacing": {"spoken_characters_per_second": 4.2},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode = _write_project(
                root,
                _minimal_episode_texts(motion_duration="6s", motion_prompt=prompt),
                manifest,
            )
            result = check.validate_episode_with_warnings(episode, root)
            self.assertEqual(result.errors, [])
            self.assertEqual(len(result.warnings), 1)
            self.assertIn("MOTION-EP001-001", result.warnings[0])
            self.assertIn("VID-05", result.warnings[0])

            cli = subprocess.run(
                [sys.executable, str(CHECK_SCRIPT), str(episode), "--project-root", str(root)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)
            self.assertIn("WARNING:", cli.stdout)
            self.assertIn("MOTION-EP001-001", cli.stdout)
            self.assertIn("OK:", cli.stdout)
            self.assertNotIn("ERROR:", cli.stdout)

    def test_supports_d_tags_wan_and_english_word_rate(self) -> None:
        cases = (
            (
                "minimax_h3_d_tag",
                "5s",
                "[Shot 1] Lin Lan leans forward and says: "
                "<d>[Chinese] 这件事从头到尾都是你们在推脱责任，今天不把账本摊开说清楚谁都别想离开这间茶室。</d>",
                {"spoken_characters_per_second": 4.0},
                "en",
            ),
            (
                "wan_chinese_cue",
                "5s",
                "近景固定，林岚盯着桌面冷声说道：“你把前三个季度的出入库清单全部藏起来，"
                "现在还敢当着大伙的面说账目没问题，真当大家都不识数吗？”",
                {"spoken_characters_per_second": 4.0},
                "zh-CN",
            ),
            (
                "english_words_overloaded",
                "4s",
                'Close shot, Lin Lan speaks rapidly: "We already checked every single invoice from last quarter '
                'and none of these numbers match the signed ledger you handed over yesterday morning."',
                {"spoken_words_per_second": 3.0},
                "en",
            ),
        )
        for label, duration, prompt, pacing, prompt_lang in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                episode = _write_project(
                    root,
                    _minimal_episode_texts(motion_duration=duration, motion_prompt=prompt),
                    {"format": {"prompt_language": prompt_lang, "pacing": pacing}},
                )
                result = check.validate_episode_with_warnings(episode, root)
                self.assertEqual(result.errors, [])
                self.assertTrue(
                    any("MOTION-EP001-001" in warning for warning in result.warnings),
                    result.warnings,
                )

    def test_undeclared_or_invalid_pacing_emits_no_speech_warning(self) -> None:
        overloaded_prompt = (
            "{林岚用中文说：“这份合同里所有条款我都逐页核对过了，"
            "你们上个月临时改掉的违约金比例、交付节点和回款顺序全都和当初会议纪要完全对不上！”}"
        )
        manifests: list[dict[str, object] | None] = [
            None,
            {"format": {"prompt_language": "zh-CN", "pacing": {}}},
            {
                "format": {
                    "prompt_language": "zh-CN",
                    "pacing": {
                        "spoken_characters_per_second": None,
                        "spoken_words_per_second": None,
                    },
                }
            },
            {
                "format": {
                    "prompt_language": "zh-CN",
                    "pacing": {
                        "spoken_characters_per_second": 0,
                        "spoken_words_per_second": True,
                    },
                }
            },
        ]
        for idx, manifest in enumerate(manifests):
            with self.subTest(manifest_index=idx), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                episode = _write_project(
                    root,
                    _minimal_episode_texts(motion_duration="4s", motion_prompt=overloaded_prompt),
                    manifest,
                )
                result = check.validate_episode_with_warnings(episode, root)
                self.assertEqual(result.errors, [])
                speech_warnings = [w for w in result.warnings if "实读对白" in w]
                self.assertEqual(speech_warnings, [])

    def test_on_screen_text_quotes_are_not_counted_as_spoken_dialogue(self) -> None:
        # Long quoted text on a screen/sign must NOT trigger a speech-rate warning.
        prompt = (
            'Close-up on the wall sign, where the board clearly reads: '
            '“本店所有原料均于每日清晨五点前冷链送达并由值班店长逐项核验签字留档，逾期一律拒收。” '
            'No speech, only room tone.'
        )
        manifest = {
            "format": {
                "prompt_language": "en",
                "pacing": {"spoken_characters_per_second": 4.0},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode = _write_project(
                root,
                _minimal_episode_texts(motion_duration="3s", motion_prompt=prompt),
                manifest,
            )
            result = check.validate_episode_with_warnings(episode, root)
            self.assertEqual(result.errors, [])
            self.assertEqual(result.warnings, [])


class CompoundShotScaleTests(unittest.TestCase):
    """F-09: compound and transition shot-scale matching in creator_views.py."""

    def test_compound_and_transition_scales_count_close_accurately(self) -> None:
        close_cases = (
            ("近景，平视", "近景"),
            ("手与茶杯大特写", "大特写"),
            ("面部近特写", "特写"),
            ("中景缓推至近景", "中景"),
            ("中景推至特写", "中景"),
            ("双人中近景缓推至主角孤冷近景，平视侧角度", "中近景"),
            ("全景推进至手部细节", "全景"),
            ("低机位近景起幅上摇至中全景", "近景"),
            ("桌面俯拍细节，活页纸居中", "细节"),
            ("medium shot pushing into close-up", "中景"),
            ("medium close-up push to extreme close-up", "中近景"),
            ("close-up of hands on desk", "特写"),
            ("close shot, eye level", "近景"),
            ("detail shot of the ledger", "细节"),
        )
        for framing, expected_primary in close_cases:
            with self.subTest(framing=framing):
                self.assertEqual(views.shot_scale(framing), expected_primary)
                self.assertTrue(views.is_close_framing(framing))

    def test_plain_wide_medium_and_standalone_medium_close_do_not_false_match(self) -> None:
        non_close_cases = (
            ("中景，平视", "中景"),
            ("全景，庭院纵深", "全景"),
            ("中全景，玄关斜后侧", "全景"),
            ("远景，城市天际线", "远景"),
            ("过肩中近景，桌面高度", "中近景"),
            ("中景缓推至扶手按键与冷脸中近景", "中景"),
            ("中景，画面环境细节丰富", "中景"),
            ("medium shot, static", "中景"),
            ("medium close-up, eye level", "中近景"),
            ("wide shot of the hallway", "全景"),
            ("full shot, eye level", "全景"),
            ("long shot at dusk", "远景"),
            ("越过右肩看屏幕", ""),
        )
        for framing, expected_primary in non_close_cases:
            with self.subTest(framing=framing):
                self.assertEqual(views.shot_scale(framing), expected_primary)
                self.assertFalse(views.is_close_framing(framing))

    def test_storyboard_metrics_include_transition_close_shots(self) -> None:
        storyboard = (
            "# EP001 分镜\n\n"
            "## SHOT-EP001-001 · 过渡近景\n"
            "- 来源：EP001-SC001\n"
            "- 时长：5s\n"
            "- 景别/机位：双人中近景缓推至主角近景\n"
            "- 运镜：缓推\n"
            "- 输入参考图：无（文生视频）\n"
            "- 出场设定：无\n\n"
            "### 首帧提示词\n"
            "> 中近景起幅。\n\n"
            "## SHOT-EP001-002 · 中景推特写\n"
            "- 来源：EP001-SC001\n"
            "- 时长：4s\n"
            "- 景别/机位：中景推至面部特写\n"
            "- 运镜：缓推\n"
            "- 输入参考图：无（文生视频）\n"
            "- 出场设定：无\n\n"
            "### 首帧提示词\n"
            "> 中景起幅。\n\n"
            "## SHOT-EP001-003 · 纯中景\n"
            "- 来源：EP001-SC001\n"
            "- 时长：4s\n"
            "- 景别/机位：双人中景，平视\n"
            "- 运镜：固定\n"
            "- 输入参考图：无（文生视频）\n"
            "- 出场设定：无\n\n"
            "### 首帧提示词\n"
            "> 双人中景。\n\n"
            "## SHOT-EP001-004 · 纯全景\n"
            "- 来源：EP001-SC001\n"
            "- 时长：4s\n"
            "- 景别/机位：全景，门廊斜侧\n"
            "- 运镜：固定\n"
            "- 输入参考图：无（文生视频）\n"
            "- 出场设定：无\n\n"
            "### 首帧提示词\n"
            "> 全景。\n"
        )
        parsed = views.parse_storyboard(storyboard)
        stats = views.metrics(None, parsed)
        self.assertEqual(stats["shots"], 4)
        self.assertEqual(stats["closeCount"], 2)
        self.assertEqual(stats["close"], 0.5)
        self.assertEqual(stats["unsized"], 0)
        self.assertEqual(
            [shot["close"] for shot in parsed["shots"]],
            [True, True, False, False],
        )


if __name__ == "__main__":
    unittest.main()
