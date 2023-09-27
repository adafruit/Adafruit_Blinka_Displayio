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
from array import array
from typing import Optional
import digitalio
import microcontroller
from circuitpython_typing import WriteableBuffer, ReadableBuffer
from ._displaycore import _DisplayCore
from ._displaybus import _DisplayBus
from ._colorconverter import ColorConverter
from ._group import Group, circuitpython_splash
from ._area import Area
from ._constants import (
    CHIP_SELECT_TOGGLE_EVERY_BYTE,
    CHIP_SELECT_UNTOUCHED,
    DISPLAY_COMMAND,
    DISPLAY_DATA,
    BACKLIGHT_IN_OUT,
    BACKLIGHT_PWM,
    NO_COMMAND,
    DELAY,
)

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class Display:
    # pylint: disable=too-many-instance-attributes, too-many-statements
    """This initializes a display and connects it into CircuitPython. Unlike other objects
    in CircuitPython, Display objects live until ``displayio.release_displays()`` is called.
    This is done so that CircuitPython can use the display itself.

    Most people should not use this class directly. Use a specific display driver instead
    that will contain the initialization sequence at minimum.
    """

    def __init__(
        self,
        display_bus: _DisplayBus,
        init_sequence: ReadableBuffer,
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
        single_byte_bounds: bool = False,
        data_as_commands: bool = False,
        auto_refresh: bool = True,
        native_frames_per_second: int = 60,
        backlight_on_high: bool = True,
        SH1107_addressing: bool = False,
    ):
        # pylint: disable=too-many-locals,invalid-name
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
        # Turn off auto-refresh as we init
        self._auto_refresh = False
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
            column_command=set_column_command,
            row_command=set_row_command,
            set_current_column_command=NO_COMMAND,
            set_current_row_command=NO_COMMAND,
            data_as_commands=data_as_commands,
            always_toggle_chip_select=False,
            sh1107_addressing=(SH1107_addressing and color_depth == 1),
            address_little_endian=False,
        )

        self._write_ram_command = write_ram_command
        self._brightness_command = brightness_command
        self._first_manual_refresh = not auto_refresh
        self._backlight_on_high = backlight_on_high

        self._native_frames_per_second = native_frames_per_second
        self._native_ms_per_frame = 1000 // native_frames_per_second

        self._brightness = brightness
        self._auto_refresh = auto_refresh

        i = 0
        while i < len(init_sequence):
            command = init_sequence[i]
            data_size = init_sequence[i + 1]
            delay = (data_size & DELAY) != 0
            data_size &= ~DELAY
            while self._core.begin_transaction():
                pass

            if self._core.data_as_commands:
                full_command = bytearray(data_size + 1)
                full_command[0] = command
                full_command[1:] = init_sequence[i + 2 : i + 2 + data_size]
                self._core.send(
                    DISPLAY_COMMAND,
                    CHIP_SELECT_TOGGLE_EVERY_BYTE,
                    full_command,
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
            self._core.end_transaction()
            delay_time_ms = 10
            if delay:
                data_size += 1
                delay_time_ms = init_sequence[i + 1 + data_size]
                if delay_time_ms == 255:
                    delay_time_ms = 500
            time.sleep(delay_time_ms / 1000)
            i += 2 + data_size

        self._current_group = None
        self._last_refresh_call = 0
        self._refresh_thread = None
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
        if not circuitpython_splash._in_group:
            self._set_root_group(circuitpython_splash)
        self.auto_refresh = auto_refresh

    def __new__(cls, *args, **kwargs):
        from . import (  # pylint: disable=import-outside-toplevel, cyclic-import
            allocate_display,
        )

        display_instance = super().__new__(cls)
        allocate_display(display_instance)
        return display_instance

    def _send_pixels(self, pixels):
        if not self._core.data_as_commands:
            self._core.send(
                DISPLAY_COMMAND,
                CHIP_SELECT_TOGGLE_EVERY_BYTE,
                bytes([self._write_ram_command]),
            )
        self._core.send(DISPLAY_DATA, CHIP_SELECT_UNTOUCHED, pixels)

    def show(self, group: Group) -> None:
        """Switches to displaying the given group of layers. When group is None, the
        default CircuitPython terminal will be shown.
        """
        if group is None:
            group = circuitpython_splash
        self._core.set_root_group(group)

    def _set_root_group(self, root_group: Group) -> None:
        ok = self._core.set_root_group(root_group)
        if not ok:
            raise ValueError("Group already used")

    def refresh(
        self,
        *,
        target_frames_per_second: Optional[int] = None,
        minimum_frames_per_second: int = 0,
    ) -> bool:
        """When auto refresh is off, waits for the target frame rate and then refreshes the
        display, returning True. If the call has taken too long since the last refresh call
        for the given target frame rate, then the refresh returns False immediately without
        updating the screen to hopefully help getting caught up.

        If the time since the last successful refresh is below the minimum frame rate, then
        an exception will be raised. Set minimum_frames_per_second to 0 to disable.

        When auto refresh is on, updates the display immediately. (The display will also
        update without calls to this.)
        """
        maximum_ms_per_real_frame = 0xFFFFFFFF
        if minimum_frames_per_second > 0:
            maximum_ms_per_real_frame = 1000 // minimum_frames_per_second

        if target_frames_per_second is None:
            target_ms_per_frame = 0xFFFFFFFF
        else:
            target_ms_per_frame = 1000 // target_frames_per_second

        if (
            not self._auto_refresh
            and not self._first_manual_refresh
            and target_ms_per_frame != 0xFFFFFFFF
        ):
            current_time = time.monotonic() * 1000
            current_ms_since_real_refresh = current_time - self._core.last_refresh
            if current_ms_since_real_refresh > maximum_ms_per_real_frame:
                raise RuntimeError("Below minimum frame rate")
            current_ms_since_last_call = current_time - self._last_refresh_call
            self._last_refresh_call = current_time
            if current_ms_since_last_call > target_ms_per_frame:
                return False

            remaining_time = target_ms_per_frame - (
                current_ms_since_real_refresh % target_ms_per_frame
            )
            time.sleep(remaining_time / 1000)
        self._first_manual_refresh = False
        self._refresh_display()
        return True

    def _refresh_display(self):
        if not self._core.start_refresh():
            return False

        areas_to_refresh = self._get_refresh_areas()
        for area in areas_to_refresh:
            self._refresh_area(area)

        self._core.finish_refresh()

        return True

    def _get_refresh_areas(self) -> list[Area]:
        """Get a list of areas to be refreshed"""
        areas = []
        if self._core.full_refresh:
            areas.append(self._core.area)
        elif self._core.current_group is not None:
            self._core.current_group._get_refresh_areas(  # pylint: disable=protected-access
                areas
            )
        return areas

    def background(self):
        """Run background refresh tasks. Do not call directly"""
        if (
            self._auto_refresh
            and (time.monotonic() * 1000 - self._core.last_refresh)
            > self._native_ms_per_frame
        ):
            self.refresh()

    def _refresh_area(self, area) -> bool:
        """Loop through dirty areas and redraw that area."""
        # pylint: disable=too-many-locals

        clipped = Area()
        # Clip the area to the display by overlapping the areas.
        # If there is no overlap then we're done.
        if not self._core.clip_area(area, clipped):
            return True

        rows_per_buffer = clipped.height()
        pixels_per_word = 32 // self._core.colorspace.depth
        pixels_per_buffer = clipped.size()

        # We should have lots of memory
        buffer_size = clipped.size() // pixels_per_word

        subrectangles = 1
        # for SH1107 and other boundary constrained controllers
        #      write one single row at a time
        if self._core.sh1107_addressing:
            subrectangles = rows_per_buffer // 8
            rows_per_buffer = 8
        elif clipped.size() > buffer_size * pixels_per_word:
            rows_per_buffer = buffer_size * pixels_per_word // clipped.width()
            if rows_per_buffer == 0:
                rows_per_buffer = 1
            # If pixels are packed by column then ensure rows_per_buffer is on a byte boundary
            if (
                self._core.colorspace.depth < 8
                and self._core.colorspace.pixels_in_byte_share_row
            ):
                pixels_per_byte = 8 // self._core.colorspace.depth
                if rows_per_buffer % pixels_per_byte != 0:
                    rows_per_buffer -= rows_per_buffer % pixels_per_byte
            subrectangles = clipped.height() // rows_per_buffer
            if clipped.height() % rows_per_buffer != 0:
                subrectangles += 1
            pixels_per_buffer = rows_per_buffer * clipped.width()
            buffer_size = pixels_per_buffer // pixels_per_word
            if pixels_per_buffer % pixels_per_word:
                buffer_size += 1
        mask_length = (pixels_per_buffer // 8) + 1  # 1 bit per pixel + 1
        remaining_rows = clipped.height()

        for subrect_index in range(subrectangles):
            subrectangle = Area(
                clipped.x1,
                clipped.y1 + rows_per_buffer * subrect_index,
                clipped.x2,
                clipped.y1 + rows_per_buffer * (subrect_index + 1),
            )
            if remaining_rows < rows_per_buffer:
                subrectangle.y2 = subrectangle.y1 + remaining_rows
            remaining_rows -= rows_per_buffer
            self._core.set_region_to_update(subrectangle)
            if self._core.colorspace.depth >= 8:
                subrectangle_size_bytes = subrectangle.size() * (
                    self._core.colorspace.depth // 8
                )
            else:
                subrectangle_size_bytes = subrectangle.size() // (
                    8 // self._core.colorspace.depth
                )

            buffer = memoryview(bytearray([0] * (buffer_size * 4)))
            mask = memoryview(bytearray([0] * mask_length))
            self._core.fill_area(subrectangle, mask, buffer)
            self._core.begin_transaction()
            self._send_pixels(buffer[:subrectangle_size_bytes])
            self._core.end_transaction()
        return True

    def fill_row(self, y: int, buffer: WriteableBuffer) -> WriteableBuffer:
        """Extract the pixels from a single row"""
        if self._core.colorspace.depth != 16:
            raise ValueError("Display must have a 16 bit colorspace.")

        area = Area(0, y, self._core.width, y + 1)
        pixels_per_word = 32 // self._core.colorspace.depth
        buffer_size = self._core.width // pixels_per_word
        pixels_per_buffer = area.size()
        if pixels_per_buffer % pixels_per_word:
            buffer_size += 1

        buffer = bytearray([0] * (buffer_size * 4))
        mask_length = (pixels_per_buffer // 32) + 1
        mask = array("L", [0x00000000] * mask_length)
        self._core.fill_area(area, mask, buffer)
        return buffer

    def release(self) -> None:
        """Release the display and free its resources"""
        self.auto_refresh = False
        self._core.release_display_core()

    def reset(self) -> None:
        """Reset the display"""
        self.auto_refresh = True
        circuitpython_splash.x = 0
        circuitpython_splash.y = 0
        if not circuitpython_splash._in_group:  # pylint: disable=protected-access
            self._set_root_group(circuitpython_splash)

    @property
    def auto_refresh(self) -> bool:
        """True when the display is refreshed automatically."""
        return self._auto_refresh

    @auto_refresh.setter
    def auto_refresh(self, value: bool):
        self._first_manual_refresh = not value
        self._auto_refresh = value

    @property
    def brightness(self) -> float:
        """The brightness of the display as a float. 0.0 is off and 1.0 is full `brightness`."""
        return self._brightness

    @brightness.setter
    def brightness(self, value: float):
        if 0 <= float(value) <= 1.0:
            if not self._backlight_on_high:
                value = 1.0 - value

            if self._backlight_type == BACKLIGHT_PWM:
                self._backlight.duty_cycle = value * 0xFFFF
            elif self._backlight_type == BACKLIGHT_IN_OUT:
                self._backlight.value = value > 0.99
            elif self._brightness_command is not None:
                okay = self._core.begin_transaction()
                if okay:
                    if self._core.data_as_commands:
                        self._core.send(
                            DISPLAY_COMMAND,
                            CHIP_SELECT_TOGGLE_EVERY_BYTE,
                            bytes([self._brightness_command, round(0xFF * value)]),
                        )
                    else:
                        self._core.send(
                            DISPLAY_COMMAND,
                            CHIP_SELECT_TOGGLE_EVERY_BYTE,
                            bytes([self._brightness_command]),
                        )
                        self._core.send(
                            DISPLAY_DATA, CHIP_SELECT_UNTOUCHED, round(value * 255)
                        )
                    self._core.end_transaction()
            self._brightness = value
        else:
            raise ValueError("Brightness must be between 0.0 and 1.0")

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
