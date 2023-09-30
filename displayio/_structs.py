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

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_Displayio.git"


@dataclass
class TransformStruct:
    # pylint: disable=invalid-name
    """Transform Struct Dataclass"""
    x: int = 0
    y: int = 0
    dx: int = 1
    dy: int = 1
    scale: int = 1
    width: int = 0
    height: int = 0
    mirror_x: bool = False
    mirror_y: bool = False
    transpose_xy: bool = False


@dataclass
class ColorspaceStruct:
    # pylint: disable=invalid-name, too-many-instance-attributes
    """Colorspace Struct Dataclass"""
    depth: int
    bytes_per_cell: int = 0
    tricolor_hue: int = 0
    tricolor_luma: int = 0
    grayscale_bit: int = 0
    grayscale: bool = False
    tricolor: bool = False
    sevencolor: bool = False  # Acep e-ink screens.
    pixels_in_byte_share_row: bool = False
    reverse_pixels_in_byte: bool = False
    reverse_bytes_in_word: bool = False
    dither: bool = False


@dataclass
class InputPixelStruct:
    """InputPixel Struct Dataclass"""

    pixel: int = 0
    x: int = 0
    y: int = 0
    tile: int = 0
    tile_x: int = 0
    tile_y: int = 0


@dataclass
class OutputPixelStruct:
    """OutputPixel Struct Dataclass"""

    pixel: int = 0
    opaque: bool = False


@dataclass
class ColorStruct:
    """Color Struct Dataclass"""

    rgb888: int = 0
    cached_colorspace: ColorspaceStruct = None
    cached_color: int = 0
    cached_colorspace_grayscale_bit: int = 0
    cached_colorspace_grayscale: bool = False
    transparent: bool = False


null_transform = TransformStruct()  # Use defaults
