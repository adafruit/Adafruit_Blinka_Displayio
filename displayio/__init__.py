# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from displayio.bitmap import Bitmap
from displayio.colorconverter import ColorConverter
from displayio.display import Display
from displayio.epaperdisplay import EPaperDisplay
from displayio.fourwire import FourWire
from displayio.group import Group
from displayio.i2cdisplay import I2CDisplay
from displayio.ondiskbitmap import OnDiskBitmap
from displayio.palette import Palette
from displayio.parallelbus import ParallelBus
from displayio.shape import Shape
from displayio.tilegrid import TileGrid
from displayio.display import displays

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


def release_displays():
    """Releases any actively used displays so their busses and pins can be used again.

    Use this once in your code.py if you initialize a display. Place it right before the
    initialization so the display is active as long as possible.
    """
    for _disp in displays:
        _disp._release()  # pylint: disable=protected-access
    displays.clear()
