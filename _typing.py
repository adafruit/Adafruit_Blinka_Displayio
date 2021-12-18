# SPDX-FileCopyrightText: 2021 Melissa LeBlanc-Williams
#
# SPDX-License-Identifier: MIT

"""
`_typing`
================================================================================

Type aliases for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from typing import Union

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_Displayio.git"


WriteableBuffer = Union[
    bytearray,
    memoryview,
    # array.array,
    # ulab.numpy.ndarray,
    # rgbmatrix.RGBMatrix
]

ReadableBuffer = Union[
    bytes,
    WriteableBuffer,
]
