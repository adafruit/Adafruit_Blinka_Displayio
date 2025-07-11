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
import time
from typing import Union

from ._bitmap import Bitmap
from ._colorspace import Colorspace
from ._colorconverter import ColorConverter
from ._group import Group
from ._ondiskbitmap import OnDiskBitmap
from ._palette import Palette
from ._tilegrid import TileGrid
from ._constants import CIRCUITPY_DISPLAY_LIMIT


__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


displays = []
display_buses = []


def _background(stop_event):
    """Main thread function to loop through all displays and update them"""
    while not stop_event.is_set():
        for display in displays:
            display._background()  # pylint: disable=protected-access

        # relax system when _background does nothing
        # and we are in a while True loop consuming lots of CPU
        time.sleep(0.0)


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


def allocate_display(
    new_display: Union["busdisplay.BusDisplay", "epaperdisplay.EPaperDisplay"]
) -> None:
    """Add a display to the displays pool and return the new display"""
    if len(displays) >= CIRCUITPY_DISPLAY_LIMIT:
        raise RuntimeError("Too many displays")
    displays.append(new_display)


def allocate_display_bus(new_display_bus: "busdisplay._displaybus._DisplayBus") -> None:
    """Add a display bus to the display_buses pool and return the new display bus"""
    if len(display_buses) >= CIRCUITPY_DISPLAY_LIMIT:
        raise RuntimeError(
            "Too many display busses; forgot displayio.release_displays() ?"
        )
    display_buses.append(new_display_bus)


background_thread_stop_event = threading.Event()
background_thread = threading.Thread(
    target=_background, args=(background_thread_stop_event,), daemon=True
)


# Start the background thread
def _start_background():
    if not background_thread.is_alive():
        background_thread.start()


def _stop_background():
    if background_thread.is_alive():
        background_thread_stop_event.set()
        # Stop the thread
        background_thread.join()


_start_background()
