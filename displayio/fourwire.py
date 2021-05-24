# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.fourwire`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

import time
import digitalio

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class FourWire:
    """Manage updating a display over SPI four wire protocol in the background while
    Python code runs. It doesn’t handle display initialization.
    """

    def __init__(
        self,
        spi_bus,
        *,
        command,
        chip_select,
        reset=None,
        baudrate=24000000,
        polarity=0,
        phase=0
    ):
        """Create a FourWire object associated with the given pins.

        The SPI bus and pins are then in use by the display until
        displayio.release_displays() is called even after a reload. (It does this so
        CircuitPython can use the display after your code is done.)
        So, the first time you initialize a display bus in code.py you should call
        :py:func`displayio.release_displays` first, otherwise it will error after the
        first code.py run.
        """
        self._dc = digitalio.DigitalInOut(command)
        self._dc.switch_to_output(value=False)
        self._chip_select = digitalio.DigitalInOut(chip_select)
        self._chip_select.switch_to_output(value=True)
        self._frequency = baudrate
        self._polarity = polarity
        self._phase = phase

        if reset is not None:
            self._reset = digitalio.DigitalInOut(reset)
            self._reset.switch_to_output(value=True)
        else:
            self._reset = None
        self._spi = spi_bus

    def _release(self):
        self.reset()
        self._spi.deinit()
        self._dc.deinit()
        self._chip_select.deinit()
        if self._reset is not None:
            self._reset.deinit()

    def reset(self):
        """Performs a hardware reset via the reset pin.
        Raises an exception if called when no reset pin is available.
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
        self._dc.value = not is_command
        if toggle_every_byte:
            for byte in data:
                self._spi.write(bytes([byte]))
                self._chip_select.value = True
                time.sleep(0.000001)
                self._chip_select.value = False
        else:
            self._spi.write(data)

    def begin_transaction(self):
        """Begin the SPI transaction by locking, configuring, and setting Chip Select"""
        while not self._spi.try_lock():
            pass
        self._spi.configure(
            baudrate=self._frequency, polarity=self._polarity, phase=self._phase
        )
        self._chip_select.value = False

    def end_transaction(self):
        """End the SPI transaction by unlocking and setting Chip Select"""
        self._chip_select.value = True
        self._spi.unlock()
