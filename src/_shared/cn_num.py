"""Canonical Chinese numeral parser vendored into standalone skill scripts.

Source of truth for `tools/sync_shared.py`. Do not import this module directly
from `skills/*/scripts/*.py` (skills must remain self-contained standalone
units); instead run `python3 tools/sync_shared.py --write` to sync the marked
region into each consumer script.
"""

from __future__ import annotations

# BEGIN SHARED: cn_num
CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000}


def chinese_to_int(text: str) -> int | None:
    """Convert 一 / 十五 / 两百零三 / 两零八 / 一千零十五 to an int, or None if malformed."""
    if not text:
        return None
    if text.isascii() and text.isdigit():
        return int(text)
    if all(character in CHINESE_DIGITS for character in text):
        if "两" in text[1:]:
            return None
        value = 0
        for character in text:
            value = value * 10 + CHINESE_DIGITS[character]
        return value
    if not all(
        character in CHINESE_DIGITS or character in CHINESE_UNITS
        for character in text
    ):
        return None

    total = 0
    previous_weight: int | None = None
    pending_digit: int | None = None
    saw_zero = False

    for index, character in enumerate(text):
        if character in CHINESE_DIGITS:
            digit = CHINESE_DIGITS[character]
            if digit == 0:
                if previous_weight is None or pending_digit is not None or saw_zero:
                    return None
                saw_zero = True
            else:
                if pending_digit is not None:
                    return None
                pending_digit = digit
            continue

        weight = CHINESE_UNITS[character]
        if pending_digit is None:
            if character == "十" and (
                (index == 0 and not saw_zero)
                or (saw_zero and previous_weight is not None and previous_weight >= 1000)
            ):
                digit = 1
            else:
                return None
        else:
            digit = pending_digit
            pending_digit = None

        if previous_weight is not None:
            if weight >= previous_weight:
                return None
            if (previous_weight > weight * 10) != saw_zero:
                return None
        saw_zero = False
        previous_weight = weight
        total += digit * weight

    if pending_digit is None:
        return None if saw_zero else total
    assert previous_weight is not None
    if (previous_weight > 10) != saw_zero:
        return None
    return total + pending_digit
# END SHARED: cn_num
