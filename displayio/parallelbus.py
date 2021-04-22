# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.parallelbus`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class ParallelBus:
    """Manage updating a display over 8-bit parallel bus in the background while Python code
    runs. This protocol may be refered to as 8080-I Series Parallel Interface in datasheets.
    It doesn’t handle display initialization.
    """

    def __init__(self, i2c_bus, *, device_address, reset=None):
        # pylint: disable=unnecessary-pass
        """Create a ParallelBus object associated with the given pins. The
        bus is inferred from data0 by implying the next 7 additional pins on a given GPIO
        port.

        The parallel bus and pins are then in use by the display until
        displayio.release_displays() is called even after a reload. (It does this so
        CircuitPython can use the display after your code is done.) So, the first time you
        initialize a display bus in code.py you should call
        :py:func`displayio.release_displays` first, otherwise it will error after the first
        code.py run.
        """
        pass

    def reset(self):
        """Performs a hardware reset via the reset pin. Raises an exception if called when
        no reset pin is available.
        """
        raise NotImplementedError("ParallelBus reset has not been implemented yet")

    def send(self, command, data):
        """Sends the given command value followed by the full set of data. Display state,
        such as vertical scroll, set via ``send`` may or may not be reset once the code is
        done.
        """
        raise NotImplementedError("ParallelBus send has not been implemented yet")
