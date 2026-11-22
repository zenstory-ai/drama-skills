#!/usr/bin/env python3
"""Build-time vendoring sync for shared helper regions in standalone skill scripts.

Skills in `skills/*` must stay self-contained standalone units with zero runtime
imports from repository-root packages. This tool keeps canonical helper snippets
in `src/_shared/*.py` and verifies (`--check`) or updates (`--write`) marked
regions (`# BEGIN SHARED: <name>` ... `# END SHARED: <name>`) inside consumer
scripts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SHARED_TARGETS: dict[str, tuple[str, tuple[str, ...]]] = {
    "cn_num": (
        "src/_shared/cn_num.py",
        (
            "skills/short-drama-novel-analyze/scripts/novel_index.py",
            "skills/short-drama-develop/scripts/episode_intake.py",
        ),
    ),
}


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _extract_region(text: str, name: str, label: str) -> tuple[int, int, str]:
    begin_marker = f"# BEGIN SHARED: {name}\n"
    end_marker = f"# END SHARED: {name}"
    start = text.find(begin_marker)
    if start == -1:
        raise ValueError(f"{label}: missing marker {begin_marker.strip()!r}")
    if text.find(begin_marker, start + len(begin_marker)) != -1:
        raise ValueError(f"{label}: duplicate marker {begin_marker.strip()!r}")
    end = text.find(end_marker, start + len(begin_marker))
    if end == -1:
        raise ValueError(f"{label}: missing marker {end_marker!r}")
    end += len(end_marker)
    if text.find(end_marker, end) != -1:
        raise ValueError(f"{label}: duplicate marker {end_marker!r}")
    return start, end, text[start:end]


def sync_all(root: Path = ROOT, *, write: bool = False) -> list[str]:
    """Check or write all vendored shared regions. Returns list of drift messages."""
    drifts: list[str] = []
    for name, (source_rel, target_rels) in SHARED_TARGETS.items():
        source_path = root / source_rel
        if not source_path.is_file():
            drifts.append(f"{source_rel}: shared source file is missing")
            continue
        source_text = _normalize_newlines(source_path.read_text(encoding="utf-8"))
        _, _, canonical_block = _extract_region(source_text, name, source_rel)

        for target_rel in target_rels:
            target_path = root / target_rel
            if not target_path.is_file():
                drifts.append(f"{target_rel}: target file is missing")
                continue
            raw_target = target_path.read_text(encoding="utf-8")
            uses_crlf = "\r\n" in raw_target
            normalized_target = _normalize_newlines(raw_target)
            start, end, current_block = _extract_region(
                normalized_target, name, target_rel
            )
            if current_block != canonical_block:
                if write:
                    updated = (
                        normalized_target[:start]
                        + canonical_block
                        + normalized_target[end:]
                    )
                    if uses_crlf:
                        updated = updated.replace("\n", "\r\n")
                    with target_path.open("w", encoding="utf-8", newline="") as handle:
                        handle.write(updated)
                else:
                    drifts.append(
                        f"{target_rel}: shared region {name!r} drifted from {source_rel}; "
                        "run `python3 tools/sync_shared.py --write`"
                    )
    return drifts


def check_sync(root: Path = ROOT) -> list[str]:
    return sync_all(root, write=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync or check vendored shared helper regions across skill scripts."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any vendored region differs from src/_shared/.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Update vendored regions in place from src/_shared/.",
    )
    args = parser.parse_args(argv)

    if args.write:
        sync_all(ROOT, write=True)
        drifts = check_sync(ROOT)
        if drifts:
            for item in drifts:
                print(f"ERROR: {item}", file=sys.stderr)
            return 1
        print("Synced all shared regions successfully.")
        return 0

    drifts = check_sync(ROOT)
    if drifts:
        for item in drifts:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1
    print("All vendored shared regions are in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
