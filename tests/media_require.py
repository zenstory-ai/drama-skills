"""Fail-closed media toolchain checks for CI runs with FFMPEG_REQUIRED=1."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _find_tool(name: str, *, include_local_bin: bool = False) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    if include_local_bin:
        candidate = Path.home() / ".local" / "bin" / name
        if candidate.is_file():
            return str(candidate)
    return None


def _has_ass_filter(ffmpeg: str) -> bool:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-filters"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    return re.search(r"^\s*[A-Z.]+\s+ass\s+", result.stdout, re.MULTILINE) is not None


def has_ffmpeg(
    *,
    require_ass: bool = False,
    include_local_bin: bool = False,
) -> bool:
    """Return True when ffmpeg/ffprobe are available; fail closed if FFMPEG_REQUIRED=1."""
    required = os.environ.get("FFMPEG_REQUIRED") == "1"
    ffmpeg = _find_tool("ffmpeg", include_local_bin=include_local_bin)
    ffprobe = _find_tool("ffprobe", include_local_bin=include_local_bin)
    if not ffmpeg or not ffprobe:
        if required:
            raise RuntimeError(
                "FFMPEG_REQUIRED=1 but ffmpeg and ffprobe are not both available"
            )
        return False
    if require_ass and not _has_ass_filter(ffmpeg):
        if required:
            raise RuntimeError(
                "FFMPEG_REQUIRED=1 but ffmpeg lacks the libass 'ass' filter"
            )
        return False
    return True
