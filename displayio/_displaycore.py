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

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_Displayio.git"


import time
import circuitpython_typing
from paralleldisplay import ParallelBus
from ._fourwire import FourWire
from ._group import Group
from ._i2cdisplay import I2CDisplay
from ._structs import ColorspaceStruct, TransformStruct, RectangleStruct
from ._area import Area
from ._displaybus import _DisplayBus


class _DisplayCore:
    # pylint: disable=too-many-arguments, too-many-instance-attributes, too-many-locals

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
        reverse_bytes_in_word: bool,
        column_command: int,
        row_command: int,
        set_current_column_command: int,
        set_current_row_command: int,
        data_as_commands: bool,
        always_toggle_chip_select: bool,
        sh1107_addressing: bool,
        address_little_endian: bool,
    ):
        self.colorspace = ColorspaceStruct(
            depth=color_depth,
            grayscale=grayscale,
            grayscale_bit=8 - color_depth,
            pixels_in_byte_share_row=pixels_in_byte_share_row,
            bytes_per_cell=bytes_per_cell,
            reverse_pixels_in_byte=reverse_pixels_in_byte,
            reverse_bytes_in_word=reverse_bytes_in_word,
            dither=False,
        )
        self.current_group = None
        self.colstart = colstart
        self.rowstart = rowstart
        self.last_refresh = 0

        self.column_command = column_command
        self.row_command = row_command
        self.set_current_column_command = set_current_column_command
        self.set_current_row_command = set_current_row_command
        self.data_as_commands = data_as_commands
        self.always_toggle_chip_select = always_toggle_chip_select
        self.sh1107_addressing = sh1107_addressing
        self.address_little_endian = address_little_endian

        self.refresh_in_progress = False
        self.full_refresh = False
        self.last_refresh = 0

        if bus:
            if isinstance(bus, (FourWire, I2CDisplay, ParallelBus)):
                self._bus_reset = bus.reset
                self._begin_transaction = bus._begin_transaction
                self._send = bus._send
                self._end_transaction = bus._end_transaction
            else:
                raise ValueError("Unsupported display bus type")

        self._bus = bus
        self.area = Area(0, 0, width, height)

        self.width = width
        self.height = height
        self.ram_width = ram_width
        self.ram_height = ram_height
        self.rotation = rotation
        self.transform = TransformStruct()

    def set_rotation(self, rotation: int) -> None:
        """
        Sets the rotation of the display as an int in degrees.
        """
        # pylint: disable=protected-access, too-many-branches
        transposed = self.rotation in (90, 270)
        will_be_transposed = rotation in (90, 270)
        if transposed != will_be_transposed:
            self.width, self.height = self.height, self.width

        height = self.height
        width = self.width

        rotation %= 360
        self.rotation = rotation
        self.transform.x = 0
        self.transform.y = 0
        self.transform.scale = 1
        self.transform.mirror_x = False
        self.transform.mirror_y = False
        self.transform.transpose_xy = False

        if rotation in (0, 180):
            if rotation == 180:
                self.transform.mirror_x = True
                self.transform.mirror_y = True
        else:
            self.transform.transpose_xy = True
            if rotation == 270:
                self.transform.mirror_y = True
            else:
                self.transform.mirror_x = True

        self.area.x1 = 0
        self.area.y1 = 0
        self.area.next = None

        self.transform.dx = 1
        self.transform.dy = 1
        if self.transform.transpose_xy:
            self.area.x2 = height
            self.area.y2 = width
            if self.transform.mirror_x:
                self.transform.x = height
                self.transform.dx = -1
            if self.transform.mirror_y:
                self.transform.y = width
                self.transform.dy = -1
        else:
            self.area.x2 = width
            self.area.y2 = height
            if self.transform.mirror_x:
                self.transform.x = width
                self.transform.dx = -1
            if self.transform.mirror_y:
                self.transform.y = height
                self.transform.dy = -1

        if self.current_group is not None:
            self.current_group._update_transform(self.transform)

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
            elif self.current_group == circuitpython_splash:
                return True
        """

        if root_group == self.current_group:
            return True

        if root_group is not None and root_group._in_group:
            return False

        if self.current_group is not None:
            self.current_group._in_group = False

        if root_group is not None:
            root_group._update_transform(self.transform)
            root_group._in_group = True

        self.current_group = root_group
        self.full_refresh = True

        return True

    def start_refresh(self) -> bool:
        # pylint: disable=protected-access
        """Mark the display core as currently being refreshed"""

        if self.refresh_in_progress:
            return False

        self.refresh_in_progress = True
        self.last_refresh = time.monotonic() * 1000
        return True

    def finish_refresh(self) -> None:
        # pylint: disable=protected-access
        """Unmark the display core as currently being refreshed"""

        if self.current_group is not None:
            self.current_group._finish_refresh()

        self.full_refresh = False
        self.refresh_in_progress = False
        self.last_refresh = time.monotonic() * 1000

    def get_refresh_areas(self) -> list:
        """Get a list of areas to be refreshed"""
        subrectangles = []
        if self.current_group is not None:
            # Eventually calculate dirty rectangles here
            subrectangles.append(RectangleStruct(0, 0, self.width, self.height))
        return subrectangles

    def release(self) -> None:
        """Release the display from the current group"""
        # pylint: disable=protected-access

        if self.current_group is not None:
            self.current_group._in_group = False

    def fill_area(
        self,
        area: Area,
        mask: circuitpython_typing.WriteableBuffer,
        buffer: circuitpython_typing.WriteableBuffer,
    ) -> bool:
        # pylint: disable=protected-access
        """Call the current group's fill area function"""

        return self.current_group._fill_area(self.colorspace, area, mask, buffer)

    def clip_area(self, area: Area, clipped: Area) -> bool:
        """Shrink the area to the region shared by the two areas"""
        # pylint: disable=protected-access

        overlaps = self.area._compute_overlap(area, clipped)
        if not overlaps:
            return False

        # Expand the area if we have multiple pixels per byte and we need to byte align the bounds
        if self.colorspace.depth < 8:
            pixels_per_byte = (
                8 // self.colorspace.depth * self.colorspace.bytes_per_cell
            )
            if self.colorspace.pixels_in_byte_share_row:
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

    def send(
        self,
        data_type: int,
        chip_select: int,
        data: circuitpython_typing.ReadableBuffer,
    ) -> None:
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
        return self.width

    def get_height(self) -> int:
        """
        Gets the height of the display in pixels.
        """
        return self.height

    def get_rotation(self) -> int:
        """
        Gets the rotation of the display as an int in degrees.
        """
        return self.rotation

    def get_bus(self) -> _DisplayBus:
        """
        The bus being used by the display. [readonly]
        """
        return self._bus
