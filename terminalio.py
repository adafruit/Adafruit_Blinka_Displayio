# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`terminalio`
================================================================================

terminalio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

import sys  # pylint: disable=unused-import
import fontio

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

FONT = fontio.BuiltinFont()

# TODO: Tap into stdout to get the REPL
# sys.stdout = open('out.dat', 'w')
# sys.stdout.close()
