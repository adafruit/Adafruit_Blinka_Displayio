# SPDX-FileCopyrightText: 2021 Melissa LeBlanc-Williams for Adafruit Industries
# SPDX-FileCopyrightText: 2021 James Carr
#
# SPDX-License-Identifier: MIT

"""
`displayio._displaycore`
================================================================================

Super class of the display classes

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): James Carr, Melissa LeBlanc-Williams

"""

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_Displayio.git"


from typing import Optional, Union
import _typing
from ._fourwire import FourWire
from ._group import Group
from ._i2cdisplay import I2CDisplay
from ._structs import ColorspaceStruct, TransformStruct, RectangleStruct
from ._area import Area

from paralleldisplay import ParallelBus
from ._constants import (
    DISPLAY_COMMAND,
    DISPLAY_DATA,
    CHIP_SELECT_TOGGLE_EVERY_BYTE,
    CHIP_SELECT_UNTOUCHED,
)

displays = []

# Functions
#* construct
#  show
#  set_dither
#^ bus_reset
#  set_region_to_update
#* release
#  fill_area
#  clip_area (_clip)

class _DisplayCore:
    # pylint: disable=too-many-arguments, too-many-instance-attributes

    def __init__(
        self,
        bus,
        width: int,
        height: int,
        ram_width: int,
        ram_height: int,
        colstart: int,
        rowstart: int,
        rotation: int,
        color_depth: int,
        grayscale: bool,
        pixels_in_byte_share_row: bool,
        bytes_per_cell: int,
        reverse_pixels_in_byte: bool,
        reverse_bytes_in_word: bool
    ):
        self._colorspace = ColorspaceStruct(
            depth = color_depth,
            grayscale = grayscale,
            grayscale_bit = 8 - color_depth,
            pixels_in_byte_share_row = pixels_in_byte_share_row,
            bytes_per_cell = bytes_per_cell,
            reverse_pixels_in_byte = reverse_pixels_in_byte,
            reverse_bytes_in_word = reverse_bytes_in_word,
            dither = False
        )
        self._current_group = None
        self._colstart = colstart
        self._rowstart = rowstart
        self._last_refresh = 0
        self._refresh_in_progress = False

        if bus:
            if isinstance(bus, (FourWire, I2CDisplay, ParallelBus)):
                self._bus_reset = bus.reset
                self._begin_transaction = bus._begin_transaction
                self._send = bus._send
                self._end_transaction = bus._end_transaction
            else:
                raise ValueError("Unsupported display bus type")

        self._bus = bus
        self._area = Area(0, 0, width, height)

        self._width = width
        self._height = height
        self._ram_width = ram_width
        self._ram_height = ram_height
        self._rotation = rotation
        self._transform = TransformStruct()

    def set_rotation(self, rotation: int) -> None:
        """
        Sets the rotation of the display as an int in degrees.
        """
        # pylint: disable=protected-access
        transposed = self._rotation in (90, 270)
        will_be_transposed = rotation in (90, 270)
        if transposed != will_be_transposed:
            self._width, self._height = self._height, self._width

        height = self._height
        width = self._width

        rotation %= 360
        self._rotation = rotation
        self._transform.x = 0
        self._transform.y = 0
        self._transform.scale = 1
        self._transform.mirror_x = False
        self._transform.mirror_y = False
        self._transform.transpose_xy = False

        if rotation in (0, 180):
            if rotation == 180:
                self._transform.mirror_x = True
                self._transform.mirror_y = True
        else:
            self._transform.transpose_xy = True
            if rotation == 270:
                self._transform.mirror_y = True
            else:
                self._transform.mirror_x = True

        self._area.x1 = 0
        self._area.y1 = 0
        self._area.next = None

        self._transform.dx = 1
        self._transform.dy = 1
        if self._transform.transpose_xy:
            self._area.x2 = height
            self._area.y2 = width
            if self._transform.mirror_x:
                self._transform.x = height
                self._transform.dx = -1
            if self._transform.mirror_y:
                self._transform.y = width
                self._transform.dy = -1
        else:
            self._area.x2 = width
            self._area.y2 = height
            if self._transform.mirror_x:
                self._transform.x = width
                self._transform.dx = -1
            if self._transform.mirror_y:
                self._transform.y = height
                self._transform.dy = -1

        if self._current_group is not None:
            self._current_group._update_transform(self._transform)

    def show(self, root_group: Group) -> bool:
        # pylint: disable=protected-access

        """
        Switches to displaying the given group of layers. When group is `None`, the
        default CircuitPython terminal will be shown.

        :param Optional[displayio.Group] root_group: The group to show.
        """

        """
        # TODO: Implement Supervisor
        if root_group is None:
            circuitpython_splash = _Supervisor().circuitpython_splash
            if not circuitpython_splash._in_group:
                root_group = circuitpython_splash
            elif self._current_group == circuitpython_splash:
                return True
        """

        if root_group == self._current_group:
            return True

        if root_group is not None and root_group._in_group:
            return False

        if self._current_group is not None:
            self._current_group._in_group = False

        if root_group is not None:
            root_group._update_transform(self._transform)
            root_group._in_group = True

        self._current_group = root_group
        self._full_refresh = True

        return True

    def set_region_to_update(
        self,
        column_command: int,
        row_command: int,
        set_current_column_command: Optional[int],
        set_current_row_command: Optional[int],
        data_as_commands: bool,
        always_toggle_chip_select: bool,
        area: Area,
        SH1107_addressing: bool,
    ) -> None:
        # pylint: disable=invalid-name, too-many-arguments, too-many-locals, too-many-branches,
        # pylint: disable=too-many-statements

        big_endian = True  # default is True # TODO ????

        x1 = area.x1 + self._colstart
        x2 = area.x2 + self._colstart
        y1 = area.y1 + self._rowstart
        y2 = area.y2 + self._rowstart

        # Collapse down the dimension where multiple pixels are in a byte.
        if self._colorspace.depth < 8:
            pixels_per_byte = 8 // self._colorspace.depth
            if self._colorspace.pixels_in_byte_share_row:
                x1 //= pixels_per_byte * self._colorspace.bytes_per_cell
                x2 //= pixels_per_byte * self._colorspace.bytes_per_cell
            else:
                y1 //= pixels_per_byte * self._colorspace.bytes_per_cell
                y2 //= pixels_per_byte * self._colorspace.bytes_per_cell

        x2 -= 1
        y2 -= 1

        chip_select = CHIP_SELECT_UNTOUCHED
        if always_toggle_chip_select or data_as_commands:
            chip_select = CHIP_SELECT_TOGGLE_EVERY_BYTE

        # Set column
        self._begin_transaction()
        data = bytearray(5)
        data[0] = column_command
        if not data_as_commands:
            self._send(DISPLAY_COMMAND, CHIP_SELECT_UNTOUCHED, data, 1)
            data_type = DISPLAY_DATA
            data_length = 0
        else:
            data_type = DISPLAY_COMMAND
            data_length = 1

        if self._ram_width < 0x100:
            data[data_length] = x1
            data_length += 1
            data[data_length] = x2
            data_length += 1
        else:
            if big_endian:
                data[data_length] = x1 >> 8
                data_length += 1
                data[data_length] = x1 & 0xFF
                data_length += 1
                data[data_length] = x2 >> 8
                data_length += 1
                data[data_length] = x2 & 0xFF
                data_length += 1
            else:
                data[data_length] = x1 & 0xFF
                data_length += 1
                data[data_length] = x1 >> 8
                data_length += 1
                data[data_length] = x2 & 0xFF
                data_length += 1
                data[data_length] = x2 >> 8
                data_length += 1

        # Quirk for "SH1107_addressing"
        #     Column lower command = 0x00, Column upper command = 0x10
        if SH1107_addressing:
            data[0] = ((x1 >> 4) & 0x0F) | 0x10  # 0x10 to 0x17
            data[1] = x1 & 0x0F  # 0x00 to 0x0F
            data_length = 2

        self._send(data_type, chip_select, data, data_length)
        self._end_transaction()

        if set_current_column_command is not None:
            command = bytearray(1)
            command[0] = set_current_column_command
            self._begin_transaction()
            self._send(DISPLAY_COMMAND, chip_select, command, 1)
            self._send(DISPLAY_DATA, chip_select, data, data_length // 2)
            self._end_transaction()

        # Set row
        self._begin_transaction()
        data[0] = row_command
        data_length = 1
        if not data_as_commands:
            self._send(DISPLAY_COMMAND, CHIP_SELECT_UNTOUCHED, data, 1)
            data_length = 0

        if self._ram_height < 0x100:
            data[data_length] = y1
            data_length += 1
            data[data_length] = y2
            data_length += 1
        else:
            if big_endian:
                data[data_length] = y1 >> 8
                data_length += 1
                data[data_length] = y1 & 0xFF
                data_length += 1
                data[data_length] = y2 >> 8
                data_length += 1
                data[data_length] = y2 & 0xFF
                data_length += 1
                # TODO Which is right? The core uses above
            else:
                data[data_length] = y1 & 0xFF
                data_length += 1
                data[data_length] = y1 >> 8
                data_length += 1
                data[data_length] = y2 & 0xFF
                data_length += 1
                data[data_length] = y2 >> 8
                data_length += 1

        # Quirk for "SH1107_addressing"
        #  Page address command = 0xB0
        if SH1107_addressing:
            # Set the page to out y value
            data[0] = 0xB0 | y1
            data_length = 1

        self._send(data_type, chip_select, data, data_length)
        self._end_transaction()

        if set_current_row_command is not None:
            command = bytearray(1)
            command[0] = set_current_row_command
            self._begin_transaction()
            self._send(DISPLAY_COMMAND, chip_select, command, 1)
            self._send(DISPLAY_DATA, chip_select, data, data_length // 2)
            self._end_transaction()

    def start_refresh(self) -> bool:
        # pylint: disable=protected-access

        if self._refresh_in_progress:
            return False

        self._refresh_in_progress = True
        #self._last_refresh = _Supervisor()._ticks_ms64()
        return True

    def finish_refresh(self) -> None:
        # pylint: disable=protected-access

        if self._current_group is not None:
            self._current_group._finish_refresh()

        self._full_refresh = False
        self._refresh_in_progress = False
        #self._last_refresh = _Supervisor()._ticks_ms64()

    def get_refresh_areas(self):
        subrectangles = []
        if self._current_group is not None:
            # Eventually calculate dirty rectangles here
            subrectangles.append(RectangleStruct(0, 0, self._width, self._height))
        return subrectangles

    def release(self) -> None:
        # pylint: disable=protected-access

        if self._current_group is not None:
            self._current_group._in_group = False

    def fill_area(
        self, area: Area, mask: _typing.WriteableBuffer, buffer: _typing.WriteableBuffer
    ) -> bool:
        # pylint: disable=protected-access

        return self._current_group._fill_area(self._colorspace, area, mask, buffer)

    def clip_area(self, area: Area, clipped: Area) -> bool:
        # pylint: disable=protected-access

        overlaps = self._area._compute_overlap(area, clipped)
        if not overlaps:
            return False

        # Expand the area if we have multiple pixels per byte and we need to byte align the bounds
        if self._colorspace.depth < 8:
            pixels_per_byte = (
                8 // self._colorspace.depth * self._colorspace.bytes_per_cell
            )
            if self._colorspace.pixels_in_byte_share_row:
                if clipped.x1 % pixels_per_byte != 0:
                    clipped.x1 -= clipped.x1 % pixels_per_byte
                if clipped.x2 % pixels_per_byte != 0:
                    clipped.x2 += pixels_per_byte - clipped.x2 % pixels_per_byte
            else:
                if clipped.y1 % pixels_per_byte != 0:
                    clipped.y1 -= clipped.y1 % pixels_per_byte
                if clipped.y2 % pixels_per_byte != 0:
                    clipped.y2 += pixels_per_byte - clipped.y2 % pixels_per_byte

        return True

    def send(self, data_type: int, chip_select: int, data: _typing.ReadableBuffer) -> None:
        """
        Send the data to the current bus
        """
        self._send(data_type, chip_select, data)

    def begin_transaction(self) -> None:
        """
        Begin Bus Transaction
        """
        self._begin_transaction()

    def end_transaction(self) -> None:
        """
        End Bus Transaction
        """
        self._end_transaction()

    def get_width(self) -> int:
        """
        Gets the width of the display in pixels.
        """
        return self._width

    def get_height(self) -> int:
        """
        Gets the height of the display in pixels.
        """
        return self._height

    def get_rotation(self) -> int:
        """
        Gets the rotation of the display as an int in degrees.
        """
        return self._rotation
            
    def get_bus(self) -> Union[FourWire,ParallelBus,I2CDisplay]:
        """
        The bus being used by the display. [readonly]
        """
        return self._bus