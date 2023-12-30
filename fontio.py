# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`fontio`
================================================================================

fontio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

import os
from dataclasses import dataclass
from typing import Union, Tuple, Optional
from displayio import Bitmap

try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

DEFAULT_FONT = "displayio/resources/ter-u12n.bdf"


class FontProtocol(Protocol):
    """A protocol shared by `BuiltinFont` and classes in ``adafruit_bitmap_font``"""

    def get_bounding_box(self) -> Union[Tuple[int, int], Tuple[int, int, int, int]]:
        """Retrieve the maximum bounding box of any glyph in the font.

        The four element version is ``(width, height, x_offset, y_offset)``.
        The two element version is ``(width, height)``, in which
        ``x_offset`` and ``y_offset`` are assumed to be zero.
        """

    def get_glyph(self, codepoint: int) -> Optional["Glyph"]:
        """Retrieve the Glyph for a given code point

        If the code point is not present in the font, `None` is returned.
        """


class BuiltinFont:
    """Simulate a font built into CircuitPython"""

    def __init__(self):
        self._width = 0
        self._height = 0

        # Place import here to avoid circular import
        from adafruit_bitmap_font import (  # pylint: disable=import-outside-toplevel
            bitmap_font,
        )

        self._font = bitmap_font.load_font(
            os.path.dirname(__file__) + "/" + DEFAULT_FONT
        )

        self._font.load_glyphs(set(range(0x20, 0x7F)))

    def get_bounding_box(self) -> Union[Tuple[int, int], Tuple[int, int, int, int]]:
        """Returns the maximum bounds of all glyphs in the font in
        a tuple of two values: width, height.
        """
        return self._font.get_bounding_box()[0:2]

    def get_glyph(self, codepoint: int) -> Optional["Glyph"]:
        """Returns a `fontio.Glyph` for the given codepoint or None if no glyph is available."""
        return self._font.get_glyph(codepoint)

    @property
    def bitmap(self):
        """Bitmap containing all font glyphs starting with ASCII and followed by unicode. Use
        `get_glyph` in most cases. This is useful for use with `displayio.TileGrid` and
        `terminalio.Terminal`.
        """
        return self._font.bitmap_class


@dataclass
class Glyph:
    # pylint: disable=invalid-name
    """Storage of glyph info"""
    bitmap: Bitmap
    tile_index: int
    width: int
    height: int
    dx: int
    dy: int
    shift_x: int
    shift_y: int
