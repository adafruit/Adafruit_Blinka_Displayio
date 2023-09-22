# SPDX-FileCopyrightText: 2023 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.helpers`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


def clamp(value, min_value, max_value):
    """Clamp a value between a minimum and maximum value"""
    return max(min(max_value, value), min_value)


def bswap16(value):
    """Swap the bytes in a 16 bit value"""
    return (value & 0xFF00) >> 8 | (value & 0x00FF) << 8
