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

from PIL import ImageFont
from displayio import Bitmap

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class BuiltinFont:
    """Simulate a font built into CircuitPython"""

    def __init__(self):
        self._font = ImageFont.load_default()
        self._generate_bitmap(0x20, 0x7E)

    def _generate_bitmap(self, start_range, end_range):
        char_width, char_height = self.get_bounding_box()
        self._bitmap = Bitmap(
            char_width * (end_range - start_range + 1), char_height, 2
        )
        for character in range(start_range, end_range + 1):
            ascii_char = chr(character)
            ascii_mask = self._font.getmask(ascii_char, mode="1")
            for y in range(char_height):
                for x in range(char_width):
                    color = ascii_mask.getpixel((x, y))
                    character_position = character - start_range
                    self._bitmap[character_position * char_width + x, y] = (
                        1 if color else 0
                    )

    def get_bounding_box(self):
        """Returns the maximum bounds of all glyphs in the font in
        a tuple of two values: width, height.
        """
        return self._font.getsize("M")

    def get_glyph(self, codepoint):
        """Returns a `fontio.Glyph` for the given codepoint or None if no glyph is available."""
        if 0x20 <= codepoint <= 0x7E:
            glyph_index = codepoint - 0x20
        else:
            return None

        bounding_box = self._font.getsize(chr(codepoint))
        width, height = bounding_box
        return Glyph(
            bitmap=self._bitmap,
            tile_index=glyph_index,
            width=width,
            height=height,
            dx=0,
            dy=0,
            shift_x=width,
            shift_y=0,
        )

    @property
    def bitmap(self):
        """Bitmap containing all font glyphs starting with ASCII and followed by unicode. Use
        `get_glyph` in most cases. This is useful for use with `displayio.TileGrid` and
        `terminalio.Terminal`.
        """
        return self._bitmap


# pylint: disable=too-few-public-methods, invalid-name, too-many-arguments
class Glyph:
    """Storage of glyph info"""

    def __init__(self, bitmap, tile_index, width, height, dx, dy, shift_x, shift_y):
        self.bitmap = bitmap
        self.width = width
        self.height = height
        self.dx = dx
        self.dy = dy
        self.shift_x = shift_x
        self.shift_y = shift_y
        self.tile_index = tile_index


# pylint: enable=too-few-public-methods, invalid-name, too-many-arguments
