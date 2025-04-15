# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`vectorio.polygon`
================================================================================

vectorio Polygon for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from typing import Union, Tuple, List
from displayio._colorconverter import ColorConverter
from displayio._palette import Palette
from displayio._area import Area
from ._vectorshape import _VectorShape

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class Polygon(_VectorShape):
    """Vectorio Polygon"""

    def __init__(
        self,
        *,
        pixel_shader: Union[ColorConverter, Palette],
        points: List[Tuple[int, int]],
        x: int,
        y: int,
    ):
        """Represents a closed shape by ordered vertices. The path will be treated as
        'closed', the last point will connect to the first point.

        :param Union[~displayio.ColorConverter,~displayio.Palette] pixel_shader: The pixel
            shader that produces colors from values
        :param List[Tuple[int,int]] points: Vertices for the polygon
        :param int x: Initial screen x position of the 0,0 origin in the points list.
        :param int y: Initial screen y position of the 0,0 origin in the points list.
        :param int color_index: Initial color_index to use when selecting color from the palette.
        """
        self._color_index = 1
        self._points = []
        super().__init__(pixel_shader, x, y)
        self.points = points

    @property
    def points(self) -> List[Tuple[int, int]]:
        """The points of the polygon in pixels"""
        return self._points

    @points.setter
    def points(self, value: List[Tuple[int, int]]) -> None:
        if len(value) < 3:
            raise ValueError("Polygon needs at least 3 points")
        self._points = value
        self._shape_set_dirty()

    @property
    def color_index(self) -> int:
        """The color_index of the polygon as 0 based index of the palette."""
        return self._color_index - 1

    @color_index.setter
    def color_index(self, value: int) -> None:
        self._color_index = abs(value + 1)
        self._shape_set_dirty()

    @staticmethod
    def _line_side(
        line_x1: int,
        line_y1: int,
        line_x2: int,
        line_y2: int,
        point_x: int,
        point_y: int,
    ):
        # pylint: disable=too-many-arguments
        return (point_x - line_x1) * (line_y2 - line_y1) - (point_y - line_y1) * (
            line_x2 - line_x1
        )

    def _get_pixel(self, x: int, y: int) -> int:
        # pylint: disable=invalid-name
        if len(self._points) == 0:
            return 0
        winding_number = 0
        x1 = self._points[0][0]
        y1 = self._points[0][1]
        for i in range(1, len(self._points)):
            x2 = self._points[i][0]
            y2 = self._points[i][1]
            if y1 <= y:
                if y2 > y and self._line_side(x1, y1, x2, y2, x, y) < 0:
                    # Wind up, point is to the left of the edge vector
                    winding_number += 1
            elif y2 <= y and self._line_side(x1, y1, x2, y2, x, y) > 0:
                # Wind down, point is to the right of the edge vector
                winding_number -= 1
            x1 = x2
            y1 = y2

        return 0 if winding_number == 0 else self._color_index

    def _get_area(self, out_area: Area) -> None:
        # Figure out the shape dimensions by using min and max
        out_area.x1 = 32768
        out_area.y1 = 32768
        out_area.x2 = 0
        out_area.y2 = 0

        for x, y in self._points:
            if x < out_area.x1:
                out_area.x1 = x
            if y < out_area.y1:
                out_area.y1 = y
            if x > out_area.x2:
                out_area.x2 = x
            if y > out_area.y2:
                out_area.y2 = y
