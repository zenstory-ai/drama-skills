import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/short-drama-edit/scripts/edit_tool.py"
SPEC = importlib.util.spec_from_file_location("edit_measurements", SCRIPT)
assert SPEC and SPEC.loader
edit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(edit)


class EditMeasurementsTests(unittest.TestCase):
    def test_checks_reject_mixed_dimensions_or_fps_before_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cuts = [edit.Cut(f"CUT-{i}", "shot", f"MOTION-{i}", f"{i}.mp4",
                             0, 2, 2, (), {}, i) for i in (1, 2)]
            (root / edit.MOTION_DOCUMENT).write_text("## MOTION-1\n\n## MOTION-2\n")
            for i in (1, 2):
                (root / f"{i}.mp4").touch()
            first = {"width": 1344, "height": 768, "fps": 24, "duration": 5}
            for changes, expected in (({}, 0), ({"width": 1282, "height": 718}, 1),
                                      ({"fps": 30}, 1)):
                with self.subTest(changes=changes), patch.object(
                    edit, "probe_stream", side_effect=[first, {**first, **changes}]
                ):
                    findings = edit.check_cuts(root, cuts, root, probe=True)
                self.assertEqual(len(findings), expected)

    def test_omission_requires_exact_id_and_nonempty_reason(self):
        known = {"MOTION-EP001-001"}
        for note in (
            "MOTION-EP001-0010（理由：重复）",
            "MOTION-EP001-002（理由：已用 MOTION-EP001-001）",
            "MOTION-EP001-001",
            "MOTION-EP001-001（理由： ）",
        ):
            with self.subTest(note=note):
                self.assertTrue(edit._unaccounted_shots(known, [], [note]))
        self.assertEqual(
            edit._unaccounted_shots(known, [], ["MOTION-EP001-001（理由：重复信息）"]), []
        )
        self.assertEqual(
            edit._unaccounted_shots(known, [SimpleNamespace(motion=next(iter(known)))], []), []
        )

    def test_colour_observations_follow_current_cuts_and_report_missing_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            segments = root / edit.SEGMENT_DIRECTORY
            segments.mkdir()
            for name in ("DAY", "NIGHT", "STALE"):
                (segments / f"{name}.mp4").touch()
            cuts = [SimpleNamespace(cut_id=name) for name in ("NIGHT", "MISSING", "DAY")]
            with patch.object(edit, "_segment_colour", side_effect=[(30, 20), (180, -10)]) as measure:
                rows = edit._segment_colours("ffmpeg", root, cuts)
            self.assertEqual([c.args[1].stem for c in measure.call_args_list], ["NIGHT", "DAY"])
            self.assertEqual(rows, [
                {"分段": "NIGHT.mp4", "平均亮度": 30, "蓝减红": 20},
                {"分段": "MISSING.mp4", "测量": "未测（分段缺失或不可读）"},
                {"分段": "DAY.mp4", "平均亮度": 180, "蓝减红": -10},
            ])

    def test_unreadable_colour_sample_is_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / edit.SEGMENT_DIRECTORY).mkdir()
            (root / edit.SEGMENT_DIRECTORY / "BROKEN.mp4").touch()
            with patch.object(edit, "_segment_colour", return_value=None):
                rows = edit._segment_colours("ffmpeg", root, [SimpleNamespace(cut_id="BROKEN")])
            self.assertEqual(rows, [{"分段": "BROKEN.mp4", "测量": "未测（分段缺失或不可读）"}])
