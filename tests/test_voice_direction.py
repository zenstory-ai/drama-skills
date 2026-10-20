import unittest
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
ASSETS = SUITE / "skills/short-drama-assets"


class RuleTests(unittest.TestCase):
    def test_one_spelling_per_pronunciation_blocks(self) -> None:
        # A second spelling is invisible in text review and only audible in the
        # finished cut, so it cannot wait for a judgement call.
        contract = (ASSETS / "references/stage-contract.md").read_text(encoding="utf-8")
        row = next(r for r in contract.splitlines() if r.startswith("| AST-10 "))
        self.assertIn("structural_invariant", row)


if __name__ == "__main__":
    unittest.main()
