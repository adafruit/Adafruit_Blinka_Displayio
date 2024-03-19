# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.epaperdisplay`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

import time
from typing import Optional, Union
import microcontroller
from digitalio import DigitalInOut
from circuitpython_typing import ReadableBuffer
from displayio._displaycore import _DisplayCore
from displayio._group import Group, circuitpython_splash
from displayio._colorconverter import ColorConverter
from busdisplay._displaybus import _DisplayBus
from displayio._area import Area
from displayio._constants import (
    CHIP_SELECT_TOGGLE_EVERY_BYTE,
    CHIP_SELECT_UNTOUCHED,
    DISPLAY_COMMAND,
    DISPLAY_DATA,
    NO_COMMAND,
    DELAY,
)

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class EPaperDisplay:
    # pylint: disable=too-many-instance-attributes, too-many-statements
    """Manage updating an epaper display over a display bus

    This initializes an epaper display and connects it into CircuitPython. Unlike other
    objects in CircuitPython, EPaperDisplay objects live until
    displayio.release_displays() is called. This is done so that CircuitPython can use
    the display itself.

    Most people should not use this class directly. Use a specific display driver instead
    that will contain the startup and shutdown sequences at minimum.
    """

    def __init__(
        self,
        display_bus: _DisplayBus,
        start_sequence: ReadableBuffer,
        stop_sequence: ReadableBuffer,
        *,
        width: int,
        height: int,
        ram_width: int,
        ram_height: int,
        colstart: int = 0,
        rowstart: int = 0,
        rotation: int = 0,
        set_column_window_command: Optional[int] = None,
        set_row_window_command: Optional[int] = None,
        set_current_column_command: Optional[int] = None,
        set_current_row_command: Optional[int] = None,
        write_black_ram_command: int,
        black_bits_inverted: bool = False,
        write_color_ram_command: Optional[int] = None,
        color_bits_inverted: bool = False,
        highlight_color: int = 0x000000,
        refresh_display_command: Union[int, ReadableBuffer],
        refresh_time: float = 40,
        busy_pin: Optional[microcontroller.Pin] = None,
        busy_state: bool = True,
        seconds_per_frame: float = 180,
        always_toggle_chip_select: bool = False,
        grayscale: bool = False,
        advanced_color_epaper: bool = False,
        two_byte_sequence_length: bool = False,
        start_up_time: float = 0,
        address_little_endian: bool = False,
    ) -> None:
        # pylint: disable=too-many-locals
        """Create a EPaperDisplay object on the given display bus (`displayio.FourWire` or
        `paralleldisplay.ParallelBus`).

        The ``start_sequence`` and ``stop_sequence`` are bitpacked to minimize the ram impact. Every
        command begins with a command byte followed by a byte to determine the parameter count and
        delay. When the top bit of the second byte is 1 (0x80), a delay will occur after the command
        parameters are sent. The remaining 7 bits are the parameter count excluding any delay
        byte. The bytes following are the parameters. When the delay bit is set, a single byte after
        the parameters specifies the delay duration in milliseconds. The value 0xff will lead to an
        extra long 500 ms delay instead of 255 ms. The next byte will begin a new command
        definition.

        :param display_bus: The bus that the display is connected to
        :type _DisplayBus: displayio.FourWire or paralleldisplay.ParallelBus
        :param ~circuitpython_typing.ReadableBuffer start_sequence: Byte-packed command sequence.
        :param ~circuitpython_typing.ReadableBuffer stop_sequence: Byte-packed command sequence.
        :param int width: Width in pixels
        :param int height: Height in pixels
        :param int ram_width: RAM width in pixels
        :param int ram_height: RAM height in pixels
        :param int colstart: The index if the first visible column
        :param int rowstart: The index if the first visible row
        :param int rotation: The rotation of the display in degrees clockwise. Must be in
            90 degree increments (0, 90, 180, 270)
        :param int set_column_window_command: Command used to set the start and end columns
            to update
        :param int set_row_window_command: Command used so set the start and end rows to update
        :param int set_current_column_command: Command used to set the current column location
        :param int set_current_row_command: Command used to set the current row location
        :param int write_black_ram_command: Command used to write pixels values into the update
            region
        :param bool black_bits_inverted: True if 0 bits are used to show black pixels. Otherwise,
            1 means to show black.
        :param int write_color_ram_command: Command used to write pixels values into the update
            region
        :param bool color_bits_inverted: True if 0 bits are used to show the color. Otherwise, 1
            means to show color.
        :param int highlight_color: RGB888 of source color to highlight with third ePaper color.
        :param int refresh_display_command: Command used to start a display refresh. Single int
            or byte-packed command sequence
        :param float refresh_time: Time it takes to refresh the display before the stop_sequence
            should be sent. Ignored when busy_pin is provided.
        :param microcontroller.Pin busy_pin: Pin used to signify the display is busy
        :param bool busy_state: State of the busy pin when the display is busy
        :param float seconds_per_frame: Minimum number of seconds between screen refreshes
        :param bool always_toggle_chip_select: When True, chip select is toggled every byte
        :param bool grayscale: When true, the color ram is the low bit of 2-bit grayscale
        :param bool advanced_color_epaper: When true, the display is a 7-color advanced color
            epaper (ACeP)
        :param bool two_byte_sequence_length: When true, use two bytes to define sequence length
        :param float start_up_time: Time to wait after reset before sending commands
        :param bool address_little_endian: Send the least significant byte (not bit) of
            multi-byte addresses first. Ignored when ram is addressed with one byte
        """

        if isinstance(refresh_display_command, int):
            refresh_sequence = bytearray([refresh_display_command, 0])
            if two_byte_sequence_length:
                refresh_sequence += bytes([0])
        elif isinstance(refresh_display_command, ReadableBuffer):
            refresh_sequence = bytearray(refresh_display_command)
        else:
            raise ValueError("Invalid refresh_display_command")

        if write_color_ram_command is None:
            write_color_ram_command = NO_COMMAND

        if rotation % 90 != 0:
            raise ValueError("Display rotation must be in 90 degree increments")

        self._refreshing = False
        color_depth = 1
        core_grayscale = True

        if advanced_color_epaper:
            color_depth = 4
            grayscale = False
            core_grayscale = False

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
            grayscale=core_grayscale,
            pixels_in_byte_share_row=True,
            bytes_per_cell=1,
            reverse_pixels_in_byte=True,
            reverse_bytes_in_word=True,
            column_command=set_column_window_command,
            row_command=set_row_window_command,
            set_current_column_command=set_current_column_command,
            set_current_row_command=set_current_row_command,
            data_as_commands=False,
            always_toggle_chip_select=always_toggle_chip_select,
            sh1107_addressing=False,
            address_little_endian=address_little_endian,
        )

        if highlight_color != 0x000000:
            self._core.colorspace.tricolor = True
            self._core.colorspace.tricolor_hue = ColorConverter._compute_hue(
                highlight_color
            )
            self._core.colorspace.tricolor_luma = ColorConverter._compute_luma(
                highlight_color
            )
        else:
            self._core.colorspace.tricolor = False

        self._acep = advanced_color_epaper
        self._core.colorspace.sevencolor = advanced_color_epaper
        self._write_black_ram_command = write_black_ram_command
        self._black_bits_inverted = black_bits_inverted
        self._write_color_ram_command = write_color_ram_command
        self._color_bits_inverted = color_bits_inverted
        self._refresh_time_ms = refresh_time * 1000
        self._busy_state = busy_state
        self._milliseconds_per_frame = seconds_per_frame * 1000
        self._chip_select = (
            CHIP_SELECT_TOGGLE_EVERY_BYTE
            if always_toggle_chip_select
            else CHIP_SELECT_UNTOUCHED
        )
        self._grayscale = grayscale

        self._start_sequence = start_sequence
        self._start_up_time = start_up_time
        self._stop_sequence = stop_sequence
        self._refresh_sequence = refresh_sequence
        self._busy = None
        self._two_byte_sequence_length = two_byte_sequence_length
        if busy_pin is not None:
            self._busy = DigitalInOut(busy_pin)
            self._busy.switch_to_input()

        self._ticks_disabled = False

        # Clear the color memory if it isn't in use
        if highlight_color == 0x00 and write_color_ram_command != NO_COMMAND:
            """TODO: Clear"""

        self._set_root_group(circuitpython_splash)

    def __new__(cls, *args, **kwargs):
        from ..displayio import (  # pylint: disable=import-outside-toplevel, cyclic-import
            allocate_display,
        )

        display_instance = super().__new__(cls)
        allocate_display(display_instance)
        return display_instance

    def show(self, _group: Group) -> None: # pylint: disable=missing-function-docstring
        raise AttributeError(".show(x) removed. Use .root_group = x")

    def _set_root_group(self, root_group: Group) -> None:
        ok = self._core.set_root_group(root_group)
        if not ok:
            raise ValueError("Group already used")

    def update_refresh_mode(
        self, start_sequence: ReadableBuffer, seconds_per_frame: float
    ) -> None:
        """Updates the ``start_sequence`` and ``seconds_per_frame`` parameters to enable
        varying the refresh mode of the display."""
        self._start_sequence = bytearray(start_sequence)
        self._milliseconds_per_frame = seconds_per_frame * 1000

    def refresh(self) -> None:
        """Refreshes the display immediately or raises an exception if too soon. Use
        ``time.sleep(display.time_to_refresh)`` to sleep until a refresh can occur.
        """
        if not self._refresh():
            raise RuntimeError("Refresh too soon")

    def _refresh(self) -> bool:
        if self._refreshing and self._busy is not None:
            if self._busy.value != self._busy_state:
                self._ticks_disabled = True
                self._refreshing = False
                self._send_command_sequence(False, self._stop_sequence)
            else:
                return False
        if self._core.current_group is None:
            return True
        # Refresh at seconds per frame rate
        if self.time_to_refresh > 0:
            return False

        if not self._core.bus_free():
            # Can't acquire display bus; skip updating this display. Try next display
            return False

        areas_to_refresh = self._get_refresh_areas()
        if not areas_to_refresh:
            return True

        if self._acep:
            self._start_refresh()
            self._clean_area()
            self._finish_refresh()
            while self._refreshing:
                # TODO: Add something here that can change self._refreshing
                # or add something in _background()
                pass

        self._start_refresh()
        for area in areas_to_refresh:
            self._refresh_area(area)
        self._finish_refresh()

        return True

    def _release(self) -> None:
        """Release the display and free its resources"""
        if self._refreshing:
            self._wait_for_busy()
            self._ticks_disabled = True
            self._refreshing = False
            # Run stop sequence but don't wait for busy because busy is set when sleeping
            self._send_command_sequence(False, self._stop_sequence)
        self._core.release_display_core()
        if self._busy is not None:
            self._busy.deinit()

    def _background(self) -> None:
        """Run background refresh tasks."""

        # Wait until initialized
        if not hasattr(self, "_core"):
            return

        if self._ticks_disabled:
            return

        if self._refreshing:
            refresh_done = False
            if self._busy is not None:
                busy = self._busy.value
                refresh_done = busy == self._busy_state
            else:
                refresh_done = (
                    time.monotonic() * 1000 - self._core.last_refresh
                    > self._refresh_time
                )

            if refresh_done:
                self._ticks_disabled = True
                self._refreshing = False
                # Run stop sequence but don't wait for busy because busy is set when sleeping
                self._send_command_sequence(False, self._stop_sequence)

    def _get_refresh_areas(self) -> list[Area]:
        """Get a list of areas to be refreshed"""
        areas = []
        if self._core.full_refresh:
            areas.append(self._core.area)
            return areas
        first_area = None
        if self._core.current_group is not None:
            self._core.current_group._get_refresh_areas(  # pylint: disable=protected-access
                areas
            )
            first_area = areas[0]
        if first_area is not None and self._core.row_command == NO_COMMAND:
            # Do a full refresh if the display doesn't support partial updates
            areas = [self._core.area]
        return areas

    def _refresh_area(self, area: Area) -> bool:
        """Redraw the area."""
        # pylint: disable=too-many-locals, too-many-branches
        clipped = Area()
        # Clip the area to the display by overlapping the areas.
        # If there is no overlap then we're done.
        if not self._core.clip_area(area, clipped):
            return True
        subrectangles = 1
        rows_per_buffer = clipped.height()
        pixels_per_word = 32 // self._core.colorspace.depth
        pixels_per_buffer = clipped.size()

        # We should have lots of memory
        buffer_size = clipped.size() // pixels_per_word

        if clipped.size() > buffer_size * pixels_per_word:
            rows_per_buffer = buffer_size * pixels_per_word // clipped.width()
            if rows_per_buffer == 0:
                rows_per_buffer = 1
            subrectangles = clipped.height() // rows_per_buffer
            if clipped.height() % rows_per_buffer != 0:
                subrectangles += 1
            pixels_per_buffer = rows_per_buffer * clipped.width()
            buffer_size = pixels_per_buffer // pixels_per_word
            if pixels_per_buffer % pixels_per_word:
                buffer_size += 1

        mask_length = (pixels_per_buffer // 32) + 1  # 1 bit per pixel + 1

        passes = 1
        if self._write_color_ram_command != NO_COMMAND:
            passes = 2
        for pass_index in range(passes):
            remaining_rows = clipped.height()
            if self._core.row_command != NO_COMMAND:
                self._core.set_region_to_update(clipped)

            write_command = self._write_black_ram_command
            if pass_index == 1:
                write_command = self._write_color_ram_command

            self._core.begin_transaction()
            self._core.send(DISPLAY_COMMAND, self._chip_select, bytes([write_command]))
            self._core.end_transaction()

            for subrect_index in range(subrectangles):
                subrectangle = Area(
                    x1=clipped.x1,
                    y1=clipped.y1 + rows_per_buffer * subrect_index,
                    x2=clipped.x2,
                    y2=clipped.y1 + rows_per_buffer * (subrect_index + 1),
                )
                if remaining_rows < rows_per_buffer:
                    subrectangle.y2 = subrectangle.y1 + remaining_rows
                remaining_rows -= rows_per_buffer

                subrectangle_size_bytes = subrectangle.size() // (
                    8 // self._core.colorspace.depth
                )

                buffer = memoryview(bytearray([0] * (buffer_size * 4))).cast("I")
                mask = memoryview(bytearray([0] * (mask_length * 4))).cast("I")

                if not self._acep:
                    self._core.colorspace.grayscale = True
                    self._core.colorspace.grayscale_bit = 7
                if pass_index == 1:
                    if self._grayscale:  # 4-color grayscale
                        self._core.colorspace.grayscale_bit = 6
                        self._core.fill_area(subrectangle, mask, buffer)
                    elif self._core.colorspace.tricolor:
                        self._core.colorspace.grayscale = False
                        self._core.fill_area(subrectangle, mask, buffer)
                    elif self._core.colorspace.sevencolor:
                        self._core.fill_area(subrectangle, mask, buffer)
                else:
                    self._core.fill_area(subrectangle, mask, buffer)

                # Invert it all
                if (pass_index == 1 and self._color_bits_inverted) or (
                    pass_index == 0 and self._black_bits_inverted
                ):
                    for i in range(buffer_size):
                        buffer[i] = ~buffer[i]

                if not self._core.begin_transaction():
                    # Can't acquire display bus; skip the rest of the data. Try next display.
                    return False
                self._core.send(
                    DISPLAY_DATA,
                    self._chip_select,
                    buffer.tobytes()[:subrectangle_size_bytes],
                )
                self._core.end_transaction()
        return True

    def _send_command_sequence(
        self, should_wait_for_busy: bool, sequence: ReadableBuffer
    ) -> None:
        i = 0
        while i < len(sequence):
            command = sequence[i]
            data_size = sequence[i + 1]
            delay = (data_size & DELAY) != 0
            data_size &= ~DELAY
            data = sequence[i + 2 : i + 2 + data_size]
            if self._two_byte_sequence_length:
                data_size = ((data_size & ~DELAY) << 8) + sequence[i + 2]
                data = sequence[i + 3 : i + 3 + data_size]

            self._core.begin_transaction()
            self._core.send(
                DISPLAY_COMMAND, CHIP_SELECT_TOGGLE_EVERY_BYTE, bytes([command])
            )
            if data_size > 0:
                self._core.send(
                    DISPLAY_DATA,
                    CHIP_SELECT_UNTOUCHED,
                    bytes(data),
                )
            self._core.end_transaction()
            delay_time_ms = 0
            if delay:
                data_size += 1
                delay_time_ms = sequence[i + 1 + data_size]
                if delay_time_ms == 255:
                    delay_time_ms = 500
            time.sleep(delay_time_ms / 1000)
            if should_wait_for_busy:
                self._wait_for_busy()
            i += 2 + data_size
            if self._two_byte_sequence_length:
                i += 1

    def _start_refresh(self) -> None:
        # Run start sequence
        self._core._bus_reset()  # pylint: disable=protected-access
        time.sleep(self._start_up_time)
        self._send_command_sequence(True, self._start_sequence)
        self._core.start_refresh()

    def _finish_refresh(self) -> None:
        # Actually refresh the display now that all pixel RAM has been updated
        self._send_command_sequence(False, self._refresh_sequence)
        self._ticks_disabled = False
        self._refreshing = True
        self._core.finish_refresh()

    def _wait_for_busy(self) -> None:
        if self._busy is not None:
            while self._busy.value == self._busy_state:
                time.sleep(0.001)

    def _clean_area(self) -> bool:
        width = self._core.width
        height = self._core.height

        buffer = bytearray([0x77] * (width // 2))
        self._core.begin_transaction()
        self._core.send(
            DISPLAY_COMMAND, self._chip_select, bytes([self._write_black_ram_command])
        )
        self._core.end_transaction()
        for _ in range(height):
            if not self._core.begin_transaction():
                return False
            self._core.send(DISPLAY_DATA, self._chip_select, buffer)
            self._core.end_transaction()
        return True

    @property
    def rotation(self) -> int:
        """The rotation of the display as an int in degrees"""
        return self._core.rotation

    @rotation.setter
    def rotation(self, value: int) -> None:
        if value % 90 != 0:
            raise ValueError("Display rotation must be in 90 degree increments")
        transposed = self._core.rotation in (90, 270)
        will_transposed = value in (90, 270)
        if transposed != will_transposed:
            self._core.width, self._core.height = self._core.height, self._core.width
        self._core.set_rotation(value)
        if self._core.current_group is not None:
            self._core.current_group._update_transform(  # pylint: disable=protected-access
                self._core.transform
            )

    @property
    def time_to_refresh(self) -> float:
        """Time, in fractional seconds, until the ePaper display can be refreshed."""
        if self._core.last_refresh == 0:
            return 0

        # Refresh at seconds per frame rate
        elapsed_time = time.monotonic() * 1000 - self._core.last_refresh
        if elapsed_time > self._milliseconds_per_frame:
            return 0
        return self._milliseconds_per_frame - elapsed_time

    @property
    def busy(self) -> bool:
        """True when the display is refreshing. This uses the ``busy_pin`` when available or the
        ``refresh_time`` otherwise."""
        return self._refreshing

    @property
    def width(self) -> int:
        """Display Width"""
        return self._core.width

    @property
    def height(self) -> int:
        """Display Height"""
        return self._core.height

    @property
    def bus(self) -> _DisplayBus:
        """Current Display Bus"""
        return self._core.get_bus()

    @property
    def root_group(self) -> Group:
        """The root group on the epaper display.
        If the root group is set to ``None``, no output will be shown.
        """
        return self._core.current_group

    @root_group.setter
    def root_group(self, new_group: Group) -> None:
        self._set_root_group(new_group)
