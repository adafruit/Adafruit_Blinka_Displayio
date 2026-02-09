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
import struct
from array import array
from typing import Union, Tuple
from circuitpython_typing import WriteableBuffer
from ._area import Area

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


def stride(width: int, bits_per_pixel: int) -> int:
    """Return the number of bytes per row of a bitmap with the given width and bits per pixel."""
    row_width = width * bits_per_pixel
    return (row_width + (31)) // 32


class Bitmap:
    """Stores values of a certain size in a 2D array

    Bitmaps can be treated as read-only buffers. If the number of bits in a pixel is 8, 16,
    or 32; and the number of bytes per row is a multiple of 4, then the resulting memoryview
    will correspond directly with the bitmap's contents. Otherwise, the bitmap data is packed
    into the memoryview with unspecified padding.

    A Bitmap can be treated as a buffer, allowing its content to be
    viewed and modified using e.g., with ``ulab.numpy.frombuffer``,
    but the `displayio.Bitmap.dirty` method must be used to inform
    displayio when a bitmap was modified through the buffer interface.

    `bitmaptools.arrayblit` can also be useful to move data efficiently
    into a Bitmap."""

    def __init__(self, width: int, height: int, value_count: int):
        """Create a Bitmap object with the given fixed size. Each pixel stores a value that is
        used to index into a corresponding palette. This enables differently colored sprites to
        share the underlying Bitmap. value_count is used to minimize the memory used to store
        the Bitmap.
        """

        if not 1 <= value_count <= 65536:
            raise ValueError("value_count must be in the range of 1-65536")

        bits = 1
        while (value_count - 1) >> bits:
            if bits < 8:
                bits = bits << 1
            else:
                bits += 8

        self._from_buffer(width, height, bits, None, False)

    def _from_buffer(
        self,
        width: int,
        height: int,
        bits_per_value: int,
        data: WriteableBuffer,
        read_only: bool,
    ) -> None:
        # pylint: disable=too-many-arguments
        self._bmp_width = width
        self._bmp_height = height
        self._stride = stride(width, bits_per_value)
        self._data_alloc = False

        if data is None or len(data) == 0:
            data = array("L", [0] * self._stride * height)
            self._data_alloc = True
        self._data = data
        self._read_only = read_only
        self._bits_per_value = bits_per_value

        if (
            self._bits_per_value > 8
            and self._bits_per_value != 16
            and self._bits_per_value != 32
        ):
            raise NotImplementedError("Invalid bits per value")

        # Division and modulus can be slow because it has to handle any integer. We know
        # bits_per_value is a power of two. We divide and mod by bits_per_value to compute
        # the offset into the byte array. So, we can the offset computation to simplify to
        # a shift for division and mask for mod.

        # Used to divide the index by the number of pixels per word. It's
        # used in a shift which effectively divides by 2 ** x_shift.
        self._x_shift = 0

        power_of_two = 1
        while power_of_two < 32 // bits_per_value:
            self._x_shift += 1
            power_of_two = power_of_two << 1

        self._x_mask = (1 << self._x_shift) - 1  # Used as a modulus on the x value
        self._bitmask = (1 << bits_per_value) - 1
        self._dirty_area = Area(0, 0, width, height)

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

        if x > self._bmp_width or x < 0 or y > self._bmp_height or y < 0:
            raise ValueError(f"Index {index} is out of range")
        return self._get_pixel(x, y)

    def _get_pixel(self, x: int, y: int) -> int:
        if x >= self._bmp_width or x < 0 or y >= self._bmp_height or y < 0:
            return 0
        row_start = y * self._stride
        bytes_per_value = self._bits_per_value // 8
        if bytes_per_value < 1:
            word = self._data[row_start + (x >> self._x_shift)]
            return (
                word >> (32 - ((x & self._x_mask) + 1) * self._bits_per_value)
            ) & self._bitmask
        row = memoryview(self._data)[row_start : row_start + self._stride]
        if bytes_per_value == 1:
            return struct.unpack_from("<B", row, x)[0]
        if bytes_per_value == 2:
            return struct.unpack_from("<H", row, x * 2)[0]
        if bytes_per_value == 4:
            return struct.unpack_from("<I", row, x * 4)[0]
        return 0

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
        # update the dirty region
        self._set_dirty_area(Area(x, y, x + 1, y + 1))
        self._write_pixel(x, y, value)

    def _write_pixel(self, x: int, y: int, value: int) -> None:
        if self._read_only:
            raise RuntimeError("Read-only")

        # Writes the color index value into a pixel position
        # Must update the dirty area separately

        # Don't write if out of area
        if x < 0 or x >= self._bmp_width or y < 0 or y >= self._bmp_height:
            return

        # Update one pixel of data
        row_start = y * self._stride
        bytes_per_value = self._bits_per_value // 8
        if bytes_per_value < 1:
            bit_position = 32 - ((x & self._x_mask) + 1) * self._bits_per_value
            index = row_start + (x >> self._x_shift)
            word = self._data[index]
            word &= ~(self._bitmask << bit_position)
            word |= (value & self._bitmask) << bit_position
            self._data[index] = word
        else:
            row = memoryview(self._data)[row_start : row_start + self._stride]
            if bytes_per_value == 1:
                struct.pack_into("<B", row, x, value)
            elif bytes_per_value == 2:
                struct.pack_into("<H", row, x * 2, value)
            elif bytes_per_value == 4:
                struct.pack_into("<I", row, x * 4, value)

    def fill(self, value: int) -> None:
        """Fills the bitmap with the supplied palette index value."""
        if self._read_only:
            raise RuntimeError("Read-only")
        self._set_dirty_area(Area(0, 0, self._bmp_width, self._bmp_height))

        # build the packed word
        word = 0
        for i in range(32 // self._bits_per_value):
            word |= (value & self._bitmask) << (32 - ((i + 1) * self._bits_per_value))

        # copy it in
        for i in range(self._stride * self._bmp_height):
            self._data[i] = word

    def dirty(self, x1: int = 0, y1: int = 0, x2: int = -1, y2: int = -1) -> None:
        """Inform displayio of bitmap updates done via the buffer protocol."""
        # pylint: disable=invalid-name
        if x2 == -1:
            x2 = self._bmp_width
        if y2 == -1:
            y2 = self._bmp_height
        self._set_dirty_area(Area(x1, y1, x2, y2))

    def _set_dirty_area(self, dirty_area: Area) -> None:
        if self._read_only:
            raise RuntimeError("Read-only")

        area = dirty_area
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
