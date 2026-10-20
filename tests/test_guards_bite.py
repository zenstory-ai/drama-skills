"""The guards a mutation run showed could be removed with the suite still green.

A mutation audit deleted 67 guards one at a time and ran the whole suite after
each. Fifty went red. The seventeen that did not are the ones covered here and
in `test_simple_lifecycle`: each was live code whose removal changed real
behaviour, and no test noticed.

The point of this module is not coverage in the line-counting sense. Each test
below was written against a specific mutation and confirmed to fail when that
mutation is reapplied -- a test that stays green under the break it names is
worth nothing, which is the whole finding this module answers.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

SUITE = Path(__file__).resolve().parents[1]
SKILLS = SUITE / "skills"
LEGACY = SUITE / "tests/legacy"


def _module(name: str, relative: str, root: Path = SKILLS) -> Any:
    spec = importlib.util.spec_from_file_location(name, root / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


asset_check = _module("g_asset_check", "short-drama-assets/scripts/asset_check.py", LEGACY)
provider_adapters = _module(
    "g_provider_adapters", "short-drama-produce/scripts/provider_adapters.py"
)
episode_intake = _module(
    "g_episode_intake", "short-drama-develop/scripts/episode_intake.py"
)
review_check = _module("g_review_check", "short-drama-review/scripts/review_check.py", LEGACY)
novel_index = _module("g_novel_index", "short-drama-novel-analyze/scripts/novel_index.py")
screenplay_index = _module(
    "g_screenplay_index", "short-drama-write/scripts/screenplay_index.py"
)
duration_estimate = _module(
    "g_duration_estimate", "short-drama-write/scripts/duration_estimate.py"
)
storyboard_check = _module("g_storyboard_check", "short-drama-storyboard/scripts/storyboard_check.py", LEGACY)


class RequiredFieldTests(unittest.TestCase):
    """`require_text` and `require_list` could accept anything of the right type.

    Both reduce to "any string" / "any list" with the suite green, because the
    only fixture ever handed to `asset_check` is a known-good one. A blank
    `display_name` or an empty `identity_anchors` propagates into every image
    prompt and every shot built from that asset.
    """

    def test_a_blank_required_string_is_refused(self) -> None:
        for value in ("", "   ", "\n"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(asset_check.ValidationError):
                    asset_check.require_text({"display_name": value}, "display_name", "c[0]")

    def test_an_empty_required_list_is_refused(self) -> None:
        with self.assertRaises(asset_check.ValidationError):
            asset_check.require_list({"identity_anchors": []}, "identity_anchors", "c[0]")

    def test_a_missing_required_list_is_refused(self) -> None:
        with self.assertRaises(asset_check.ValidationError):
            asset_check.require_list({}, "identity_anchors", "c[0]")


class CredentialScrubbingTests(unittest.TestCase):
    """`_safe_token` is what keeps a provider's reply out of an error report.

    Removing its allowlist leaves it echoing whatever the provider sent, into a
    file written to disk. `test_provider_adapters` is thorough about payloads
    and HTTP failures and asserted nothing about this.
    """

    def test_a_credential_shaped_string_is_not_echoed(self) -> None:
        # Spaces and punctuation are what a leaked secret or a prose error
        # message carries; the allowlist is what keeps both out of the report.
        for value in ("sk-live-SECRET KEY!", "Bearer sk-abc DEF!!", "a" * 201):
            with self.subTest(value=value[:20]):
                self.assertIsNone(provider_adapters._safe_token(value))

    def test_an_ordinary_identifier_still_passes_through(self) -> None:
        self.assertEqual(provider_adapters._safe_token("req-12ab34"), "req-12ab34")


class EpisodeIdentityTests(unittest.TestCase):
    """A merge must not write records for episodes the index does not carry.

    With the guard removed, a stale batch or an off-by-one silently creates
    phantom episodes in `episode-map.jsonl`.
    """

    def test_a_record_for_an_unknown_episode_is_refused(self) -> None:
        with self.assertRaises(Exception):
            episode_intake._validated_records(
                [{"episode_id": "EP999", "x": 1}], {"EP001", "EP002"}, "episode map"
            )


class ReviewFieldTests(unittest.TestCase):
    """`text()` is the only thing standing between a review and empty fields."""

    def test_a_blank_required_review_field_is_refused(self) -> None:
        with self.assertRaises(review_check.ValidationError):
            review_check.text({"scope": "   "}, "scope", "finding[0]")


class ChapterNumberingTests(unittest.TestCase):
    """Two rules sit next to each other in `verify_index`; only one was tested.

    Line-span contiguity had a case. Sequence-number contiguity -- immediately
    above it -- did not, and this is the same neighbourhood as the shipped
    defect where a documented rebuild did not match the script.
    """

    def test_a_gap_in_the_sequence_numbers_is_reported(self) -> None:
        """Built by the script, then renumbered by hand -- as a creator would."""

        body = "正文内容。" * 20
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "novel.txt"
            source.write_text(
                f"第一章 起\n{body}\n第二章 承\n{body}\n第三章 转\n{body}\n",
                encoding="utf-8",
            )
            index_path = root / "index.json"
            document = novel_index.build_index(source)
            index_path.write_text(json.dumps(document), encoding="utf-8")
            self.assertTrue(novel_index.verify_index(index_path, source)["verified"])

            document["chapters"][2]["sequence"] = 4
            index_path.write_text(json.dumps(document), encoding="utf-8")
            result = novel_index.verify_index(index_path, source)

        self.assertFalse(result["verified"])
        self.assertTrue(
            any("sequence" in problem for problem in result["problems"]),
            f"the sequence gap was not the reported problem: {result['problems']}",
        )

    def test_a_chapter_with_almost_no_body_is_reported(self) -> None:
        chapters = [
            {"sequence": 1, "heading": "第一章", "char_count": 5, "source_number": 1},
        ]
        problems = novel_index.validate_chapters(chapters, [chapters])
        self.assertTrue(
            any("almost no body" in problem for problem in problems),
            problems,
        )


class BlockIdentityTests(unittest.TestCase):
    """Block IDs must survive a whitespace-only edit.

    The suite covers IDs surviving an *insertion*. Nothing covered normalization
    itself, and with it removed every block in the file gets a new ID: every
    shot's `source_refs`, every keyframe boundary, every motion spec and the
    voice sheet all point at retired IDs at once.
    """

    SCREENPLAY = (
        "# EP001\n\n## EP001-SC001 内 · 客厅 · 夜\n\n"
        "陈予安推开门。\n\n陈予安：我回来了。\n"
    )

    def build(self, root: Path, text: str, previous: Path | None) -> list[dict[str, Any]]:
        source = root / "screenplay.md"
        source.write_text(text, encoding="utf-8")
        index_path = root / "index.jsonl"
        screenplay_index.build_index(
            source,
            index_path,
            source_ref="剧集/EP001/screenplay.md",
            speakers=["陈予安"],
            previous_index_path=previous,
            previous_source_path=root / "previous.md" if previous else None,
            no_previous=previous is None,
        )
        return [
            json.loads(line)
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_trailing_whitespace_does_not_renumber_every_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.build(root, self.SCREENPLAY, None)
            before = [r["block_id"] for r in first if r.get("record_type") == "block"]

            (root / "previous.md").write_text(self.SCREENPLAY, encoding="utf-8")
            (root / "index.jsonl").rename(root / "previous.jsonl")
            spaced = self.SCREENPLAY.replace("陈予安推开门。", "陈予安推开门。   ")
            second = self.build(root, spaced, root / "previous.jsonl")
            after = [r["block_id"] for r in second if r.get("record_type") == "block"]

        self.assertEqual(before, after, "a whitespace-only edit renumbered blocks")


class SpokenCharacterTests(unittest.TestCase):
    """A parenthesised direction is a note to the performer, not spoken time."""

    def test_a_parenthesised_direction_is_not_counted(self) -> None:
        self.assertEqual(duration_estimate._spoken_characters("（压着嗓子）你走"), 2)
        self.assertEqual(duration_estimate._spoken_characters("(quietly) 你走"), 2)


class UnresolvableShotTests(unittest.TestCase):
    """`SHT16_SHOT_UNRESOLVABLE` had no test; its five siblings each had one."""

    def test_a_duration_record_naming_a_missing_shot_is_caught(self) -> None:
        coverage = {
            "episode_id": "EP001",
            "dispositions": [],
            "episode_duration": {
                "shot_seconds_total": 0.0,
                "counted_shot_ids": ["SHOT-NOT-IN-THE-FILE"],
                "unresolved_durations": [],
                "target_seconds": None,
                "delta_seconds": None,
                "disposition": "no_target_declared",
            },
        }
        findings = storyboard_check.check_episode_duration(coverage, [], None)
        self.assertIn(
            "SHT16_SHOT_UNRESOLVABLE", {finding["code"] for finding in findings}
        )


if __name__ == "__main__":
    unittest.main()
