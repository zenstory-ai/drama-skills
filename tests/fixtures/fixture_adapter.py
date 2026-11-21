#!/usr/bin/env python3
"""Offline adapter fixture for image, video, TTS, and music production tests."""

from __future__ import annotations

import argparse
import base64
import json
import struct
import sys
import wave
from pathlib import Path

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "short-drama-produce fixture needs Python {}.{} or newer".format(
            *MINIMUM_PYTHON
        )
    )

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail", action="store_true")
    # A real video provider bills at submission and can be interrupted at any
    # point afterwards. `--submit-then-fail` reproduces exactly that: record the
    # handle the way a live adapter does, then die before returning anything.
    parser.add_argument("--submit-then-fail", action="store_true")
    args = parser.parse_args()
    job = json.load(sys.stdin.buffer)
    collecting = job.get("collect_provider_job_id")
    if args.submit_then_fail and not collecting:
        destination = job.get("handle_path")
        if isinstance(destination, str) and destination:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"provider_job_id": "fixture-task-1"}), encoding="utf-8"
            )
        return 7
    if args.fail:
        return 7
    directory_raw = job.get("output_root")
    if not isinstance(directory_raw, str):
        return 8
    directory = Path(directory_raw)
    if not directory.is_absolute() or not directory.is_dir() or directory.is_symlink():
        return 8
    outputs = []
    for index, target in enumerate(job["outputs"]):
        suffix = Path(target).suffix.lower()
        path = directory / f"output-{index}{suffix}"
        if job["modality"] == "image":
            path.write_bytes(PNG)
        elif job["modality"] == "video":
            path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 24)
        else:
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(8000)
                handle.writeframes(struct.pack("<h", 0) * 80)
        outputs.append({"target": target, "source": str(path)})
    response = {"outputs": outputs, "provider_job_id": "fixture-local"}
    if isinstance(collecting, str) and collecting:
        response["provider_job_id"] = collecting
    json.dump(response, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
