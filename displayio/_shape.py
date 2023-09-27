# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT


"""
`displayio.shape`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from ._bitmap import Bitmap
from ._area import Area
from ._helpers import clamp

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class Shape(Bitmap):
    """Create a Shape object with the given fixed size. Each pixel is one bit and is stored
    by the column boundaries of the shape on each row. Each row’s boundary defaults to the
    full row.
    """

    def __init__(
        self, width: int, height: int, *, mirror_x: bool = False, mirror_y: bool = False
    ):
        """Create a Shape object with the given fixed size. Each pixel is one bit and is
        stored by the column boundaries of the shape on each row. Each row’s boundary
        defaults to the full row.
        """
        self._mirror_x = mirror_x
        self._mirror_y = mirror_y
        self._width = width
        self._height = height
        if self._mirror_x:
            width //= 2
            width += self._width % 2
        self._half_width = width
        if self._mirror_y:
            height //= 2
            height += self._height % 2
        self._half_height = height
        self._data = bytearray(height * 4)
        for i in range(height):
            self._data[2 * i] = 0
            self._data[2 * i + 1] = width

        self._dirty_area = Area(0, 0, width, height)
        super().__init__(width, height, 2)

    def set_boundary(self, y: int, start_x: int, end_x: int) -> None:
        """Loads pre-packed data into the given row."""
        max_y = self._height - 1
        if self._mirror_y:
            max_y = self._half_height - 1
        y = clamp(y, 0, max_y)
        max_x = self._width - 1
        if self._mirror_x:
            max_x = self._half_width - 1
        start_x = clamp(start_x, 0, max_x)
        end_x = clamp(end_x, 0, max_x)

        # find x-boundaries for updating based on current data and start_x, end_x, and mirror_x
        lower_x = min(start_x, self._data[2 * y])

        if self._mirror_x:
            upper_x = (
                self._width - lower_x + 1
            )  # dirty rectangles are treated with max value exclusive
        else:
            upper_x = max(
                end_x, self._data[2 * y + 1]
            )  # dirty rectangles are treated with max value exclusive

        # find y-boundaries based on y and mirror_y
        lower_y = y

        if self._mirror_y:
            upper_y = (
                self._height - lower_y + 1
            )  # dirty rectangles are treated with max value exclusive
        else:
            upper_y = y + 1  # dirty rectangles are treated with max value exclusive

        self._data[2 * y] = start_x  # update the data array with the new boundaries
        self._data[2 * y + 1] = end_x

        if self._dirty_area.x1 == self._dirty_area.x2:  # dirty region is empty
            self._dirty_area.x1 = lower_x
            self._dirty_area.x2 = upper_x
            self._dirty_area.y1 = lower_y
            self._dirty_area.y2 = upper_y
        else:
            self._dirty_area.x1 = min(lower_x, self._dirty_area.x1)
            self._dirty_area.x2 = max(upper_x, self._dirty_area.x2)
            self._dirty_area.y1 = min(lower_y, self._dirty_area.y1)
            self._dirty_area.y2 = max(upper_y, self._dirty_area.y2)

    def _get_pixel(self, x: int, y: int) -> int:
        if x >= self._width or x < 0 or y >= self._height or y < 0:
            return 0
        if self._mirror_x and x >= self._half_width:
            x = self._width - x - 1
        if self._mirror_y and y >= self._half_height:
            y = self._height - y - 1
        start_x = self._data[2 * y]
        end_x = self._data[2 * y + 1]
        if x < start_x or x >= end_x:
            return 0
        return 1

    def _finish_refresh(self):
        self._dirty_area.x1 = 0
        self._dirty_area.x2 = 0

    def _get_refresh_areas(self, areas: list[Area]) -> None:
        if self._dirty_area.x1 != self._dirty_area.x2:
            areas.append(self._dirty_area)
