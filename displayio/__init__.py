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
import threading
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
from ._displaybus import _DisplayBus
from ._constants import CIRCUITPY_DISPLAY_LIMIT

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


displays = []
display_buses = []


def _background():
    """Main thread function to loop through all displays and update them"""
    while True:
        for display in displays:
            display._background()  # pylint: disable=protected-access


def release_displays() -> None:
    """Releases any actively used displays so their busses and pins can be used again.

    Use this once in your code.py if you initialize a display. Place it right before the
    initialization so the display is active as long as possible.
    """
    for display in displays:
        display._release()  # pylint: disable=protected-access
    displays.clear()

    for display_bus in display_buses:
        display_bus.deinit()
    display_buses.clear()


def allocate_display(new_display: Union[Display, EPaperDisplay]) -> None:
    """Add a display to the displays pool and return the new display"""
    if len(displays) >= CIRCUITPY_DISPLAY_LIMIT:
        raise RuntimeError("Too many displays")
    displays.append(new_display)


def allocate_display_bus(new_display_bus: _DisplayBus) -> None:
    """Add a display bus to the display_buses pool and return the new display bus"""
    if len(display_buses) >= CIRCUITPY_DISPLAY_LIMIT:
        raise RuntimeError(
            "Too many display busses; forgot displayio.release_displays() ?"
        )
    display_buses.append(new_display_bus)


background_thread = threading.Thread(target=_background, daemon=True)


# Start the background thread
def _start_background():
    if not background_thread.is_alive():
        background_thread.start()


def _stop_background():
    if background_thread.is_alive():
        # Stop the thread
        background_thread.join()


_start_background()
