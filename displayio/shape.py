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

from displayio.bitmap import Bitmap

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class Shape(Bitmap):
    """Create a Shape object with the given fixed size. Each pixel is one bit and is stored
    by the column boundaries of the shape on each row. Each row’s boundary defaults to the
    full row.
    """

    def __init__(self, width, height, *, mirror_x=False, mirror_y=False):
        # pylint: disable=unused-argument
        """Create a Shape object with the given fixed size. Each pixel is one bit and is
        stored by the column boundaries of the shape on each row. Each row’s boundary
        defaults to the full row.
        """
        super().__init__(width, height, 2)

    def set_boundary(self, y, start_x, end_x):
        # pylint: disable=unnecessary-pass
        """Loads pre-packed data into the given row."""
        pass
