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

import fontio

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

FONT = fontio.BuiltinFont()

# TODO: Tap into stdout to get the REPL
# Look at how Adafruit_Python_Shell's run_command works as an option
# Additionally, adding supervisor to Blinka may be helpful to keep track of REPL output
# sys.stdout = open('out.dat', 'w')
# sys.stdout.close()
