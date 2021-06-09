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

* Author(s): Melissa LeBlanc-Williams, Erik Tollerud

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

    def reset(self):
        """Performs a hardware reset via the reset pin if one is present.
        """
        if self._reset is not None:
            self._reset.value = False
            time.sleep(0.001)
            self._reset.value = True
            time.sleep(0.001)


    def send(self, is_command, data, *, toggle_every_byte=False):
        """Sends the given command value followed by the full set of data. Display state,
        such as vertical scroll, set via ``send`` may or may not be reset once the code is
        done.
        """
        control_byte = 0b10000000 if is_command else 0b11000000

        buffer = []
        for d in data:
            buffer.append(control_byte)
            buffer.append(d)

        self._i2c.writeto(self._dev_addr, bytes(buffer))

    def begin_transaction(self):
        while not self._i2c.try_lock():
            pass

    def end_transaction(self):
        self._i2c.unlock()
