# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`vectorio.circle`
================================================================================

vectorio Circle for Blinka

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


class Circle(_VectorShape):
    """Vectorio Circle"""

    def __init__(
        self,
        *,
        pixel_shader: Union[ColorConverter, Palette],
        radius: int,
        x: int = 0,
        y: int = 0,
    ):
        """Circle is positioned on screen by its center point.

        :param Union[~displayio.ColorConverter,~displayio.Palette] pixel_shader:
            The pixel shader that produces colors from values
        :param int radius: The radius of the circle in pixels
        :param int x: Initial x position of the axis.
        :param int y: Initial y position of the axis.
        :param int color_index: Initial color_index to use when selecting color from the palette.
        """
        self._radius = 1
        self._color_index = 1
        super().__init__(pixel_shader, x, y)
        self.radius = radius

    @property
    def radius(self) -> int:
        """The radius of the circle in pixels"""
        return self._radius

    @radius.setter
    def radius(self, value: int) -> None:
        if value < 1:
            raise ValueError("radius must be >= 1")
        self._radius = int(value)  # other code assumes radius is an integer
        self._shape_set_dirty()

    @property
    def color_index(self) -> int:
        """The color_index of the circle as 0 based index of the palette."""
        return self._color_index - 1

    @color_index.setter
    def color_index(self, value: int) -> None:
        self._color_index = abs(value + 1)
        self._shape_set_dirty()

    def _get_pixel(self, x: int, y: int) -> int:
        x = abs(x)
        y = abs(y)
        if x + y <= self._radius:
            return self._color_index
        if x > self._radius or y > self._radius:
            return 0
        pythagoras_smaller_than_radius = x * x + y * y <= self._radius * self._radius
        return self._color_index if pythagoras_smaller_than_radius else 0

    def _get_area(self, out_area: Area) -> None:
        out_area.x1 = -1 * self._radius - 1
        out_area.y1 = -1 * self._radius - 1
        out_area.x2 = self._radius + 1
        out_area.y2 = self._radius + 1
