# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
# SPDX-FileCopyrightText: 2020 Erik Tollerud
# SPDX-FileCopyrightText: 2021 Jim Morris
# SPDX-FileCopyrightText: 2021 James Carr
#
# SPDX-License-Identifier: MIT

"""
`displayio.i2cdisplay`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams, Erik Tollerud, James Carr

"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

import time
import busio
import digitalio


class I2CDisplay:
    """Manage updating a display over I2C in the background while Python code runs.
    It doesn’t handle display initialization.
    """

    def __init__(self, i2c_bus: busio.I2C, *, device_address: int, reset=None):
        """Create a I2CDisplay object associated with the given I2C bus and reset pin.

        The I2C bus and pins are then in use by the display until displayio.release_displays() is
        called even after a reload. (It does this so CircuitPython can use the display after your
        code is done.) So, the first time you initialize a display bus in code.py you should call
        :py:func`displayio.release_displays` first, otherwise it will error after the first
        code.py run.
        """

        if reset is not None:
            self._reset = digitalio.DigitalInOut(reset)
            self._reset.switch_to_output(value=True)
        else:
            self._reset = None
        self._i2c = i2c_bus
        self._dev_addr = device_address

    def _release(self):
        self.reset()
        self._i2c.deinit()
        if self._reset is not None:
            self._reset.deinit()

    def reset(self) -> None:
        """
        Performs a hardware reset via the reset pin if one is present.
        """

        if self._reset is None:
            return

        self._reset.value = False
        time.sleep(0.0001)
        self._reset.value = True

    def begin_transaction(self) -> None:
        """
        Lock the bus before sending data.
        """
        while not self._i2c.try_lock():
            pass

    def send(self, command: bool, data, *, toggle_every_byte=False) -> None:
        # pylint: disable=unused-argument
        """
        Sends the given command value followed by the full set of data. Display state,
        such as vertical scroll, set via ``send`` may or may not be reset once the code is
        done.
        """
        # NOTE: we have to have a toggle_every_byte parameter, which we ignore,
        # because Display._write() sets it regardless of bus type.

        if command:
            n = len(data)
            if n > 0:
                command_bytes = bytearray(n * 2)
                for i in range(n):
                    command_bytes[2 * i] = 0x80
                    command_bytes[2 * i + 1] = data[i]

                self._i2c.writeto(self._dev_addr, buffer=command_bytes, stop=True)

        else:
            data_bytes = bytearray(len(data) + 1)
            data_bytes[0] = 0x40
            data_bytes[1:] = data
            self._i2c.writeto(self._dev_addr, buffer=data_bytes, stop=True)

    def end_transaction(self) -> None:
        """
        Release the bus after sending data.
        """
        self._i2c.unlock()
