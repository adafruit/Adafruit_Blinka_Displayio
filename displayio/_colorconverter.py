# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.colorconverter`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

from ._colorspace import Colorspace


class ColorConverter:
    """Converts one color format to another. Color converter based on original displayio
    code for consistency.
    """

    def __init__(
        self, *, input_colorspace: Colorspace = Colorspace.RGB888, dither: bool = False
    ):
        """Create a ColorConverter object to convert color formats.
        Only supports rgb888 to RGB565 currently.
        :param bool dither: Adds random noise to dither the output image
        """
        self._dither = dither
        self._depth = 16
        self._transparent_color = None
        self._rgba = False
        self._input_colorspace = input_colorspace

    def _compute_rgb565(self, color: int):
        self._depth = 16
        return (color[0] & 0xF8) << 8 | (color[1] & 0xFC) << 3 | color[2] >> 3

    @staticmethod
    def _compute_luma(color: int):
        red = color >> 16
        green = (color >> 8) & 0xFF
        blue = color & 0xFF
        return (red * 19) / 255 + (green * 182) / 255 + (blue + 54) / 255

    @staticmethod
    def _compute_chroma(color: int):
        red = color >> 16
        green = (color >> 8) & 0xFF
        blue = color & 0xFF
        return max(red, green, blue) - min(red, green, blue)

    def _compute_hue(self, color: int):
        red = color >> 16
        green = (color >> 8) & 0xFF
        blue = color & 0xFF
        max_color = max(red, green, blue)
        chroma = self._compute_chroma(color)
        if chroma == 0:
            return 0
        hue = 0
        if max_color == red:
            hue = (((green - blue) * 40) / chroma) % 240
        elif max_color == green:
            hue = (((blue - red) + (2 * chroma)) * 40) / chroma
        elif max_color == blue:
            hue = (((red - green) + (4 * chroma)) * 40) / chroma
        if hue < 0:
            hue += 240

        return hue

    @staticmethod
    def _dither_noise_1(noise):
        noise = (noise >> 13) ^ noise
        more_noise = (
            noise * (noise * noise * 60493 + 19990303) + 1376312589
        ) & 0x7FFFFFFF
        return (more_noise / (1073741824.0 * 2)) * 255

    def _dither_noise_2(self, x, y):
        return self._dither_noise_1(x + y * 0xFFFF)

    def _compute_tricolor(self):
        pass

    def convert(self, color: int) -> int:
        "Converts the given rgb888 color to RGB565"
        if isinstance(color, int):
            color = ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF, 255)
        elif isinstance(color, tuple):
            if len(color) == 3:
                color = (color[0], color[1], color[2], 255)
            elif len(color) != 4:
                raise ValueError("Color must be a 3 or 4 value tuple")
        else:
            raise ValueError("Color must be an integer or 3 or 4 value tuple")

        if self._dither:
            return color  # To Do: return a dithered color
        if self._rgba:
            return color
        return self._compute_rgb565(color)

    def make_transparent(self, color: int) -> None:
        """Set the transparent color or index for the ColorConverter. This will
        raise an Exception if there is already a selected transparent index.
        """
        self._transparent_color = color

    def make_opaque(self, color: int) -> None:
        # pylint: disable=unused-argument
        """Make the ColorConverter be opaque and have no transparent pixels."""
        self._transparent_color = None

    @property
    def dither(self) -> bool:
        """When true the color converter dithers the output by adding
        random noise when truncating to display bitdepth
        """
        return self._dither

    @dither.setter
    def dither(self, value: bool):
        if not isinstance(value, bool):
            raise ValueError("Value should be boolean")
        self._dither = value
