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
`displayio.ondiskbitmap`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from PIL import Image

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

# pylint: disable=unnecessary-pass, unused-argument


class OnDiskBitmap:
    """
    Loads values straight from disk. This minimizes memory use but can lead to much slower
    pixel load times. These load times may result in frame tearing where only part of the
    image is visible."""

    def __init__(self, file):
        self._image = Image.open(file).convert("RGBA")

    @property
    def width(self):
        """Width of the bitmap. (read only)"""
        return self._image.width

    @property
    def height(self):
        """Height of the bitmap. (read only)"""
        return self._image.height

    def __getitem__(self, index):
        """
        Returns the value at the given index. The index can either be
        an x,y tuple or an int equal to `y * width + x`.
        """
        if isinstance(index, (tuple, list)):
            x = index[0]
            y = index[1]
        elif isinstance(index, int):
            x = index % self._image._width
            y = index // self._image._width
        if not 0 <= x < self._image.width or not 0 <= y < self._image.height:
            return 0

        return self._image.getpixel((x, y))
