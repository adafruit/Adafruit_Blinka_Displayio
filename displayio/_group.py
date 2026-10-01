# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.group`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from __future__ import annotations
from threading import RLock
from typing import Union, Callable
from circuitpython_typing import WriteableBuffer
from vectorio._rectangle import _VectorShape
from ._structs import TransformStruct
from ._tilegrid import TileGrid
from ._colorspace import Colorspace
from ._area import Area

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

# Held while removed areas move between a group's queue, its dirty area and its
# parent, so the background refresh and the app never see an area in neither place
_removed_lock = RLock()


class Group:
    # pylint: disable=too-many-instance-attributes
    """
    Manage a group of sprites and groups and how they are inter-related.

    Create a Group of a given scale. Scale is in one dimension. For example, scale=2
    leads to a layer's pixel being 2x2 pixels when in the group.
    """

    def __init__(self, *, scale: int = 1, x: int = 0, y: int = 0):
        """
        :param int scale: Scale of layer pixels in one dimension.
        :param int x: Initial x position within the parent.
        :param int y: Initial y position within the parent.
        """

        if not isinstance(scale, int) or scale < 1:
            raise ValueError("Scale must be >= 1")
        self._scale = 1  # Use the setter below to actually set the scale
        self._name = "Group"
        self._group_x = x
        self._group_y = y
        self._hidden_group = False
        self._hidden_by_parent = False
        self._layers = []
        self._supported_types = (TileGrid, Group, _VectorShape)
        self._in_group = False
        self._item_removed = False
        self._dirty_area = Area(0, 0, 0, 0)
        self._removed_areas = []
        self._absolute_transform = TransformStruct(0, 0, 1, 1, 1, False, False, False)
        self._set_scale(scale)  # Set the scale via the setter

    def _update_transform(self, parent_transform):
        """Update the parent transform and child transforms"""
        self._in_group = parent_transform is not None
        if self._in_group:
            x = self._group_x
            y = self._group_y
            if parent_transform.transpose_xy:
                x, y = y, x
            self._absolute_transform.x = int(
                parent_transform.x + parent_transform.dx * x
            )
            self._absolute_transform.y = int(
                parent_transform.y + parent_transform.dy * y
            )
            self._absolute_transform.dx = parent_transform.dx * self._scale
            self._absolute_transform.dy = parent_transform.dy * self._scale
            self._absolute_transform.transpose_xy = parent_transform.transpose_xy
            self._absolute_transform.mirror_x = parent_transform.mirror_x
            self._absolute_transform.mirror_y = parent_transform.mirror_y
            self._absolute_transform.scale = parent_transform.scale * self._scale
        self._update_child_transforms()

    def _update_child_transforms(self):
        # pylint: disable=protected-access
        if self._in_group:
            for layer in self._layers:
                layer._update_transform(self._absolute_transform)

    def _removal_cleanup(self, layer):
        # pylint: disable=protected-access
        with _removed_lock:
            self._queue_removed(layer)
        layer._update_transform(None)

    def _queue_removed(self, layer):
        # pylint: disable=protected-access
        # Queue the area the layer was last drawn in, so a refresh draws over it.
        # The layer is already out of the list, so no refresh can draw it again.
        layer_area = Area()
        if layer._get_previous_area(layer_area):
            self._removed_areas.append(layer_area)
            if len(self._removed_areas) > 8:
                # A group that is not being refreshed never drains its queue, so
                # merge it. Areas the refresh takes meanwhile are drawn by it.
                merged = Area(0, 0, 0, 0)
                self._pop_removed_areas_into(merged)
                self._removed_areas.append(merged)
        if isinstance(layer, Group):
            # A refresh will not finish this group now, so drop what it owes
            layer._item_removed = False
            layer._removed_areas.clear()

    def _pop_removed_areas_into(self, area: Area) -> None:
        """Union every queued removed area into area, emptying the queue."""
        while self._removed_areas:
            area.union(self._removed_areas.pop(0), area)

    def _consume_removed_areas(self) -> None:
        """Fold the queued areas of removed layers into the refresh-owned area."""
        with _removed_lock:
            if not self._item_removed:
                self._dirty_area.x2 = self._dirty_area.x1
            self._pop_removed_areas_into(self._dirty_area)
            self._item_removed = not self._dirty_area.empty()

    def _get_previous_area(self, area: Area) -> bool:
        """Copy the area last drawn into area. Returns False if nothing was drawn."""
        # pylint: disable=protected-access
        area.x2 = area.x1
        layer_area = Area()
        for layer in self._layers:
            if layer._get_previous_area(layer_area):
                area.union(layer_area, area)
        with _removed_lock:
            for removed_area in self._removed_areas:
                area.union(removed_area, area)
            if self._item_removed:
                area.union(self._dirty_area, area)
        return not area.empty()

    def _layer_update(self, index):
        # pylint: disable=protected-access
        layer = self._layers[index]
        layer._update_transform(self._absolute_transform)

    def append(self, layer: Union[Group, TileGrid, _VectorShape]) -> None:
        """Append a layer to the group. It will be drawn
        above other layers.
        """
        self.insert(len(self._layers), layer)

    def insert(self, index: int, layer: Union[Group, TileGrid, _VectorShape]) -> None:
        """Insert a layer into the group."""
        if not isinstance(layer, self._supported_types):
            raise ValueError("Invalid Group Member")
        if isinstance(layer, (Group, TileGrid)):
            if layer._in_group:  # pylint: disable=protected-access
                raise ValueError("Layer already in a group.")
        self._layers.insert(index, layer)
        self._layer_update(index)

    def index(self, layer: Union[Group, TileGrid, _VectorShape]) -> int:
        """Returns the index of the first copy of layer.
        Raises ValueError if not found.
        """
        return self._layers.index(layer)

    def pop(self, index: int = -1) -> Union[Group, TileGrid, _VectorShape]:
        """Remove the ith item and return it."""
        layer = self._layers.pop(index)
        self._removal_cleanup(layer)
        return layer

    def remove(self, layer: Union[Group, TileGrid, _VectorShape]) -> None:
        """Remove the first copy of layer. Raises ValueError
        if it is not present."""
        self._layers.pop(self.index(layer))
        self._removal_cleanup(layer)

    def __bool__(self) -> bool:
        """Returns if there are any layers"""
        return len(self._layers) > 0

    def __len__(self) -> int:
        """Returns the number of layers in a Group"""
        return len(self._layers)

    def __getitem__(self, index: int) -> Union[Group, TileGrid, _VectorShape]:
        """Returns the value at the given index."""
        return self._layers[index]

    def __setitem__(
        self, index: int, value: Union[Group, TileGrid, _VectorShape]
    ) -> None:
        """Sets the value at the given index."""
        # pylint: disable=protected-access
        if not isinstance(value, self._supported_types):
            raise ValueError("Invalid Group Member")
        if isinstance(value, (Group, TileGrid)) and value._in_group:
            raise ValueError("Layer already in a group.")
        old = self._layers[index]
        self._layers[index] = value
        self._removal_cleanup(old)
        self._layer_update(index)

    def __delitem__(self, index: int) -> None:
        """Deletes the value at the given index."""
        removed = self._layers[index]
        del self._layers[index]
        for layer in removed if isinstance(index, slice) else (removed,):
            self._removal_cleanup(layer)

    def _fill_area(
        self,
        colorspace: Colorspace,
        area: Area,
        mask: WriteableBuffer,
        buffer: WriteableBuffer,
    ) -> bool:
        if not self._hidden_group:
            for layer in reversed(self._layers):
                if isinstance(layer, (Group, TileGrid, _VectorShape)):
                    if layer._fill_area(  # pylint: disable=protected-access
                        colorspace, area, mask, buffer
                    ):
                        return True
        return False

    def sort(self, key: Callable, reverse: bool) -> None:
        """Sort the members of the group."""
        self._layers.sort(key=key, reverse=reverse)

    def _finish_refresh(self):
        self._item_removed = False
        for layer in reversed(self._layers):
            if isinstance(layer, (Group, TileGrid, _VectorShape)):
                layer._finish_refresh()  # pylint: disable=protected-access

    def _prepare_full_refresh(self):
        # A full refresh draws everything, so nothing removed is owed
        self._removed_areas.clear()
        for layer in reversed(self._layers):
            if isinstance(layer, (Group, TileGrid, _VectorShape)):
                layer._prepare_full_refresh()  # pylint: disable=protected-access

    def _get_refresh_areas(self, areas: list[Area]) -> None:
        # pylint: disable=protected-access
        self._consume_removed_areas()
        if self._item_removed:
            areas.append(self._dirty_area)
        for layer in reversed(self._layers):
            if isinstance(layer, (Group, _VectorShape)):
                layer._get_refresh_areas(areas)
            elif isinstance(layer, TileGrid):
                if not layer._get_rendered_hidden():
                    layer._get_refresh_areas(areas)

    def _set_hidden(self, hidden: bool) -> None:
        if self._hidden_group == hidden:
            return
        self._hidden_group = hidden
        if self._hidden_by_parent:
            return
        for layer in self._layers:
            if isinstance(layer, (Group, TileGrid)):
                layer._set_hidden_by_parent(hidden)  # pylint: disable=protected-access
            elif isinstance(layer, _VectorShape):
                layer._shape_set_dirty()  # pylint: disable=protected-access

    def _set_hidden_by_parent(self, hidden: bool) -> None:
        if self._hidden_by_parent == hidden:
            return
        self._hidden_by_parent = hidden
        if self._hidden_group:
            return
        for layer in self._layers:
            if isinstance(layer, (Group, TileGrid)):
                layer._set_hidden_by_parent(hidden)  # pylint: disable=protected-access
            elif isinstance(layer, _VectorShape):
                layer._shape_set_dirty()  # pylint: disable=protected-access

    @property
    def hidden(self) -> bool:
        """True when the Group and all of it's layers are not visible. When False, the
        Group’s layers are visible if they haven't been hidden.
        """
        return self._hidden_group

    @hidden.setter
    def hidden(self, value: bool) -> None:
        if not isinstance(value, (bool, int)):
            raise ValueError("Expecting a boolean or integer value")
        value = bool(value)
        self._set_hidden(value)

    @property
    def scale(self) -> int:
        """Scales each pixel within the Group in both directions. For example, when
        scale=2 each pixel will be represented by 2x2 pixels.
        """
        return self._scale

    @scale.setter
    def scale(self, value: int):
        self._set_scale(value)

    def _set_scale(self, value: int):
        # This is method allows the scale to be set by this class even when
        # the scale property is over-ridden by a subclass.
        if not isinstance(value, int) or value < 1:
            raise ValueError("Scale must be >= 1")
        if self._scale != value:
            parent_scale = self._absolute_transform.scale // self._scale
            self._absolute_transform.dx = (
                self._absolute_transform.dx // self._scale * value
            )
            self._absolute_transform.dy = (
                self._absolute_transform.dy // self._scale * value
            )
            self._absolute_transform.scale = parent_scale * value

            self._scale = value
            self._update_child_transforms()

    @property
    def x(self) -> int:
        """X position of the Group in the parent."""
        return self._group_x

    @x.setter
    def x(self, value: int):
        if not isinstance(value, int):
            raise ValueError("x must be an integer")
        if self._group_x != value:
            if self._absolute_transform.transpose_xy:
                dy_value = self._absolute_transform.dy // self._scale
                self._absolute_transform.y += dy_value * (value - self._group_x)
            else:
                dx_value = self._absolute_transform.dx // self._scale
                self._absolute_transform.x += dx_value * (value - self._group_x)
            self._group_x = value
            self._update_child_transforms()

    @property
    def y(self) -> int:
        """Y position of the Group in the parent."""
        return self._group_y

    @y.setter
    def y(self, value: int):
        if not isinstance(value, int):
            raise ValueError("y must be an integer")
        if self._group_y != value:
            if self._absolute_transform.transpose_xy:
                dx_value = self._absolute_transform.dx // self._scale
                self._absolute_transform.x += dx_value * (value - self._group_y)
            else:
                dy_value = self._absolute_transform.dy // self._scale
                self._absolute_transform.y += dy_value * (value - self._group_y)
            self._group_y = value
            self._update_child_transforms()


circuitpython_splash = Group(scale=2, x=0, y=0)
