# SPDX-FileCopyrightText: 2021 Melissa LeBlanc-Williams
#
# SPDX-License-Identifier: MIT

"""
`displayio._structs`
================================================================================

Struct Data Classes for Blinka Displayio

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from dataclasses import dataclass

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_Displayio.git"


@dataclass
class RectangleStruct:
    # pylint: disable=invalid-name
    """Rectangle Struct Dataclass. To eventually be replaced by Area."""
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class TransformStruct:
    # pylint: disable=invalid-name
    """Transform Struct Dataclass"""
    x: int = 0
    y: int = 0
    dx: int = 1
    dy: int = 1
    scale: int = 1
    transpose_xy: bool = False
    mirror_x: bool = False
    mirror_y: bool = False


@dataclass
class ColorspaceStruct:
    # pylint: disable=invalid-name
    """Colorspace Struct Dataclass"""
    depth: int
    bytes_per_cell: int = 0
    tricolor_hue: int = 0
    tricolor_luma: int = 0
    grayscale_bit: int = 0
    grayscale: bool = False
    tricolor: bool = False
    pixels_in_byte_share_row: bool = False
    reverse_pixels_in_byte: bool = False
    reverse_bytes_in_word: bool = False
    dither: bool = False
