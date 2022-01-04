# SPDX-FileCopyrightText: 2021 Melissa LeBlanc-Williams for Adafruit Industries
# SPDX-FileCopyrightText: 2021 James Carr
#
# SPDX-License-Identifier: MIT

"""
`displayio._area`
================================================================================

Area for Blinka Displayio

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): James Carr, Melissa LeBlanc-Williams

"""

from __future__ import annotations

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_Displayio.git"


class Area:
    # pylint: disable=invalid-name,missing-function-docstring
    """Area Class to represent an area to be updated. Currently not used."""

    def __init__(self, x1: int = 0, y1: int = 0, x2: int = 0, y2: int = 0):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.next = None

    def __str__(self):
        return f"Area TL({self.x1},{self.y1}) BR({self.x2},{self.y2})"

    def _copy_into(self, dst) -> None:
        dst.x1 = self.x1
        dst.y1 = self.y1
        dst.x2 = self.x2
        dst.y2 = self.y2

    def _scale(self, scale: int) -> None:
        self.x1 *= scale
        self.y1 *= scale
        self.x2 *= scale
        self.y2 *= scale

    def _shift(self, dx: int, dy: int) -> None:
        self.x1 += dx
        self.y1 += dy
        self.x2 += dx
        self.y2 += dy

    def _compute_overlap(self, other, overlap) -> bool:
        a = self
        overlap.x1 = max(a.x1, other.x1)
        overlap.x2 = min(a.x2, other.x2)

        if overlap.x1 >= overlap.x2:
            return False

        overlap.y1 = max(a.y1, other.y1)
        overlap.y2 = min(a.y2, other.y2)

        return overlap.y1 < overlap.y2

    def _empty(self):
        return (self.x1 == self.x2) or (self.y1 == self.y2)

    def _canon(self):
        if self.x1 > self.x2:
            self.x1, self.x2 = self.x2, self.x1
        if self.y1 > self.y2:
            self.y1, self.y2 = self.y2, self.y1

    def _union(self, other, union):
        # pylint: disable=protected-access
        if self._empty():
            self._copy_into(union)
            return
        if other._empty():
            other._copy_into(union)
            return

        union.x1 = min(self.x1, other.x1)
        union.y1 = min(self.y1, other.y1)
        union.x2 = max(self.x2, other.x2)
        union.y2 = max(self.y2, other.y2)

    def width(self) -> int:
        return self.x2 - self.x1

    def height(self) -> int:
        return self.y2 - self.y1

    def size(self) -> int:
        return self.width() * self.height()

    def __eq__(self, other):
        if not isinstance(other, Area):
            return False

        return (
            self.x1 == other.x1
            and self.y1 == other.y1
            and self.x2 == other.x2
            and self.y2 == other.y2
        )

    @staticmethod
    def _transform_within(
        mirror_x: bool,
        mirror_y: bool,
        transpose_xy: bool,
        original: Area,
        whole: Area,
        transformed: Area,
    ):
        # pylint: disable=too-many-arguments
        # Original and whole must be in the same coordinate space.
        if mirror_x:
            transformed.x1 = whole.x1 + (whole.x2 - original.x2)
            transformed.x2 = whole.x2 - (original.x1 - whole.x1)
        else:
            transformed.x1 = original.x1
            transformed.x2 = original.x2

        if mirror_y:
            transformed.y1 = whole.y1 + (whole.y2 - original.y2)
            transformed.y2 = whole.y2 - (original.y1 - whole.y1)
        else:
            transformed.y1 = original.y1
            transformed.y2 = original.y2

        if transpose_xy:
            y1 = transformed.y1
            y2 = transformed.y2
            transformed.y1 = whole.y1 + (transformed.x1 - whole.x1)
            transformed.y2 = whole.y1 + (transformed.x2 - whole.x1)
            transformed.x1 = whole.x1 + (y1 - whole.y1)
            transformed.x2 = whole.x1 + (y2 - whole.y1)
