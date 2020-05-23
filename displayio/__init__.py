# The MIT License (MIT)
#
# Copyright (c) 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

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
