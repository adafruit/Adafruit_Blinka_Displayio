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

from typing import Union
from ._fourwire import FourWire
from ._i2cdisplay import I2CDisplay
from ._bitmap import Bitmap
from ._colorspace import Colorspace
from ._colorconverter import ColorConverter
from ._display import Display
from ._epaperdisplay import EPaperDisplay
from ._group import Group
from ._ondiskbitmap import OnDiskBitmap
from ._palette import Palette
from ._shape import Shape
from ._tilegrid import TileGrid
from ._display import displays
from ._displaybus import _DisplayBus

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


def release_displays() -> None:
    """Releases any actively used displays so their busses and pins can be used again.

    Use this once in your code.py if you initialize a display. Place it right before the
    initialization so the display is active as long as possible.
    """
    for _disp in displays:
        _disp._release()  # pylint: disable=protected-access
    displays.clear()
