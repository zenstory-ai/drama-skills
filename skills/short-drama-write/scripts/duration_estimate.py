#!/usr/bin/env python3
"""Estimate how long a screenplay runs, using the project's own declared rates.

This reports a number; it never judges one. The suite carries no cross-project
speech rate and no tolerance band, because a 90-second episode of dense argument
and a 90-second episode of silent work do not convert at the same ratio. The
creator declares the two rates their project actually uses, and this script
applies them.

Without declared rates the script still counts dialogue characters and action
paragraphs -- those counts are facts about the text -- and says the seconds
cannot be derived yet. That is the honest output, not a guess from a default.

What counts as a line and what counts as a paragraph is decided by
``screenplay-index.jsonl``, never re-derived here. This script used to carry its
own reader of the screenplay format, and a second reader of one format is a
second set of answers: it timed ``[VO]`` at zero, billed a Markdown comment as
speech, read ``他写下两个字：军宣。`` as dialogue because of the colon, and
counted one multi-line action paragraph once per line. The index already
classifies all four correctly. Reading it means this script cannot disagree with
the artifact the rest of the pipeline cites.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


# Creators run these scripts on whatever interpreter their machine provides, so
# an unsupported version must say so instead of failing inside an import.
MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "short-drama needs Python {}.{} or newer; this interpreter is {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )


# [VO] and [OS] are spoken off-camera. The format contract writes them as
# ``[VO] 角色：台词`` -- a real line. Timing them at zero silently shortens every
# episode that carries its interiority in voice-over, and the estimate then reads
# as a deficit the writer pads to fill.
VOICED_TAGS = {"VO", "OS"}
VOICE_TAG_PREFIX = re.compile(r"^\[(?:VO|OS)\]\s*")
# ``角色（提示）：台词`` -- the speaker label may carry a parenthesised direction.
# Only the spoken half is timed; the direction is a note to the performer.
DIALOGUE = re.compile(r"^(?P<who>[^：:（(\[\]]{1,24})(?:（[^）]*）|\([^)]*\))?[：:](?P<line>.+)$")


# Tags that occupy screen time without being spoken. Their seconds depend on how
# the cut holds them, so they are counted and named rather than timed -- unless
# the project declares how fast its audience reads on-screen text.
ON_SCREEN_TEXT_TAG = "画面文字"
UNTIMED_TAGS = (ON_SCREEN_TEXT_TAG, "SFX", "转场")
TAG_PREFIX = re.compile(r"^\[[^\]]+\]\s*")


class StaleIndex(Exception):
    """The index does not describe the screenplay it was handed."""


def _spoken_characters(line: str) -> int:
    """Count what is actually voiced: no whitespace, no bracketed directions."""
    stripped = re.sub(r"（[^）]*）|\([^)]*\)", "", line)
    return len(re.sub(r"\s", "", stripped))


# Scripts written with spaces between words. Their speech unit is the word: an
# English line timed letter by letter at a per-character rate came out about
# three times too long. Characters of every other script stay one unit each.
WORD_SCRIPTS = ("LATIN", "CYRILLIC", "GREEK")
# Inside a word only: don't, well-known, it’s.
WORD_JOINERS = frozenset("'’-")


def _is_word_letter(character: str) -> bool:
    if not character.isalpha():
        return False
    name = unicodedata.name(character, "")
    return any(script in name for script in WORD_SCRIPTS)


def _voiced_units(line: str) -> tuple[int, int]:
    """What a speaker actually pronounces, as (characters, words).

    Punctuation is not pronounced, so neither count includes it; the
    punctuation-inclusive count stays for the VO share, whose ceiling is
    defined on it. A run of word-script letters (digits and inner apostrophes
    or hyphens included) is one word, and every other pronounced character is
    one character, so ``OK，走吧`` is one word and two characters. A run of
    bare digits is read in the language around it: one word in a line that is
    all words, one unit per digit wherever characters are spoken, as before.
    """
    # NFC first, so an accent typed as a separate combining mark counts the
    # same as the precomposed letter.
    text = unicodedata.normalize(
        "NFC", re.sub(r"（[^）]*）|\([^)]*\)", "", line)
    )
    characters = words = 0
    digit_runs: list[int] = []
    position, length = 0, len(text)
    while position < length:
        character = text[position]
        if _is_word_letter(character) or character.isdigit():
            end, has_letter, digits = position, False, 0
            while end < length:
                current = text[end]
                if _is_word_letter(current):
                    has_letter = True
                elif unicodedata.category(current).startswith("M"):
                    pass  # a mark NFC could not fold still belongs to its letter
                elif current.isdigit():
                    digits += 1
                elif not (
                    current in WORD_JOINERS
                    and end + 1 < length
                    and (_is_word_letter(text[end + 1]) or text[end + 1].isdigit())
                ):
                    break
                end += 1
            if has_letter:
                words += 1
            else:
                digit_runs.append(digits)
            position = end
            continue
        if not character.isspace() and unicodedata.category(character)[0] not in "PM":
            characters += 1
        position += 1
    if words and not characters:
        words += len(digit_runs)
    else:
        characters += sum(digit_runs)
    return characters, words


def _readable_characters(body: str) -> int:
    """Characters a viewer reads in an on-screen text line.

    The whole tag body counts, brackets and any text before a colon included.
    ``已授予：演唱`` puts displayed words before its colon and ``暂停营业（东门）``
    displays its parentheses, so neither can be stripped as a carrier name or a
    performer's note; a line that does name its carrier is over-read by a few
    characters rather than having visible words silently dropped.
    """
    return sum(
        1
        for character in re.sub(r"\s", "", body)
        if not unicodedata.category(character).startswith("P")
    )


def _is_voiced(block: Mapping[str, Any]) -> bool:
    """Speech is a dialogue block, or a production tag that is spoken aloud."""
    kind = block.get("kind")
    if kind == "dialogue":
        return True
    return kind == "production_tag" and block.get("tag") in VOICED_TAGS


def _block_text(screenplay: bytes, block: Mapping[str, Any]) -> str | None:
    """Return the block's own bytes, or None when its span does not fit."""
    start, end = block.get("byte_start"), block.get("byte_end")
    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or not 0 <= start < end <= len(screenplay)
    ):
        return None
    try:
        return screenplay[start:end].decode("utf-8").strip()
    except UnicodeDecodeError:
        # A span that begins or ends mid-character is a stale offset, not a
        # crash: report it the same way as any other span that does not fit.
        return None


def measure(screenplay: bytes, blocks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Count the timed material, taking every classification from the index."""
    dialogue_lines = 0
    dialogue_characters = 0
    voiced_characters = 0
    voiced_words = 0
    voiceover_characters = 0
    action_paragraphs = 0
    tag_lines = 0
    untimed_lines = {tag: 0 for tag in UNTIMED_TAGS}
    on_screen_text_characters = 0
    unreadable_blocks: list[str] = []

    for block in blocks:
        if block.get("record_type") != "block":
            continue
        kind = block.get("kind")

        if kind == "action":
            # One paragraph is one block however many lines it occupies. The
            # format contract lets an action paragraph run several lines.
            action_paragraphs += 1
            continue

        if not _is_voiced(block):
            # Scene headings, comments and instruction-only tags carry no
            # performed duration. Comments are not production content at all.
            if kind == "production_tag":
                tag_lines += 1
                tag = block.get("tag")
                if tag in untimed_lines:
                    untimed_lines[tag] += 1
                if tag == ON_SCREEN_TEXT_TAG:
                    text = _block_text(screenplay, block)
                    if text is None:
                        unreadable_blocks.append(str(block.get("block_id")))
                    else:
                        on_screen_text_characters += _readable_characters(
                            TAG_PREFIX.sub("", text)
                        )
            continue

        text = _block_text(screenplay, block)
        if text is None:
            unreadable_blocks.append(str(block.get("block_id")))
            continue
        spoken = DIALOGUE.match(VOICE_TAG_PREFIX.sub("", text))
        if spoken is None:
            # The index recorded it as speech but it does not use the documented
            # line grammar. Guessing a duration here is how a wrong number gets
            # reported as a fact; the block is named instead.
            unreadable_blocks.append(str(block.get("block_id")))
            continue
        dialogue_lines += 1
        characters = _spoken_characters(spoken.group("line"))
        dialogue_characters += characters
        characters_voiced, words_voiced = _voiced_units(spoken.group("line"))
        voiced_characters += characters_voiced
        voiced_words += words_voiced
        if block.get("tag") == "VO":
            voiceover_characters += characters

    counts: dict[str, Any] = {
        "dialogue_lines": dialogue_lines,
        "dialogue_characters": dialogue_characters,
        "voiced_characters": voiced_characters,
        "voiced_words": voiced_words,
        "voiceover_characters": voiceover_characters,
        "action_paragraphs": action_paragraphs,
        "production_tag_lines": tag_lines,
    }
    if any(untimed_lines.values()):
        counts["untimed_tag_lines"] = {
            tag: number for tag, number in untimed_lines.items() if number
        }
    if untimed_lines[ON_SCREEN_TEXT_TAG]:
        counts["on_screen_text_characters"] = on_screen_text_characters
    if unreadable_blocks:
        counts["unreadable_blocks"] = sorted(unreadable_blocks)
    return counts


def index_blocks(
    index: list[dict[str, Any]], screenplay: bytes
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return the index's blocks and its own review state.

    An index built from other bytes is refused rather than measured: its spans
    would land on text it never classified.
    """
    meta = next(
        (row for row in index if row.get("record_type") == "screenplay_index_meta"),
        None,
    )
    if meta is None:
        raise StaleIndex("the index carries no screenplay_index_meta record")
    declared = meta.get("source_byte_length")
    if not isinstance(declared, int):
        raise StaleIndex("the index declares no source_byte_length")
    if declared != len(screenplay):
        raise StaleIndex(
            "the index was built from {} bytes but this screenplay is {}; "
            "rebuild it with screenplay_index.py before estimating".format(
                declared, len(screenplay)
            )
        )
    review = {
        "review_status": meta.get("review_status"),
        "source_issue_count": meta.get("source_issue_count"),
    }
    return [row for row in index if row.get("record_type") == "block"], review


def declared_rates(project: dict[str, Any] | None) -> dict[str, Any]:
    """Read the project's own pacing rates, or report that it declared none."""
    pacing = ((project or {}).get("format") or {}).get("pacing") or {}
    per_character = _rate(pacing.get("spoken_characters_per_second"))
    # Words for scripts written with spaces; a project in one language declares
    # only the speech rate it uses, a bilingual one declares both.
    per_word = _rate(pacing.get("spoken_words_per_second"))
    per_action = _rate(pacing.get("seconds_per_action_paragraph"), allow_zero=True)
    usable = (per_character is not None or per_word is not None) and per_action is not None
    reading = _rate(pacing.get("on_screen_text_characters_per_second"))
    return {
        "declared": usable,
        "spoken_characters_per_second": per_character if usable else None,
        "spoken_words_per_second": per_word if usable else None,
        "seconds_per_action_paragraph": per_action if usable else None,
        # Optional: a project that holds text on screen as its own beat can
        # declare how fast it is read. Without it the text stays untimed.
        "on_screen_text_characters_per_second": reading,
    }


def _rate(value: Any, allow_zero: bool = False) -> float | None:
    """A declared rate, or None when the value is not a usable number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        return None
    return value


def accepted_vo_share(
    counts: Mapping[str, Any], project: dict[str, Any] | None
) -> dict[str, Any] | None:
    """The [VO] share of spoken characters against an accepted ceiling.

    [OS] is off-screen dialogue inside the scene, not narration or inner
    voice, so it counts as spoken but not as voice-over.

    Only a rhythm profile the creator accepted carries a ceiling; a missing or
    proposed one declares nothing, so nothing is compared. The comparison is
    reported, never enforced: the creator may keep an episode over its own cap.
    """
    authority = (project or {}).get("creator_authority")
    profile = authority.get("rhythm_profile") if isinstance(authority, dict) else None
    if not isinstance(profile, dict) or profile.get("status") != "accepted":
        return None
    ceiling = profile.get("vo_share_max")
    if isinstance(ceiling, bool) or not isinstance(ceiling, (int, float)):
        return None
    if not (math.isfinite(ceiling) and 0 <= ceiling <= 1):
        # A hand-edited ceiling outside a share is no ceiling: comparing
        # against NaN or 5 reports a verdict nobody accepted.
        return None
    spoken = counts["dialogue_characters"]
    if not spoken:
        return None
    share = counts["voiceover_characters"] / spoken
    return {
        "share": round(share, 3),
        "vo_share_max": ceiling,
        "over_max": share > ceiling,
    }


def estimate(
    screenplay: bytes,
    blocks: Iterable[Mapping[str, Any]],
    project: dict[str, Any] | None = None,
    review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    counts = measure(screenplay, blocks)
    rates = declared_rates(project)
    target = ((project or {}).get("format") or {}).get("target_seconds_per_episode")

    result: dict[str, Any] = {"counts": counts, "rates": rates, "seconds": None}
    result["target_seconds"] = target if isinstance(target, (int, float)) else None
    vo_share = accepted_vo_share(counts, project)
    if vo_share is not None:
        result["vo_share"] = vo_share

    # Material the index could not classify is material this estimate did not
    # time. Reporting the seconds without that fact is how an incomplete number
    # gets read as a complete one.
    issues = (review or {}).get("source_issue_count")
    unreadable = counts.get("unreadable_blocks") or []
    if isinstance(issues, int) and issues > 0 or unreadable:
        result["incomplete"] = {
            "index_review_status": (review or {}).get("review_status"),
            "source_issue_count": issues,
            "unreadable_blocks": unreadable,
            "note": (
                "the index left some of this screenplay unclassified, so the "
                "counts below cover less than the whole text; resolve the index "
                "issues before reading these seconds as the episode's length"
            ),
        }

    untimed = dict(counts.get("untimed_tag_lines") or {})
    if rates["on_screen_text_characters_per_second"] is not None:
        untimed.pop(ON_SCREEN_TEXT_TAG, None)
    if untimed:
        # These lines take screen time this estimate cannot see. A storyboard
        # that holds each one long enough to read lands well above the number
        # below, so the gap is named here instead of surfacing two stages later.
        result["untimed"] = {
            "tag_lines": untimed,
            "note": (
                "these production tags take screen time that is not in the "
                "seconds; declare format.pacing.on_screen_text_characters_per_second "
                "to time on-screen text by its readable characters"
            ),
        }

    if not rates["declared"]:
        result["note"] = (
            "the project declares no format.pacing rates, so seconds cannot be "
            "derived; the counts above are still exact"
            if "incomplete" not in result
            else "the project declares no format.pacing rates, so seconds "
            "cannot be derived; the counts above are exact for the blocks the "
            "index classified, which is not all of this screenplay"
        )
        return result

    seconds = counts["action_paragraphs"] * rates["seconds_per_action_paragraph"]
    unpriced: dict[str, int] = {}
    for unit, rate_name in (
        ("voiced_characters", "spoken_characters_per_second"),
        ("voiced_words", "spoken_words_per_second"),
    ):
        if not counts[unit]:
            continue
        if rates[rate_name] is None:
            unpriced[unit] = counts[unit]
        else:
            seconds += counts[unit] / rates[rate_name]
    if unpriced:
        # Speech in a unit the project has no rate for. Borrowing the other
        # rate is the letter-by-letter error this split exists to stop, so the
        # count is named next to seconds that leave it out.
        result["untimed_speech"] = {
            "counts": unpriced,
            "note": (
                "the project declares no rate for this speech, so the seconds "
                "leave it out; declare format.pacing.spoken_words_per_second "
                "for words and spoken_characters_per_second for characters"
            ),
        }
    reading = rates["on_screen_text_characters_per_second"]
    if reading is not None and counts.get("on_screen_text_characters"):
        reading_seconds = counts["on_screen_text_characters"] / reading
        result["on_screen_text_seconds"] = round(reading_seconds, 1)
        seconds += reading_seconds
    result["seconds"] = round(seconds, 1)
    if result["target_seconds"]:
        delta = seconds - result["target_seconds"]
        result["delta_seconds"] = round(delta, 1)
        result["delta_ratio"] = round(delta / result["target_seconds"], 3)
        result["note"] = (
            "informational only: the suite sets no tolerance band, because the "
            "right spread depends on the project's own scenes"
        )
    else:
        result["note"] = (
            "no format.target_seconds_per_episode is declared, so there is "
            "nothing to compare the estimate against"
        )
    return result


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise SystemExit("{}:{}: {}".format(path, number, error))
        if isinstance(row, dict):
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Estimate screenplay duration from the project's declared rates."
    )
    parser.add_argument("screenplay", type=Path)
    parser.add_argument(
        "--index",
        type=Path,
        required=True,
        help="screenplay-index.jsonl built from this screenplay by screenplay_index.py",
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=None,
        help=(
            "short-drama.json carrying format.pacing, target_seconds_per_episode "
            "and, when accepted, creator_authority.rhythm_profile.vo_share_max"
        ),
    )
    args = parser.parse_args(argv)

    if not args.screenplay.is_file():
        raise SystemExit("screenplay not found: {}".format(args.screenplay))
    if not args.index.is_file():
        raise SystemExit("screenplay index not found: {}".format(args.index))

    project = None
    if args.project is not None:
        if not args.project.is_file():
            raise SystemExit("project file not found: {}".format(args.project))
        project = json.loads(args.project.read_text(encoding="utf-8"))

    screenplay = args.screenplay.read_bytes()
    try:
        blocks, review = index_blocks(_load_jsonl(args.index), screenplay)
    except StaleIndex as error:
        raise SystemExit("{}: {}".format(args.index, error))

    report = estimate(screenplay, blocks, project, review)
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    # An estimate is never a verdict, so this exits successfully even when the
    # episode lands far from its target. Blocking here would turn a reported
    # number into the cross-project threshold this suite refuses to carry.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
