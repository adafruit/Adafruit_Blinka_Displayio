# The MIT License (MIT)
#
# Copyright (c) 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
`displayio.epaperdisplay`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""


__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

# pylint: disable=unnecessary-pass, unused-argument


class EPaperDisplay:
    """Manage updating an epaper display over a display bus

    This initializes an epaper display and connects it into CircuitPython. Unlike other
    objects in CircuitPython, EPaperDisplay objects live until
    displayio.release_displays() is called. This is done so that CircuitPython can use
    the display itself.

    Most people should not use this class directly. Use a specific display driver instead
    that will contain the startup and shutdown sequences at minimum.
    """

    # pylint: disable=too-many-locals
    def __init__(
        self,
        display_bus,
        start_sequence,
        stop_sequence,
        *,
        width,
        height,
        ram_width,
        ram_height,
        colstart=0,
        rowstart=0,
        rotation=0,
        set_column_window_command=None,
        set_row_window_command=None,
        single_byte_bounds=False,
        write_black_ram_command,
        black_bits_inverted=False,
        write_color_ram_command=None,
        color_bits_inverted=False,
        highlight_color=0x000000,
        refresh_display_command,
        refresh_time=40,
        busy_pin=None,
        busy_state=True,
        seconds_per_frame=180,
        always_toggle_chip_select=False
    ):
        """
        Create a EPaperDisplay object on the given display bus (displayio.FourWire or
        displayio.ParallelBus).

        The start_sequence and stop_sequence are bitpacked to minimize the ram impact. Every
        command begins with a command byte followed by a byte to determine the parameter
        count and if a delay is need after. When the top bit of the second byte is 1, the
        next byte will be the delay time in milliseconds. The remaining 7 bits are the
        parameter count excluding any delay byte. The third through final bytes are the
        remaining command parameters. The next byte will begin a new command definition.
        """
        pass

    # pylint: enable=too-many-locals

    def show(self, group):
        """Switches to displaying the given group of layers. When group is None, the default
        CircuitPython terminal will be shown (eventually).
        """
        pass

    def refresh(self):
        """Refreshes the display immediately or raises an exception if too soon. Use
        ``time.sleep(display.time_to_refresh)`` to sleep until a refresh can occur.
        """
        pass

    @property
    def time_to_refresh(self):
        """Time, in fractional seconds, until the ePaper display can be refreshed."""
        return 0

    @property
    def width(self):
        """Display Width"""
        pass

    @property
    def height(self):
        """Display Height"""
        pass

    @property
    def bus(self):
        """Current Display Bus"""
        pass
