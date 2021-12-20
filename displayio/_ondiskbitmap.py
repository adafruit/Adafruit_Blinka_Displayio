# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.ondiskbitmap`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from typing import Union, BinaryIO
from PIL import Image
from ._colorconverter import ColorConverter
from ._palette import Palette

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class OnDiskBitmap:
    """
    Loads values straight from disk. This minimizes memory use but can lead to much slower
    pixel load times. These load times may result in frame tearing where only part of the
    image is visible."""

    def __init__(self, file: Union[str, BinaryIO]):
        self._image = Image.open(file).convert("RGBA")

    @property
    def width(self) -> int:
        """Width of the bitmap. (read only)"""
        return self._image.width

    @property
    def height(self) -> int:
        """Height of the bitmap. (read only)"""
        return self._image.height

    @property
    def pixel_shader(self) -> Union[ColorConverter, Palette]:
        """The ColorConverter or Palette for this image. (read only)"""
        return self._image.getpalette()

    def __getitem__(self, index: Union[tuple, list, int]) -> int:
        """
        Returns the value at the given index. The index can either be
        an x,y tuple or an int equal to `y * width + x`.
        """
        if isinstance(index, (tuple, list)):
            x = index[0]
            y = index[1]
        elif isinstance(index, int):
            x = index % self._image._width
            y = index // self._image._width
        if not 0 <= x < self._image.width or not 0 <= y < self._image.height:
            return 0

        return self._image.getpixel((x, y))
