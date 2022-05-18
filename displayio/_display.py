# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.display`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

import time
import struct
import threading
from typing import Optional
from dataclasses import astuple
import digitalio
from PIL import Image
import numpy
import microcontroller
import circuitpython_typing
from ._displaycore import _DisplayCore
from ._displaybus import _DisplayBus
from ._colorconverter import ColorConverter
from ._group import Group
from ._structs import RectangleStruct
from ._constants import (
    CHIP_SELECT_TOGGLE_EVERY_BYTE,
    CHIP_SELECT_UNTOUCHED,
    DISPLAY_COMMAND,
    DISPLAY_DATA,
    BACKLIGHT_IN_OUT,
    BACKLIGHT_PWM,
)

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

displays = []


class Display:
    # pylint: disable=too-many-instance-attributes
    """This initializes a display and connects it into CircuitPython. Unlike other objects
    in CircuitPython, Display objects live until ``displayio.release_displays()`` is called.
    This is done so that CircuitPython can use the display itself.

    Most people should not use this class directly. Use a specific display driver instead
    that will contain the initialization sequence at minimum.
    """

    def __init__(
        self,
        display_bus: _DisplayBus,
        init_sequence: circuitpython_typing.ReadableBuffer,
        *,
        width: int,
        height: int,
        colstart: int = 0,
        rowstart: int = 0,
        rotation: int = 0,
        color_depth: int = 16,
        grayscale: bool = False,
        pixels_in_byte_share_row: bool = True,
        bytes_per_cell: int = 1,
        reverse_pixels_in_byte: bool = False,
        reverse_bytes_in_word: bool = True,
        set_column_command: int = 0x2A,
        set_row_command: int = 0x2B,
        write_ram_command: int = 0x2C,
        backlight_pin: Optional[microcontroller.Pin] = None,
        brightness_command: Optional[int] = None,
        brightness: float = 1.0,
        auto_brightness: bool = False,
        single_byte_bounds: bool = False,
        data_as_commands: bool = False,
        auto_refresh: bool = True,
        native_frames_per_second: int = 60,
        backlight_on_high: bool = True,
        SH1107_addressing: bool = False,
        set_vertical_scroll: int = 0,
    ):
        # pylint: disable=unused-argument,too-many-locals,invalid-name
        """Create a Display object on the given display bus (`displayio.FourWire` or
        `paralleldisplay.ParallelBus`).

        The ``init_sequence`` is bitpacked to minimize the ram impact. Every command begins
        with a command byte followed by a byte to determine the parameter count and if a
        delay is need after. When the top bit of the second byte is 1, the next byte will be
        the delay time in milliseconds. The remaining 7 bits are the parameter count
        excluding any delay byte. The third through final bytes are the remaining command
        parameters. The next byte will begin a new command definition. Here is a portion of
        ILI9341 init code:

        .. code-block:: python

            init_sequence = (
                b"\\xE1\\x0F\\x00\\x0E\\x14\\x03\\x11\\x07\\x31\
\\xC1\\x48\\x08\\x0F\\x0C\\x31\\x36\\x0F"
                b"\\x11\\x80\\x78"  # Exit Sleep then delay 0x78 (120ms)
                b"\\x29\\x80\\x78"  # Display on then delay 0x78 (120ms)
            )
            display = displayio.Display(display_bus, init_sequence, width=320, height=240)

        The first command is 0xE1 with 15 (0x0F) parameters following. The second and third
        are 0x11 and 0x29 respectively with delays (0x80) of 120ms (0x78) and no parameters.
        Multiple byte literals (b”“) are merged together on load. The parens are needed to
        allow byte literals on subsequent lines.

        The initialization sequence should always leave the display memory access inline with
        the scan of the display to minimize tearing artifacts.
        """
        ram_width = 0x100
        ram_height = 0x100
        if single_byte_bounds:
            ram_width = 0xFF
            ram_height = 0xFF
        self._core = _DisplayCore(
            bus=display_bus,
            width=width,
            height=height,
            ram_width=ram_width,
            ram_height=ram_height,
            colstart=colstart,
            rowstart=rowstart,
            rotation=rotation,
            color_depth=color_depth,
            grayscale=grayscale,
            pixels_in_byte_share_row=pixels_in_byte_share_row,
            bytes_per_cell=bytes_per_cell,
            reverse_pixels_in_byte=reverse_pixels_in_byte,
            reverse_bytes_in_word=reverse_bytes_in_word,
        )

        self._set_column_command = set_column_command
        self._set_row_command = set_row_command
        self._write_ram_command = write_ram_command
        self._brightness_command = brightness_command
        self._data_as_commands = data_as_commands
        self._single_byte_bounds = single_byte_bounds
        self._width = width
        self._height = height
        self._colstart = colstart
        self._rowstart = rowstart
        self._rotation = rotation
        self._auto_brightness = auto_brightness
        self._brightness = 1.0
        self._auto_refresh = auto_refresh
        self._initialize(init_sequence)
        self._buffer = Image.new("RGB", (width, height))
        self._subrectangles = []
        self._bounds_encoding = ">BB" if single_byte_bounds else ">HH"
        self._current_group = None
        displays.append(self)
        self._refresh_thread = None
        if self._auto_refresh:
            self.auto_refresh = True
        self._colorconverter = ColorConverter()

        self._backlight_type = None
        if backlight_pin is not None:
            try:
                from pwmio import PWMOut  # pylint: disable=import-outside-toplevel

                # 100Hz looks decent and doesn't keep the CPU too busy
                self._backlight = PWMOut(backlight_pin, frequency=100, duty_cycle=0)
                self._backlight_type = BACKLIGHT_PWM
            except ImportError:
                # PWMOut not implemented on this platform
                pass
            if self._backlight_type is None:
                self._backlight_type = BACKLIGHT_IN_OUT
                self._backlight = digitalio.DigitalInOut(backlight_pin)
                self._backlight.switch_to_output()
            self.brightness = brightness

    def _initialize(self, init_sequence):
        i = 0
        while i < len(init_sequence):
            command = init_sequence[i]
            data_size = init_sequence[i + 1]
            delay = (data_size & 0x80) > 0
            data_size &= ~0x80

            if self._data_as_commands:
                self._core.send(
                    DISPLAY_COMMAND,
                    CHIP_SELECT_TOGGLE_EVERY_BYTE,
                    bytes([command]) + init_sequence[i + 2 : i + 2 + data_size],
                )
            else:
                self._core.send(
                    DISPLAY_COMMAND, CHIP_SELECT_TOGGLE_EVERY_BYTE, bytes([command])
                )
                self._core.send(
                    DISPLAY_DATA,
                    CHIP_SELECT_UNTOUCHED,
                    init_sequence[i + 2 : i + 2 + data_size],
                )
            delay_time_ms = 10
            if delay:
                data_size += 1
                delay_time_ms = init_sequence[i + 1 + data_size]
                if delay_time_ms == 255:
                    delay_time_ms = 500
            time.sleep(delay_time_ms / 1000)
            i += 2 + data_size

    def _send(self, command, data):
        self._core.begin_transaction()
        if self._data_as_commands:
            self._core.send(
                DISPLAY_COMMAND, CHIP_SELECT_TOGGLE_EVERY_BYTE, bytes([command]) + data
            )
        else:
            self._core.send(
                DISPLAY_COMMAND, CHIP_SELECT_TOGGLE_EVERY_BYTE, bytes([command])
            )
            self._core.send(DISPLAY_DATA, CHIP_SELECT_UNTOUCHED, data)
        self._core.end_transaction()

    def _send_pixels(self, data):
        if not self._data_as_commands:
            self._core.send(
                DISPLAY_COMMAND,
                CHIP_SELECT_TOGGLE_EVERY_BYTE,
                bytes([self._write_ram_command]),
            )
        self._core.send(DISPLAY_DATA, CHIP_SELECT_UNTOUCHED, data)

    def show(self, group: Group) -> None:
        """Switches to displaying the given group of layers. When group is None, the
        default CircuitPython terminal will be shown.
        """
        self._core.show(group)

    def refresh(
        self,
        *,
        target_frames_per_second: Optional[int] = None,
        minimum_frames_per_second: int = 0,
    ) -> bool:
        # pylint: disable=unused-argument, protected-access
        """When auto refresh is off, waits for the target frame rate and then refreshes the
        display, returning True. If the call has taken too long since the last refresh call
        for the given target frame rate, then the refresh returns False immediately without
        updating the screen to hopefully help getting caught up.

        If the time since the last successful refresh is below the minimum frame rate, then
        an exception will be raised. Set minimum_frames_per_second to 0 to disable.

        When auto refresh is on, updates the display immediately. (The display will also
        update without calls to this.)
        """
        if not self._core.start_refresh():
            return False

        # Go through groups and and add each to buffer
        if self._core._current_group is not None:
            buffer = Image.new("RGBA", (self._core._width, self._core._height))
            # Recursively have everything draw to the image
            self._core._current_group._fill_area(
                buffer
            )  # pylint: disable=protected-access
            # save image to buffer (or probably refresh buffer so we can compare)
            self._buffer.paste(buffer)

        self._subrectangles = self._core.get_refresh_areas()

        for area in self._subrectangles:
            self._refresh_display_area(area)

        self._core.finish_refresh()

        return True

    def _refresh_loop(self):
        while self._auto_refresh:
            self.refresh()

    def _refresh_display_area(self, rectangle):
        """Loop through dirty rectangles and redraw that area."""
        img = self._buffer.convert("RGB").crop(astuple(rectangle))
        img = img.rotate(360 - self._rotation, expand=True)

        display_rectangle = self._apply_rotation(rectangle)
        img = img.crop(astuple(self._clip(display_rectangle)))

        data = numpy.array(img).astype("uint16")
        color = (
            ((data[:, :, 0] & 0xF8) << 8)
            | ((data[:, :, 1] & 0xFC) << 3)
            | (data[:, :, 2] >> 3)
        )

        pixels = bytes(
            numpy.dstack(((color >> 8) & 0xFF, color & 0xFF)).flatten().tolist()
        )

        self._send(
            self._set_column_command,
            self._encode_pos(
                display_rectangle.x1 + self._colstart,
                display_rectangle.x2 + self._colstart - 1,
            ),
        )
        self._send(
            self._set_row_command,
            self._encode_pos(
                display_rectangle.y1 + self._rowstart,
                display_rectangle.y2 + self._rowstart - 1,
            ),
        )

        self._core.begin_transaction()
        self._send_pixels(pixels)
        self._core.end_transaction()

    def _clip(self, rectangle):
        if self._rotation in (90, 270):
            width, height = self._height, self._width
        else:
            width, height = self._width, self._height

        rectangle.x1 = max(rectangle.x1, 0)
        rectangle.y1 = max(rectangle.y1, 0)
        rectangle.x2 = min(rectangle.x2, width)
        rectangle.y2 = min(rectangle.y2, height)

        return rectangle

    def _apply_rotation(self, rectangle):
        """Adjust the rectangle coordinates based on rotation"""
        if self._rotation == 90:
            return RectangleStruct(
                self._height - rectangle.y2,
                rectangle.x1,
                self._height - rectangle.y1,
                rectangle.x2,
            )
        if self._rotation == 180:
            return RectangleStruct(
                self._width - rectangle.x2,
                self._height - rectangle.y2,
                self._width - rectangle.x1,
                self._height - rectangle.y1,
            )
        if self._rotation == 270:
            return RectangleStruct(
                rectangle.y1,
                self._width - rectangle.x2,
                rectangle.y2,
                self._width - rectangle.x1,
            )
        return rectangle

    def _encode_pos(self, x, y):
        """Encode a postion into bytes."""
        return struct.pack(self._bounds_encoding, x, y)  # pylint: disable=no-member

    def fill_row(
        self, y: int, buffer: circuitpython_typing.WriteableBuffer
    ) -> circuitpython_typing.WriteableBuffer:
        """Extract the pixels from a single row"""
        for x in range(0, self._width):
            _rgb_565 = self._colorconverter.convert(self._buffer.getpixel((x, y)))
            buffer[x * 2] = (_rgb_565 >> 8) & 0xFF
            buffer[x * 2 + 1] = _rgb_565 & 0xFF
        return buffer

    @property
    def auto_refresh(self) -> bool:
        """True when the display is refreshed automatically."""
        return self._auto_refresh

    @auto_refresh.setter
    def auto_refresh(self, value: bool):
        self._auto_refresh = value
        if self._refresh_thread is None:
            self._refresh_thread = threading.Thread(
                target=self._refresh_loop, daemon=True
            )
        if value and not self._refresh_thread.is_alive():
            # Start the thread
            self._refresh_thread.start()
        elif not value and self._refresh_thread.is_alive():
            # Stop the thread
            self._refresh_thread.join()

    @property
    def brightness(self) -> float:
        """The brightness of the display as a float. 0.0 is off and 1.0 is full `brightness`.
        When `auto_brightness` is True, the value of `brightness` will change automatically.
        If `brightness` is set, `auto_brightness` will be disabled and will be set to False.
        """
        return self._brightness

    @brightness.setter
    def brightness(self, value: float):
        if 0 <= float(value) <= 1.0:
            self._brightness = value
            if self._backlight_type == BACKLIGHT_IN_OUT:
                self._backlight.value = round(self._brightness)
            elif self._backlight_type == BACKLIGHT_PWM:
                self._backlight.duty_cycle = self._brightness * 65535
            elif self._brightness_command is not None:
                self._send(self._brightness_command, round(value * 255))
        else:
            raise ValueError("Brightness must be between 0.0 and 1.0")

    @property
    def auto_brightness(self) -> bool:
        """True when the display brightness is adjusted automatically, based on an ambient
        light sensor or other method. Note that some displays may have this set to True by
        default, but not actually implement automatic brightness adjustment.
        `auto_brightness` is set to False if `brightness` is set manually.
        """
        return self._auto_brightness

    @auto_brightness.setter
    def auto_brightness(self, value: bool):
        self._auto_brightness = value

    @property
    def width(self) -> int:
        """Display Width"""
        return self._core.get_width()

    @property
    def height(self) -> int:
        """Display Height"""
        return self._core.get_height()

    @property
    def rotation(self) -> int:
        """The rotation of the display as an int in degrees."""
        return self._core.get_rotation()

    @rotation.setter
    def rotation(self, value: int):
        self._core.set_rotation(value)

    @property
    def bus(self) -> _DisplayBus:
        """Current Display Bus"""
        return self._core.get_bus()
