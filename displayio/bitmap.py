# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.bitmap`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from recordclass import recordclass
from PIL import Image

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

Rectangle = recordclass("Rectangle", "x1 y1 x2 y2")


class Bitmap:
    """Stores values of a certain size in a 2D array"""

    def __init__(self, width, height, value_count):
        """Create a Bitmap object with the given fixed size. Each pixel stores a value that is
        used to index into a corresponding palette. This enables differently colored sprites to
        share the underlying Bitmap. value_count is used to minimize the memory used to store
        the Bitmap.
        """
        self._bmp_width = width
        self._bmp_height = height
        self._read_only = False

        if value_count < 0:
            raise ValueError("value_count must be > 0")

        bits = 1
        while (value_count - 1) >> bits:
            if bits < 8:
                bits = bits << 1
            else:
                bits += 8

        self._bits_per_value = bits

        if (
            self._bits_per_value > 8
            and self._bits_per_value != 16
            and self._bits_per_value != 32
        ):
            raise NotImplementedError("Invalid bits per value")

        self._image = Image.new("P", (width, height), 0)
        self._dirty_area = Rectangle(0, 0, width, height)

    def __getitem__(self, index):
        """
        Returns the value at the given index. The index can either be
        an x,y tuple or an int equal to `y * width + x`.
        """
        if isinstance(index, (tuple, list)):
            x, y = index
        elif isinstance(index, int):
            x = index % self._bmp_width
            y = index // self._bmp_width
        else:
            raise TypeError("Index is not an int, list, or tuple")

        if x > self._image.width or y > self._image.height:
            raise ValueError("Index {} is out of range".format(index))
        return self._image.getpixel((x, y))

    def __setitem__(self, index, value):
        """
        Sets the value at the given index. The index can either be
        an x,y tuple or an int equal to `y * width + x`.
        """
        if self._read_only:
            raise RuntimeError("Read-only object")
        if isinstance(index, (tuple, list)):
            x = index[0]
            y = index[1]
            index = y * self._bmp_width + x
        elif isinstance(index, int):
            x = index % self._bmp_width
            y = index // self._bmp_width
        self._image.putpixel((x, y), value)
        if self._dirty_area.x1 == self._dirty_area.x2:
            self._dirty_area.x1 = x
            self._dirty_area.x2 = x + 1
            self._dirty_area.y1 = y
            self._dirty_area.y2 = y + 1
        else:
            if x < self._dirty_area.x1:
                self._dirty_area.x1 = x
            elif x >= self._dirty_area.x2:
                self._dirty_area.x2 = x + 1
            if y < self._dirty_area.y1:
                self._dirty_area.y1 = y
            elif y >= self._dirty_area.y2:
                self._dirty_area.y2 = y + 1

    def _finish_refresh(self):
        self._dirty_area.x1 = 0
        self._dirty_area.x2 = 0

    def fill(self, value):
        """Fills the bitmap with the supplied palette index value."""
        self._image = Image.new("P", (self._bmp_width, self._bmp_height), value)
        self._dirty_area = Rectangle(0, 0, self._bmp_width, self._bmp_height)

    @property
    def width(self):
        """Width of the bitmap. (read only)"""
        return self._bmp_width

    @property
    def height(self):
        """Height of the bitmap. (read only)"""
        return self._bmp_height
