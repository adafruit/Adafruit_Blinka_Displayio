# SPDX-FileCopyrightText: 2026 Bert Outtier
#
# SPDX-License-Identifier: MIT

"""
`framebufferio`
================================================================================

framebufferio for Blinka

The `framebufferio` module contains classes to manage display output
including synchronizing with refresh rates and partial updating.
It is used in conjunction with classes from `displayio` to actually
place items on the display; and classes like `linuxframebuffer.LinuxFramebuffer`
to actually drive the display.

**Framebuffer protocol**

On CircuitPython, framebuffers are native objects with a C protocol. In
Blinka, a framebuffer is any object with these methods, after that protocol:

* ``_get_bufinfo()``: a writable buffer holding the pixels, or `None` while
  the framebuffer is not available
* ``_swapbuffers(dirty_row_bitmask)``: called after each refresh that drew
  something, with a `bytearray` that has bit ``row % 8`` of byte ``row // 8``
  set for every row that changed
* ``_deinit()``: release the framebuffer
* ``_get_width()``, ``_get_height()``: the size in pixels

and optionally these, which default to the value in parentheses:

* ``_get_color_depth()`` (16)
* ``_get_bytes_per_cell()`` (2)
* ``_get_first_pixel_offset()`` (0): offset in bytes of the first pixel
* ``_get_row_stride()`` (0, meaning width * color_depth / 8): bytes per row
* ``_get_grayscale()`` (color_depth < 8)
* ``_get_native_frames_per_second()`` (60)
* ``_get_pixels_in_byte_share_row()`` (`False`)
* ``_get_reverse_pixels_in_byte()`` (`False`)
* ``_get_reverse_pixels_in_word()`` (`False`): 16 bit pixels are stored
  byte swapped, big endian on a little endian host
* ``_get_brightness()``, ``_set_brightness(value)`` (no brightness control)

and, specific to Blinka:

* ``_area_written(x1, y1, x2, y2)``: called for each area drawn into the
  pixels, before ``_swapbuffers()``, in framebuffer coordinates (``x2`` and
  ``y2`` excluded), so that a framebuffer that converts its pixels can
  convert only those areas instead of the whole dirty rows

16 bit pixels are RGB565 and 32 bit pixels 0x00RRGGBB, as native integers. Color depths below 8 bits
(pixels packed in bytes) are not supported yet.

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Bert Outtier

"""

# The refresh timing and the display properties are the same as BusDisplay's,
# as in CircuitPython
# pylint: disable=duplicate-code

import contextlib
import os
import sys
import threading
import time
from typing import Optional
from circuitpython_typing import WriteableBuffer
from displayio._displaycore import _DisplayCore
from displayio._group import Group, circuitpython_splash
from displayio._area import Area
from displayio._bitmap import _start_collection
from displayio._constants import NO_COMMAND

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


def _get(framebuffer, method: str, default):
    """Call an optional framebuffer protocol getter, or return its default."""
    getter = getattr(framebuffer, method, None)
    return default if getter is None else getter()


class FramebufferDisplay:
    # pylint: disable=too-many-instance-attributes
    """Manage updating a display with framebuffer in RAM

    This initializes a display and connects it into CircuitPython. Unlike other objects
    in CircuitPython, Display objects live until ``displayio.release_displays()`` is called.
    """

    def __init__(
        self,
        framebuffer,
        *,
        rotation: int = 0,
        auto_refresh: bool = True,
    ) -> None:
        """Create a Display object with the given framebuffer

        :param framebuffer: The framebuffer that the display is connected to, an
            object with the framebuffer protocol (see the module documentation),
            such as a `linuxframebuffer.LinuxFramebuffer`.
        :param bool auto_refresh: Automatically refresh the screen
        :param int rotation: The rotation of the display in degrees clockwise. Must be in
            90 degree increments (0, 90, 180, 270)
        """
        # pylint: disable=too-many-statements
        try:
            if rotation % 90 != 0:
                raise ValueError("Display rotation must be in 90 degree increments")

            # Turn off auto-refresh as we init
            self._auto_refresh = False
            # Taken while a frame is drawn and when the display is released, which
            # the refresh thread and the main thread may do at the same time
            self._lock = threading.RLock()
            self._pid = os.getpid()
            # Counts the root group changes, which a frame being drawn must notice
            self._root_changes = 0
            self._refresh_error = None
            self._framebuffer = framebuffer

            width = framebuffer._get_width()  # pylint: disable=protected-access
            height = framebuffer._get_height()  # pylint: disable=protected-access
            depth = _get(framebuffer, "_get_color_depth", 16)
            pixels_in_byte_share_row = _get(
                framebuffer, "_get_pixels_in_byte_share_row", False
            )
            if depth < 8:
                # Pixels packed in bytes, by rows or by columns, are not copied
                # into the framebuffer correctly yet
                raise ValueError("Color depths below 8 bits are not supported")
            self._core = _DisplayCore(
                bus=None,
                width=width,
                height=height,
                ram_width=width,
                ram_height=height,
                colstart=0,
                rowstart=0,
                rotation=0,
                color_depth=depth,
                grayscale=_get(framebuffer, "_get_grayscale", depth < 8),
                pixels_in_byte_share_row=pixels_in_byte_share_row,
                bytes_per_cell=_get(framebuffer, "_get_bytes_per_cell", 2),
                reverse_pixels_in_byte=_get(
                    framebuffer, "_get_reverse_pixels_in_byte", False
                ),
                reverse_bytes_in_word=_get(
                    framebuffer, "_get_reverse_pixels_in_word", False
                ),
                column_command=NO_COMMAND,
                row_command=NO_COMMAND,
                set_current_column_command=NO_COMMAND,
                set_current_row_command=NO_COMMAND,
                data_as_commands=False,
                always_toggle_chip_select=False,
                sh1107_addressing=False,
                address_little_endian=False,
            )

            self._first_pixel_offset = _get(framebuffer, "_get_first_pixel_offset", 0)
            self._row_stride = _get(framebuffer, "_get_row_stride", 0)
            if self._row_stride == 0:
                self._row_stride = width * depth // 8
            if self._row_stride < width * depth // 8:
                raise ValueError("The row stride is shorter than a row")

            self._bufinfo = None
            self._get_bufinfo()
            framebuffer_size = (
                self._first_pixel_offset
                + self._row_stride * (height - 1)
                + width * depth // 8
            )
            if self._bufinfo is None or len(self._bufinfo) < framebuffer_size:
                raise ValueError("framebuffer is too small")

            self._first_manual_refresh = not auto_refresh

            self._native_frames_per_second = _get(
                framebuffer, "_get_native_frames_per_second", 60
            )
            self._native_ms_per_frame = 1000 // self._native_frames_per_second
            self._last_refresh_call = 0

            if rotation != 0:
                self.rotation = rotation

            if not circuitpython_splash._in_group:  # pylint: disable=protected-access
                self._set_root_group(circuitpython_splash)
            self.auto_refresh = auto_refresh
        except BaseException:
            # __new__ allocated the display: give the slot back
            from displayio import (  # pylint: disable=import-outside-toplevel, cyclic-import
                displays,
            )

            if self in displays:
                displays.remove(self)
            raise

    def __new__(cls, *args, **kwargs):
        from displayio import (  # pylint: disable=import-outside-toplevel, cyclic-import
            allocate_display,
        )

        display_instance = super().__new__(cls)
        allocate_display(display_instance)
        return display_instance

    def _get_bufinfo(self) -> Optional[memoryview]:
        """The pixels of the framebuffer as bytes, None while it is not available"""
        buffer = self._framebuffer._get_bufinfo()  # pylint: disable=protected-access
        if buffer is None:
            self._release_bufinfo()
            return None
        if self._bufinfo is None or self._bufinfo.obj is not buffer:
            self._release_bufinfo()
            self._bufinfo = memoryview(buffer).cast("B")
        return self._bufinfo

    def _release_bufinfo(self) -> None:
        if self._bufinfo is not None:
            self._bufinfo.release()
            self._bufinfo = None

    @staticmethod
    def show(_group: Group) -> None:  # pylint: disable=missing-function-docstring
        raise AttributeError(".show(x) removed. Use .root_group = x")

    def _set_root_group(self, root_group: Group) -> None:
        if root_group is not self._core.current_group:
            self._root_changes += 1
        ok = self._core.set_root_group(root_group)
        if not ok:
            raise ValueError("Group already used")

    def _locked(self):
        """The lock of the display, but not in a child forked from the process
        that created it: the child inherits the lock as it was at the fork, maybe
        held by a refresh that will not finish in the child"""
        if os.getpid() != self._pid:
            return contextlib.nullcontext()
        return self._lock

    def refresh(
        self,
        *,
        target_frames_per_second: Optional[int] = None,
        minimum_frames_per_second: int = 0,
    ) -> bool:
        """When auto_refresh is off, and :py:attr:`target_frames_per_second` is not `None` this
        waits for the target frame rate and then refreshes the display, returning `True`. If the
        call has taken too long since the last refresh call for the given target frame rate,
        then the refresh returns `False` immediately without updating the screen to hopefully
        help getting caught up.

        If the time since the last successful refresh is below the minimum frame rate, then an
        exception will be raised. The default :py:attr:`minimum_frames_per_second` of 0
        disables this behavior.

        When auto_refresh is off, and :py:attr:`target_frames_per_second` is `None` this
        will update the display immediately.

        When auto_refresh is on, updates the display immediately. (The display will also update
        without calls to this.)

        :param Optional[int] target_frames_per_second: The target frame rate that
            :py:func:`refresh` should try to achieve. Set to `None` for immediate refresh.
        :param int minimum_frames_per_second: The minimum number of times the screen should be
            updated per second.
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

    def _refresh_display(self) -> None:
        with self._locked():
            self._refresh_display_locked()

    def _refresh_display_locked(self) -> None:
        if self._get_bufinfo() is None:
            return
        if not self._core.start_refresh():
            return

        root_changes = self._root_changes
        try:
            areas_to_refresh = self._get_refresh_areas()
            if areas_to_refresh:
                transposed = self._core.rotation in (90, 270)
                row_count = self._core.width if transposed else self._core.height
                dirty_row_bitmask = bytearray((row_count + 7) // 8)
                for area in areas_to_refresh:
                    self._refresh_area(area, dirty_row_bitmask)
                self._framebuffer._swapbuffers(  # pylint: disable=protected-access
                    dirty_row_bitmask
                )
        except BaseException:
            # Redraw everything at the next refresh, which may be a retry
            self._core.full_refresh = True
            self._core.refresh_in_progress = False
            raise

        self._core.finish_refresh()
        if self._root_changes != root_changes:
            # The root group changed during this frame: its full refresh, which
            # finish_refresh() cleared, is still to come
            self._core.full_refresh = True

    def _get_refresh_areas(self) -> list[Area]:
        """Get a list of areas to be refreshed"""
        areas = []
        _start_collection()
        if self._core.full_refresh:
            if self._core.current_group is not None:
                self._core.current_group._prepare_full_refresh()  # pylint: disable=protected-access
            areas.append(self._core.area)
        elif self._core.current_group is not None:
            self._core.current_group._get_refresh_areas(  # pylint: disable=protected-access
                areas
            )
        return areas

    def _refresh_area(self, area: Area, dirty_row_bitmask: bytearray) -> None:
        """Draw an area into the framebuffer and mark its rows dirty."""
        # pylint: disable=too-many-locals
        clipped = Area()
        # Clip the area to the display by overlapping the areas.
        # If there is no overlap then we're done.
        if not self._core.clip_area(area, clipped):
            return

        depth = self._core.colorspace.depth
        # If pixels are packed by row then rows are on byte boundaries
        if depth < 8 and self._core.colorspace.pixels_in_byte_share_row:
            div = 8 // depth
            clipped.x1 = (clipped.x1 // div) * div
            clipped.x2 = ((clipped.x2 + div - 1) // div) * div

        # We should have lots of memory, so take the whole area in one pass
        pixels_per_word = 32 // depth
        buffer_size = (clipped.size() + pixels_per_word - 1) // pixels_per_word
        mask_length = (clipped.size() // 32) + 1
        buffer = memoryview(bytearray(buffer_size * 4)).cast("I")
        mask = memoryview(bytearray(mask_length * 4)).cast("I")
        self._core.fill_area(clipped, mask, buffer)

        source = buffer.cast("B")
        destination = self._bufinfo
        row_size = clipped.width() * depth // 8
        offset = (
            self._first_pixel_offset
            + clipped.y1 * self._row_stride
            + clipped.x1 * depth // 8
        )
        start = 0
        for row in range(clipped.y1, clipped.y2):
            destination[offset : offset + row_size] = source[start : start + row_size]
            dirty_row_bitmask[row // 8] |= 1 << (row & 7)
            offset += self._row_stride
            start += row_size

        area_written = getattr(self._framebuffer, "_area_written", None)
        if area_written is not None:
            area_written(clipped.x1, clipped.y1, clipped.x2, clipped.y2)

    def fill_row(self, y: int, buffer: WriteableBuffer) -> WriteableBuffer:
        """Extract the pixels from a single row

        :param int y: The top edge of the area
        :param ~circuitpython_typing.WriteableBuffer buffer: The buffer in which to place
            the pixel data
        """
        if self._core.colorspace.depth != 16:
            raise ValueError("Display must have a 16 bit colorspace.")

        area = Area(0, y, self._core.width, y + 1)
        pixels_per_word = 32 // self._core.colorspace.depth
        buffer_size = self._core.width // pixels_per_word
        pixels_per_buffer = area.size()
        if pixels_per_buffer % pixels_per_word:
            buffer_size += 1

        result = memoryview(buffer).cast("B")
        if len(result) < buffer_size * 4:
            raise ValueError("Buffer too small")
        mask_length = (pixels_per_buffer // 32) + 1
        mask = memoryview(bytearray(mask_length * 4)).cast("I")
        self._core.fill_area(area, mask, result[: buffer_size * 4].cast("I"))
        return buffer

    def _background(self) -> None:
        """Run background refresh tasks. Do not call directly"""
        if (
            self._auto_refresh
            and (time.monotonic() * 1000 - self._core.last_refresh)
            > self._native_ms_per_frame
        ):
            try:
                self.refresh()
            except Exception as error:  # pylint: disable=broad-exception-caught
                # The display thread refreshes every display: keep it running. The
                # failed refresh left a full refresh pending for the next tick.
                message = f"{type(error).__name__}: {error}"
                if message != self._refresh_error:
                    print(f"Display refresh failed: {message}", file=sys.stderr)
                self._refresh_error = message
            else:
                self._refresh_error = None

    def _release(self) -> None:
        """Release the display and free its resources"""
        with self._locked():
            self.auto_refresh = False
            self._core.release_display_core()
            self._release_bufinfo()
            self._framebuffer._deinit()  # pylint: disable=protected-access

    def _reset(self) -> None:
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
        """The brightness of the display as a float. 0.0 is off and 1.0 is full brightness."""
        getter = getattr(self._framebuffer, "_get_brightness", None)
        brightness = -1 if getter is None else getter()
        if brightness < 0:
            raise RuntimeError("Brightness not adjustable")
        return brightness

    @brightness.setter
    def brightness(self, value: float):
        value = float(value)
        if not 0.0 <= value <= 1.0:
            raise ValueError("brightness must be 0-1")
        setter = getattr(self._framebuffer, "_set_brightness", None)
        if setter is None:
            raise RuntimeError("Brightness not adjustable")
        setter(value)

    @property
    def width(self) -> int:
        """Gets the width of the framebuffer"""
        return self._core.get_width()

    @property
    def height(self) -> int:
        """Gets the height of the framebuffer"""
        return self._core.get_height()

    @property
    def rotation(self) -> int:
        """The rotation of the display as an int in degrees."""
        return self._core.get_rotation()

    @rotation.setter
    def rotation(self, value: int):
        if value % 90 != 0:
            raise ValueError("Display rotation must be in 90 degree increments")
        value %= 360
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
    def framebuffer(self):
        """The framebuffer being used by the display"""
        return self._framebuffer

    @property
    def root_group(self) -> Group:
        """The root group on the display.
        If the root group is set to `displayio.CIRCUITPYTHON_TERMINAL`, the default
        CircuitPython terminal will be shown.
        If the root group is set to ``None``, no output will be shown.
        """
        return self._core.current_group

    @root_group.setter
    def root_group(self, new_group: Group) -> None:
        self._set_root_group(new_group)
