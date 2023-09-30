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

from typing import Optional, Union, Tuple
from circuitpython_typing import ReadableBuffer
from ._colorconverter import ColorConverter
from ._colorspace import Colorspace
from ._structs import InputPixelStruct, OutputPixelStruct, ColorStruct

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class Palette:
    """Map a pixel palette_index to a full color. Colors are transformed to the display's
    format internally to save memory.
    """

    def __init__(self, color_count: int, *, dither: bool = False):
        """Create a Palette object to store a set number of colors.

        :param int color_count: The number of colors in the Palette
        :param bool dither: When true, dither the RGB color before converting to the
                            display's color space
        """
        self._needs_refresh = False
        self._dither = dither

        self._colors = []
        for _ in range(color_count):
            self._colors.append(ColorStruct())

    @staticmethod
    def _color_to_int(value):
        if isinstance(value, (tuple, list, bytes, bytearray)):
            value = (value[0] & 0xFF) << 16 | (value[1] & 0xFF) << 8 | value[2] & 0xFF
        elif isinstance(value, int):
            if not 0 <= value <= 0xFFFFFF:
                raise ValueError("Color must be between 0x000000 and 0xFFFFFF")
        else:
            raise TypeError("Color buffer must be a buffer, tuple, list, or int")
        return value

    def __len__(self) -> int:
        """Returns the number of colors in a Palette"""
        return len(self._colors)

    def __setitem__(
        self,
        index: int,
        value: Union[int, ReadableBuffer, Tuple[int, int, int]],
    ) -> None:
        """Sets the pixel color at the given index. The index should be
        an integer in the range 0 to color_count-1.

        The value argument represents a color, and can be from 0x000000 to 0xFFFFFF
        (to represent an RGB value). Value can be an int, bytes (3 bytes (RGB) or
        4 bytes (RGB + pad byte)), bytearray, or a tuple or list of 3 integers.
        """
        self._set_color(index, self._color_to_int(value))

    def _set_color(self, palette_index: int, color: int):
        if self._colors[palette_index].rgb888 == color:
            return
        self._colors[palette_index].rgb888 = color
        self._colors[palette_index].cached_colorspace = None
        self._needs_refresh = True

    def __getitem__(self, index: int) -> Optional[int]:
        if not 0 <= index < len(self._colors):
            raise ValueError("Palette index out of range")
        return self._colors[index].rgb888

    def make_transparent(self, palette_index: int) -> None:
        """Set the palette index to be a transparent color"""
        self._colors[palette_index].transparent = True
        self._needs_refresh = True

    def make_opaque(self, palette_index: int) -> None:
        """Set the palette index to be an opaque color"""
        self._colors[palette_index].transparent = False
        self._needs_refresh = True

    def _get_color(
        self,
        colorspace: Colorspace,
        input_pixel: InputPixelStruct,
        output_color: OutputPixelStruct,
    ):
        palette_index = input_pixel.pixel
        if palette_index > len(self._colors) or self._colors[palette_index].transparent:
            output_color.opaque = False
            return

        color = self._colors[palette_index]
        if (
            not self._dither
            and color.cached_colorspace == colorspace
            and color.cached_colorspace_grayscale_bit == colorspace.grayscale_bit
            and color.cached_colorspace_grayscale == colorspace.grayscale
        ):
            output_color.pixel = self._colors[palette_index].cached_color
            return

        rgb888_pixel = input_pixel
        rgb888_pixel.pixel = self._colors[palette_index].rgb888
        ColorConverter._convert_color(  # pylint: disable=protected-access
            colorspace, self._dither, rgb888_pixel, output_color
        )
        if not self._dither:
            color.cached_colorspace = colorspace
            color.cached_color = output_color.pixel
            color.cached_colorspace_grayscale = colorspace.grayscale
            color.cached_colorspace_grayscale_bit = colorspace.grayscale_bit

    def is_transparent(self, palette_index: int) -> bool:
        """Returns True if the palette index is transparent. Returns False if opaque."""
        return self._colors[palette_index].transparent

    def _finish_refresh(self):
        self._needs_refresh = False

    @property
    def dither(self) -> bool:
        """When true the palette dithers the output by adding
        random noise when truncating to display bitdepth
        """
        return self._dither

    @dither.setter
    def dither(self, value: bool):
        if not isinstance(value, bool):
            raise ValueError("Value should be boolean")
        self._dither = value
