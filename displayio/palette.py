# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.palette`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class Palette:
    """Map a pixel palette_index to a full color. Colors are transformed to the display’s
    format internally to save memory.
    """

    def __init__(self, color_count):
        """Create a Palette object to store a set number of colors."""
        self._needs_refresh = False

        self._colors = []
        for _ in range(color_count):
            self._colors.append(self._make_color(0))
            self._update_rgba(len(self._colors) - 1)

    def _update_rgba(self, index):
        color = self._colors[index]["rgb888"]
        transparent = self._colors[index]["transparent"]
        self._colors[index]["rgba"] = (
            color >> 16,
            (color >> 8) & 0xFF,
            color & 0xFF,
            0 if transparent else 0xFF,
        )

    def _make_color(self, value, transparent=False):
        color = {
            "transparent": transparent,
            "rgb888": 0,
            "rgba": (0, 0, 0, 255),
        }
        if isinstance(value, (tuple, list, bytes, bytearray)):
            value = (value[0] & 0xFF) << 16 | (value[1] & 0xFF) << 8 | value[2] & 0xFF
        elif isinstance(value, int):
            if not 0 <= value <= 0xFFFFFF:
                raise ValueError("Color must be between 0x000000 and 0xFFFFFF")
        else:
            raise TypeError("Color buffer must be a buffer, tuple, list, or int")
        color["rgb888"] = value
        self._needs_refresh = True

        return color

    def __len__(self):
        """Returns the number of colors in a Palette"""
        return len(self._colors)

    def __setitem__(self, index, value):
        """Sets the pixel color at the given index. The index should be
        an integer in the range 0 to color_count-1.

        The value argument represents a color, and can be from 0x000000 to 0xFFFFFF
        (to represent an RGB value). Value can be an int, bytes (3 bytes (RGB) or
        4 bytes (RGB + pad byte)), bytearray, or a tuple or list of 3 integers.
        """
        if self._colors[index]["rgb888"] != value:
            self._colors[index] = self._make_color(value)
            self._update_rgba(index)

    def __getitem__(self, index):
        if not 0 <= index < len(self._colors):
            raise ValueError("Palette index out of range")
        return self._colors[index]

    def make_transparent(self, palette_index):
        """Set the palette index to be a transparent color"""
        self._colors[palette_index]["transparent"] = True
        self._update_rgba(palette_index)

    def make_opaque(self, palette_index):
        """Set the palette index to be an opaque color"""
        self._colors[palette_index]["transparent"] = False
        self._update_rgba(palette_index)

    def _get_palette(self):
        """Generate a palette for use with PIL"""
        palette = []
        for color in self._colors:
            palette += color["rgba"][0:3]
        return palette

    def _get_alpha_palette(self):
        """Generate an alpha channel palette with white being
        opaque and black being transparent"""
        palette = []
        for color in self._colors:
            for _ in range(3):
                palette += [0 if color["transparent"] else 255]
        return palette
