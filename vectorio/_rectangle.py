# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`vectorio.rectangle`
================================================================================

vectorio Rectangle for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from typing import Union
from displayio._colorconverter import ColorConverter
from displayio._palette import Palette
from displayio._area import Area
from ._vectorshape import _VectorShape

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class Rectangle(_VectorShape):
    """Vectorio Rectangle"""

    def __init__(
        self,
        *,
        pixel_shader: Union[ColorConverter, Palette],
        width: int,
        height: int,
        x: int,
        y: int,
        color_index: int = 0,
    ):
        """Represents a rectangle by defining its bounds

        :param Union[~displayio.ColorConverter,~displayio.Palette] pixel_shader:
            The pixel shader that produces colors from values
        :param int width: The number of pixels wide
        :param int height: The number of pixels high
        :param int x: Initial x position of the top left corner.
        :param int y: Initial y position of the top left corner.
        :param int color_index: Initial color_index to use when selecting color from the palette.
        """
        self._width = 1
        self._height = 1
        self._color_index = color_index + 1

        super().__init__(pixel_shader, x, y)
        self.width = width
        self.height = height

    @property
    def width(self) -> int:
        """The width of the rectangle in pixels"""
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        if value < 1:
            raise ValueError("width must be >= 1")

        self._width = abs(value)
        self._shape_set_dirty()

    @property
    def height(self) -> int:
        """The height of the rectangle in pixels"""
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        if value < 1:
            raise ValueError("height must be >= 1")
        self._height = abs(value)
        self._shape_set_dirty()

    @property
    def color_index(self) -> int:
        """The color_index of the rectangle as 0 based index of the palette."""
        return self._color_index - 1

    @color_index.setter
    def color_index(self, value: int) -> None:
        self._color_index = abs(value + 1)
        self._shape_set_dirty()

    def _get_pixel(self, x: int, y: int) -> int:
        if 0 <= x < self._width and 0 <= y < self._height:
            return self._color_index
        return 0

    def _get_area(self, out_area: Area) -> None:
        out_area.x1 = 0
        out_area.y1 = 0
        out_area.x2 = self._width
        out_area.y2 = self._height
