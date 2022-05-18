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


from typing import Union
import circuitpython_typing
from paralleldisplay import ParallelBus
from ._fourwire import FourWire
from ._group import Group
from ._i2cdisplay import I2CDisplay
from ._structs import ColorspaceStruct, TransformStruct, RectangleStruct
from ._area import Area

displays = []


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
        reverse_bytes_in_word: bool,
    ):
        self._colorspace = ColorspaceStruct(
            depth=color_depth,
            grayscale=grayscale,
            grayscale_bit=8 - color_depth,
            pixels_in_byte_share_row=pixels_in_byte_share_row,
            bytes_per_cell=bytes_per_cell,
            reverse_pixels_in_byte=reverse_pixels_in_byte,
            reverse_bytes_in_word=reverse_bytes_in_word,
            dither=False,
        )
        self._current_group = None
        self._colstart = colstart
        self._rowstart = rowstart
        self._last_refresh = 0
        self._refresh_in_progress = False
        self._full_refresh = False

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
        # pylint: disable=protected-access, too-many-branches
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

    def start_refresh(self) -> bool:
        # pylint: disable=protected-access
        """Mark the display core as currently being refreshed"""

        if self._refresh_in_progress:
            return False

        self._refresh_in_progress = True
        # self._last_refresh = _Supervisor()._ticks_ms64()
        return True

    def finish_refresh(self) -> None:
        # pylint: disable=protected-access
        """Unmark the display core as currently being refreshed"""

        if self._current_group is not None:
            self._current_group._finish_refresh()

        self._full_refresh = False
        self._refresh_in_progress = False
        # self._last_refresh = _Supervisor()._ticks_ms64()

    def get_refresh_areas(self) -> list:
        """Get a list of areas to be refreshed"""
        subrectangles = []
        if self._current_group is not None:
            # Eventually calculate dirty rectangles here
            subrectangles.append(RectangleStruct(0, 0, self._width, self._height))
        return subrectangles

    def release(self) -> None:
        """Release the display from the current group"""
        # pylint: disable=protected-access

        if self._current_group is not None:
            self._current_group._in_group = False

    def fill_area(
        self,
        area: Area,
        mask: circuitpython_typing.WriteableBuffer,
        buffer: circuitpython_typing.WriteableBuffer,
    ) -> bool:
        # pylint: disable=protected-access
        """Call the current group's fill area function"""

        return self._current_group._fill_area(self._colorspace, area, mask, buffer)

    def clip_area(self, area: Area, clipped: Area) -> bool:
        """Shrink the area to the region shared by the two areas"""
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

    def get_bus(self) -> Union[FourWire, ParallelBus, I2CDisplay]:
        """
        The bus being used by the display. [readonly]
        """
        return self._bus
