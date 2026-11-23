# SPDX-FileCopyrightText: 2026 Bert Outtier
#
# SPDX-License-Identifier: MIT

"""
`linuxframebuffer`
================================================================================

A Linux framebuffer device (``/dev/fb0``, ...) as a framebuffer for
`framebufferio.FramebufferDisplay`, for displays that Linux drives itself:
HDMI, DSI and parallel RGB panels, and the framebuffer drivers of SPI panels.

.. code-block:: python

    import displayio
    import framebufferio
    import linuxframebuffer

    displayio.release_displays()
    framebuffer = linuxframebuffer.LinuxFramebuffer("/dev/fb0")
    display = framebufferio.FramebufferDisplay(framebuffer)

displayio draws 16 bit (RGB565) pixels by default, which is more than twice
as fast as 32 bit pixels in Python. When the framebuffer device uses another
pixel format, for example 32 bit XRGB8888 as most DRM drivers do, displayio
draws into a copy in memory, and the rows it changed are converted into the
device at each refresh.

Writing to the framebuffer device needs access to it (``root``, or the
``video`` group on most distributions).

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Bert Outtier

"""

import atexit
import fcntl
import mmap
import os
import struct
import sys
import threading
import warnings
from array import array
from typing import Optional

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

# linux/fb.h
_FBIOGET_VSCREENINFO = 0x4600
_FBIOGET_FSCREENINFO = 0x4602
_FBIOBLANK = 0x4611
_FB_BLANK_UNBLANK = 0
_FB_TYPE_PACKED_PIXELS = 0
_FB_VISUAL_TRUECOLOR = 2
# struct fb_var_screeninfo: 40 __u32
_VAR_SCREENINFO = struct.Struct("=40I")
# struct fb_fix_screeninfo, with native unsigned longs and its end padding
_FIX_SCREENINFO = struct.Struct("@16sLIIIIHHHILIIH2H0L")

# linux/kd.h
_KDSETMODE = 0x4B3A
_KDGETMODE = 0x4B3B
_KD_TEXT = 0
_KD_GRAPHICS = 1

_BACKLIGHT_CLASS = "/sys/class/backlight"


def _channel(offset: int, length: int, bits: int) -> list:
    """Each value of a color channel of the given bits, rounded to the length of
    the device's field and shifted to its offset."""
    maximum = (1 << bits) - 1
    return [
        ((value * ((1 << length) - 1) + maximum // 2) // maximum) << offset
        for value in range(1 << bits)
    ]


def _rgb565_table(fields, typecode: str) -> array:
    """The pixel value of the device for each RGB565 value."""
    red = _channel(*fields[0], 5)
    green = _channel(*fields[1], 6)
    blue = _channel(*fields[2], 5)
    return array(typecode, (r | g | b for r in red for g in green for b in blue))


def _byte_channels(fields, alpha: int) -> Optional[tuple]:
    """How to convert RGB565 into a 32 bit device a byte at a time, when its red,
    green and blue fields are whole bytes: the byte of each of red, green and blue
    with its translation table, and the constant bytes of the other fields. None
    for other formats."""
    if sys.byteorder != "little" or any(
        length != 8 or offset % 8 for offset, length in fields
    ):
        return None
    used = [offset // 8 for offset, _ in fields]
    if len(set(used)) != 3 or any(alpha >> (byte * 8) & 0xFF for byte in used):
        return None
    red, green, blue = (_channel(0, 8, bits) for bits in (5, 6, 5))
    tables = (
        # Red is the top 5 bits of the high byte, blue the low 5 bits of the low
        # byte, green the index made by _convert_channels
        bytes(red[value >> 3] for value in range(256)),
        bytes(green) + bytes(256 - len(green)),
        bytes(blue[value & 0x1F] for value in range(256)),
    )
    constants = tuple(
        (byte, alpha >> (byte * 8) & 0xFF)
        for byte in range(4)
        if byte not in used and alpha >> (byte * 8) & 0xFF
    )
    return tuple(zip(used, tables)), constants


# Green has 3 bits in the low byte and 3 in the high byte of an RGB565 pixel
_GREEN_LOW = bytes(value >> 5 for value in range(256))
_GREEN_HIGH = bytes((value & 7) << 3 for value in range(256))


def _convert_channels(channels, source: memoryview) -> bytearray:
    """Convert RGB565 pixels (little endian bytes) into a 32 bit device a channel
    at a time, with bytes.translate on all the pixels at once"""
    (red, red_table), (green, green_table), (blue, blue_table) = channels[0]
    low = bytes(source[0::2])
    high = bytes(source[1::2])
    count = len(low)
    green_index = (
        int.from_bytes(low.translate(_GREEN_LOW), "little")
        | int.from_bytes(high.translate(_GREEN_HIGH), "little")
    ).to_bytes(count, "little")
    pixels = bytearray(count * 4)
    pixels[red::4] = high.translate(red_table)
    pixels[green::4] = green_index.translate(green_table)
    pixels[blue::4] = low.translate(blue_table)
    for byte, value in channels[1]:
        pixels[byte::4] = bytes((value,)) * count
    return pixels


class LinuxFramebuffer:
    # pylint: disable=too-many-instance-attributes
    """A Linux framebuffer device"""

    def __init__(
        self,
        device: str = "/dev/fb0",
        *,
        color_depth: int = 16,
        backlight: Optional[str] = None,
        console_graphics: bool = True,
    ) -> None:
        """Open a framebuffer device

        :param str device: The framebuffer device
        :param int color_depth: The color depth displayio draws with: 16 (RGB565, the
            fastest) or 32 (0x00RRGGBB, only for a device with 8 bit color fields)
        :param str backlight: The backlight of the display, a name in
            ``/sys/class/backlight``, for `framebufferio.FramebufferDisplay.brightness`.
            `None` takes the only backlight when there is exactly one.
        :param bool console_graphics: Switch the Linux text console to graphics mode while
            the framebuffer is in use, so that it does not draw over the display (needs
            access to ``/dev/tty0``)
        """
        if color_depth not in (16, 32):
            raise ValueError("color_depth must be 16 or 32")

        self._fd = os.open(device, os.O_RDWR)
        self._mmap = None
        self._console = None
        # Taken by _swapbuffers() and deinit(), which a refresh thread and the
        # main thread may call at the same time
        self._lock = threading.Lock()
        try:
            self._setup(color_depth)
            self._backlight = self._find_backlight(backlight)
        except:
            self.deinit()
            raise

        try:
            fcntl.ioctl(self._fd, _FBIOBLANK, _FB_BLANK_UNBLANK)
        except OSError:
            pass
        if console_graphics:
            self._console_graphics()
        atexit.register(self.deinit)

    def _setup(self, color_depth: int) -> None:
        # pylint: disable=too-many-locals
        var = _VAR_SCREENINFO.unpack(
            fcntl.ioctl(self._fd, _FBIOGET_VSCREENINFO, bytes(_VAR_SCREENINFO.size))
        )
        fix = _FIX_SCREENINFO.unpack(
            fcntl.ioctl(self._fd, _FBIOGET_FSCREENINFO, bytes(_FIX_SCREENINFO.size))
        )
        width, height, _, _, xoffset, yoffset, bits_per_pixel, grayscale = var[:8]
        # red, green, blue, transp: offset, length, msb_right
        red, green, blue, transp = var[8:11], var[11:14], var[14:17], var[17:20]
        smem_len, fb_type, visual, line_length = fix[2], fix[3], fix[5], fix[9]

        if fb_type != _FB_TYPE_PACKED_PIXELS or visual != _FB_VISUAL_TRUECOLOR:
            raise ValueError("Only true color framebuffers with packed pixels")
        if bits_per_pixel not in (16, 32) or grayscale:
            raise ValueError(f"Unsupported pixel format: {bits_per_pixel} bpp")
        fields = tuple((field[0], field[1]) for field in (red, green, blue))
        if any(length > 8 or msb_right for _, length, msb_right in (red, green, blue)):
            raise ValueError("Unsupported pixel format")

        self._width = width
        self._height = height
        self._line_length = line_length
        self._device_offset = yoffset * line_length + xoffset * bits_per_pixel // 8
        self._device_bytes = bits_per_pixel // 8
        self._mmap = mmap.mmap(
            self._fd,
            smem_len or line_length * var[3],  # yres_virtual
            mmap.MAP_SHARED,
            mmap.PROT_READ | mmap.PROT_WRITE,
        )

        rgb565 = bits_per_pixel == 16 and fields == ((11, 5), (5, 6), (0, 5))
        # Without an alpha field: displayio draws 0x00RRGGBB, transparent pixels
        # on a device that uses its alpha byte
        xrgb8888 = (
            bits_per_pixel == 32
            and fields == ((16, 8), (8, 8), (0, 8))
            and transp[1] == 0
        )
        self._color_depth = color_depth
        if (color_depth == 16 and rgb565) or (color_depth == 32 and xrgb8888):
            # displayio draws straight into the device
            self._shadow = None
            self._table = None
            self._channels = None
            return
        if color_depth == 32:
            raise ValueError("color_depth 32 needs an XRGB8888 framebuffer")
        # displayio draws RGB565 into a copy, converted into the device at each refresh
        self._shadow = bytearray(width * height * 2)
        self._areas = []
        # Opaque alpha, in case the device uses it
        alpha = ((1 << transp[1]) - 1) << transp[0]
        self._channels = None
        if bits_per_pixel == 32:
            self._channels = _byte_channels(fields, alpha)
        self._table = None
        if self._channels is None:
            self._table = _rgb565_table(fields, "H" if bits_per_pixel == 16 else "I")
            if alpha:
                for index, value in enumerate(self._table):
                    self._table[index] = value | alpha

    @staticmethod
    def _find_backlight(name: Optional[str]) -> Optional[str]:
        if name is not None:
            path = os.path.join(_BACKLIGHT_CLASS, name)
            if not os.path.isdir(path):
                raise ValueError(f"No backlight {name}")
            return path
        try:
            names = os.listdir(_BACKLIGHT_CLASS)
        except OSError:
            return None
        if len(names) == 1:
            return os.path.join(_BACKLIGHT_CLASS, names[0])
        return None

    def _console_graphics(self) -> None:
        try:
            console = os.open("/dev/tty0", os.O_RDWR | os.O_NOCTTY)
        except OSError as error:
            warnings.warn(f"The text console may draw over the display: {error}")
            return
        try:
            mode = bytearray(4)
            fcntl.ioctl(console, _KDGETMODE, mode)
            if int.from_bytes(mode, sys.byteorder) != _KD_TEXT:
                # Already in graphics mode: another program owns the console
                os.close(console)
                return
            fcntl.ioctl(console, _KDSETMODE, _KD_GRAPHICS)
        except OSError as error:
            os.close(console)
            warnings.warn(f"The text console may draw over the display: {error}")
            return
        # Only this process gives the console back to text mode, not a child it
        # forks, which inherits the atexit handler
        self._console = console
        self._console_pid = os.getpid()

    def deinit(self) -> None:
        """Release the framebuffer device and give the display back to the text console"""
        with self._lock:
            self._release()
        atexit.unregister(self.deinit)

    def _release(self) -> None:
        if self._console is not None:
            if self._console_pid == os.getpid():
                try:
                    fcntl.ioctl(self._console, _KDSETMODE, _KD_TEXT)
                except OSError:
                    pass
            os.close(self._console)
            self._console = None
        if self._mmap is not None:
            try:
                self._mmap.close()
            except BufferError:
                # Still used by a display that was not released: unmapped once
                # that display is gone
                pass
            self._mmap = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> "LinuxFramebuffer":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.deinit()

    @property
    def width(self) -> int:
        """The width of the framebuffer in pixels"""
        return self._width

    @property
    def height(self) -> int:
        """The height of the framebuffer in pixels"""
        return self._height

    # Framebuffer protocol, used by framebufferio.FramebufferDisplay

    def _get_bufinfo(self):
        if self._mmap is None:
            return None
        if self._shadow is not None:
            return self._shadow
        return self._mmap

    def _area_written(self, x1: int, y1: int, x2: int, y2: int) -> None:
        # pylint: disable=invalid-name
        if self._shadow is not None:
            self._areas.append((x1, y1, x2, y2))

    def _swapbuffers(self, dirty_row_bitmask: bytearray) -> None:
        with self._lock:
            self._swap(dirty_row_bitmask)

    def _swap(self, dirty_row_bitmask: bytearray) -> None:
        if self._shadow is None or self._mmap is None:
            return
        if self._areas:
            # Only the areas drawn, rather than the whole dirty rows: with the
            # display rotated, a small area spans many rows
            for area in self._areas:
                self._convert_area(*area)
            self._areas.clear()
            return
        row = 0
        while row < self._height:
            if not dirty_row_bitmask[row // 8] & (1 << (row & 7)):
                row += 1
                continue
            first = row
            while row < self._height and dirty_row_bitmask[row // 8] & (1 << (row & 7)):
                row += 1
            self._convert_rows(first, row)

    def _convert(self, source: memoryview):
        """Convert RGB565 bytes of the copy into bytes of the device"""
        if self._channels is not None:
            return _convert_channels(self._channels, source)
        return memoryview(
            array(self._table.typecode, map(self._table.__getitem__, source.cast("H")))
        ).cast("B")

    def _convert_area(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Convert an area of the RGB565 copy into the device"""
        # pylint: disable=invalid-name
        if x1 == 0 and x2 == self._width:
            self._convert_rows(y1, y2)
            return
        row_bytes = self._width * 2
        source = memoryview(self._shadow)
        destination = memoryview(self._mmap)
        size = (x2 - x1) * self._device_bytes
        offset = self._device_offset + y1 * self._line_length + x1 * self._device_bytes
        for row in range(y1 * row_bytes, y2 * row_bytes, row_bytes):
            destination[offset : offset + size] = self._convert(
                source[row + x1 * 2 : row + x2 * 2]
            )
            offset += self._line_length
        destination.release()
        source.release()

    def _convert_rows(self, first: int, last: int) -> None:
        """Convert the RGB565 rows first to last - 1 of the copy into the device"""
        row_bytes = self._width * 2
        device_row_bytes = self._width * self._device_bytes
        source = memoryview(self._shadow)
        destination = memoryview(self._mmap)
        if self._line_length == device_row_bytes:
            # Contiguous rows: convert them at once
            pixels = self._convert(source[first * row_bytes : last * row_bytes])
            offset = self._device_offset + first * self._line_length
            destination[offset : offset + len(pixels)] = pixels
        else:
            for row in range(first, last):
                offset = self._device_offset + row * self._line_length
                destination[offset : offset + device_row_bytes] = self._convert(
                    source[row * row_bytes : (row + 1) * row_bytes]
                )
        destination.release()
        source.release()

    def _deinit(self) -> None:
        self.deinit()

    def _get_width(self) -> int:
        return self._width

    def _get_height(self) -> int:
        return self._height

    def _get_color_depth(self) -> int:
        return self._color_depth

    def _get_bytes_per_cell(self) -> int:
        return self._color_depth // 8

    def _get_row_stride(self) -> int:
        if self._shadow is not None:
            return self._width * 2
        return self._line_length

    def _get_first_pixel_offset(self) -> int:
        if self._shadow is not None:
            return 0
        return self._device_offset

    def _get_brightness(self) -> float:
        if self._backlight is None:
            return -1
        with open(
            os.path.join(self._backlight, "brightness"), encoding="ascii"
        ) as file:
            brightness = int(file.read())
        return brightness / self._max_brightness()

    def _set_brightness(self, value: float) -> None:
        if self._backlight is None:
            raise RuntimeError("Brightness not adjustable")
        with open(
            os.path.join(self._backlight, "brightness"), "w", encoding="ascii"
        ) as file:
            file.write(str(round(value * self._max_brightness())))

    def _max_brightness(self) -> int:
        with open(
            os.path.join(self._backlight, "max_brightness"), encoding="ascii"
        ) as file:
            return int(file.read())
