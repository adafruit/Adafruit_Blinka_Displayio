# SPDX-FileCopyrightText: 2021 Melissa LeBlanc-Williams
#
# SPDX-License-Identifier: MIT

"""
`displayio._displaybus`
================================================================================

Type aliases for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from typing import Union
import paralleldisplay
from ._fourwire import FourWire
from ._i2cdisplay import I2CDisplay

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_Displayio.git"

_DisplayBus = Union[FourWire, I2CDisplay, paralleldisplay.ParallelBus]
