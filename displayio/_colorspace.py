# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT


"""
`displayio.colorspace`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class Colorspace:
    """The colorspace for a ColorConverter to operate in."""

    # pylint: disable=too-few-public-methods
    def __init__(self, colorspace_type):
        self._colorspace_type = colorspace_type


Colorspace.RGB888 = Colorspace("RGB888")
Colorspace.RGB565 = Colorspace("RGB565")
Colorspace.RGB565_SWAPPED = Colorspace("RGB565_SWAPPED")
Colorspace.RGB555 = Colorspace("RGB555")
Colorspace.RGB555_SWAPPED = Colorspace("RGB555_SWAPPED")
Colorspace.BGR565 = Colorspace("BGR565")
Colorspace.BGR565_SWAPPED = Colorspace("BGR565_SWAPPED")
Colorspace.BGR555 = Colorspace("BGR555")
Colorspace.BGR555_SWAPPED = Colorspace("BGR555_SWAPPED")
Colorspace.L8 = Colorspace("L8")
