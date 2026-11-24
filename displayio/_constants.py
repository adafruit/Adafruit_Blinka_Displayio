# SPDX-FileCopyrightText: 2021 James Carr
#
# SPDX-License-Identifier: MIT


"""Constants"""

import os

import adafruit_blinka


__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_Displayio.git"


def _read_display_limit() -> int:
    """Read Blinka's display limit once at import."""
    key = "BLINKA_DISPLAY_LIMIT"
    get_setting = getattr(adafruit_blinka, "get_setting", os.environ.__getitem__)
    try:
        value = get_setting(key)
    except KeyError:
        value = 1

    message = f"{key} must be a positive integer"
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(message)
    try:
        limit = int(value)
    except ValueError as error:
        raise ValueError(message) from error
    if limit < 1:
        raise ValueError(message)
    return limit


DISPLAY_COMMAND = 0
DISPLAY_DATA = 1

CHIP_SELECT_UNTOUCHED = 0
CHIP_SELECT_TOGGLE_EVERY_BYTE = 1

BACKLIGHT_IN_OUT = 1
BACKLIGHT_PWM = 2

NO_COMMAND = 0x100
CIRCUITPY_DISPLAY_LIMIT = _read_display_limit()

DELAY = 0x80
