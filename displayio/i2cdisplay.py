# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.i2cdisplay`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class I2CDisplay:
    """Manage updating a display over I2C in the background while Python code runs.
    It doesn’t handle display initialization.
    """

    def __init__(self, i2c_bus, *, device_address, reset=None):
        # pylint: disable=unnecessary-pass
        """Create a I2CDisplay object associated with the given I2C bus and reset pin.

        The I2C bus and pins are then in use by the display until displayio.release_displays() is
        called even after a reload. (It does this so CircuitPython can use the display after your
        code is done.) So, the first time you initialize a display bus in code.py you should call
        :py:func`displayio.release_displays` first, otherwise it will error after the first
        code.py run.
        """
        pass

    def reset(self):
        """Performs a hardware reset via the reset pin. Raises an exception if called
        when no reset pin is available.
        """
        raise NotImplementedError("I2CDisplay reset has not been implemented yet")

    def send(self, command, data):
        """Sends the given command value followed by the full set of data. Display state,
        such as vertical scroll, set via send may or may not be reset once the code is
        done.
        """
        raise NotImplementedError("I2CDisplay send has not been implemented yet")
