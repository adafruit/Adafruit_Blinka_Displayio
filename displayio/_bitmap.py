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

from __future__ import annotations
from typing import Union, Tuple
from PIL import Image
from ._structs import RectangleStruct
from ._area import Area

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class Bitmap:
    """Stores values of a certain size in a 2D array"""

    def __init__(self, width: int, height: int, value_count: int):
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
        self._dirty_area = RectangleStruct(0, 0, width, height)

    def __getitem__(self, index: Union[Tuple[int, int], int]) -> int:
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
            raise ValueError(f"Index {index} is out of range")
        return self._get_pixel(x, y)

    def _get_pixel(self, x: int, y: int) -> int:
        return self._image.getpixel((x, y))

    def __setitem__(self, index: Union[Tuple[int, int], int], value: int) -> None:
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

    def fill(self, value: int) -> None:
        """Fills the bitmap with the supplied palette index value."""
        self._image = Image.new("P", (self._bmp_width, self._bmp_height), value)
        self._dirty_area = RectangleStruct(0, 0, self._bmp_width, self._bmp_height)

    def blit(
        self,
        x: int,
        y: int,
        source_bitmap: Bitmap,
        *,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        skip_index: int,
    ) -> None:
        """Inserts the source_bitmap region defined by rectangular boundaries"""
        # pylint: disable=invalid-name
        if x2 is None:
            x2 = source_bitmap.width
        if y2 is None:
            y2 = source_bitmap.height

        # Rearrange so that x1 < x2 and y1 < y2
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        # Ensure that x2 and y2 are within source bitmap size
        x2 = min(x2, source_bitmap.width)
        y2 = min(y2, source_bitmap.height)

        for y_count in range(y2 - y1):
            for x_count in range(x2 - x1):
                x_placement = x + x_count
                y_placement = y + y_count

                if (self.width > x_placement >= 0) and (
                    self.height > y_placement >= 0
                ):  # ensure placement is within target bitmap
                    # get the palette index from the source bitmap
                    this_pixel_color = source_bitmap[
                        y1
                        + (
                            y_count * source_bitmap.width
                        )  # Direct index into a bitmap array is speedier than [x,y] tuple
                        + x1
                        + x_count
                    ]

                    if (skip_index is None) or (this_pixel_color != skip_index):
                        self[  # Direct index into a bitmap array is speedier than [x,y] tuple
                            y_placement * self.width + x_placement
                        ] = this_pixel_color
                elif y_placement > self.height:
                    break

    def dirty(self, x1: int = 0, y1: int = 0, x2: int = -1, y2: int = -1) -> None:
        """Inform displayio of bitmap updates done via the buffer protocol."""
        # pylint: disable=invalid-name
        if x2 == -1:
            x2 = self._bmp_width
        if y2 == -1:
            y2 = self._bmp_height
        area = Area(x1, y1, x2, y2)
        area.canon()
        area.union(self._dirty_area, area)
        bitmap_area = Area(0, 0, self._bmp_width, self._bmp_height)
        area.compute_overlap(bitmap_area, self._dirty_area)

    def _finish_refresh(self):
        if self._read_only:
            return
        self._dirty_area.x1 = 0
        self._dirty_area.x2 = 0

    def _get_refresh_areas(self, areas: list[Area]) -> None:
        if self._dirty_area.x1 == self._dirty_area.x2 or self._read_only:
            return
        areas.append(self._dirty_area)

    @property
    def width(self) -> int:
        """Width of the bitmap. (read only)"""
        return self._bmp_width

    @property
    def height(self) -> int:
        """Height of the bitmap. (read only)"""
        return self._bmp_height
