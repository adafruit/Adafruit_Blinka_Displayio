# SPDX-FileCopyrightText: 2021 Melissa LeBlanc-Williams
#
# SPDX-License-Identifier: MIT

"""
`busdisplay._displaybus`
================================================================================

DisplayBus Type aliases for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from typing import Union
import paralleldisplaybus
import fourwire
import i2cdisplaybus

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_Displayio.git"

_DisplayBus = Union[
    fourwire.FourWire, i2cdisplaybus.I2CDisplayBus, paralleldisplaybus.ParallelBus
]
