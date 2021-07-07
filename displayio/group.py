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

from recordclass import recordclass
from displayio.tilegrid import TileGrid

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


Transform = recordclass("Transform", "x y dx dy scale transpose_xy mirror_x mirror_y")


class Group:
    """Manage a group of sprites and groups and how they are inter-related."""

    def __init__(self, *, max_size=4, scale=1, x=0, y=0):
        """Create a Group of a given size and scale. Scale is in
        one dimension. For example, scale=2 leads to a layer’s
        pixel being 2x2 pixels when in the group.
        """
        if not isinstance(max_size, int) or max_size < 1:
            raise ValueError("Max Size must be >= 1")
        self._max_size = max_size
        if not isinstance(scale, int) or scale < 1:
            raise ValueError("Scale must be >= 1")
        self._scale = 1  # Use the setter below to actually set the scale
        self._group_x = x
        self._group_y = y
        self._hidden_group = False
        self._layers = []
        self._supported_types = (TileGrid, Group)
        self.in_group = False
        self._absolute_transform = Transform(0, 0, 1, 1, 1, False, False, False)
        self._set_scale(scale)  # Set the scale via the setter

    def update_transform(self, parent_transform):
        """Update the parent transform and child transforms"""
        self.in_group = parent_transform is not None
        if self.in_group:
            x = self._group_x
            y = self._group_y
            if parent_transform.transpose_xy:
                x, y = y, x
            self._absolute_transform.x = parent_transform.x + parent_transform.dx * x
            self._absolute_transform.y = parent_transform.y + parent_transform.dy * y
            self._absolute_transform.dx = parent_transform.dx * self._scale
            self._absolute_transform.dy = parent_transform.dy * self._scale
            self._absolute_transform.transpose_xy = parent_transform.transpose_xy
            self._absolute_transform.mirror_x = parent_transform.mirror_x
            self._absolute_transform.mirror_y = parent_transform.mirror_y
            self._absolute_transform.scale = parent_transform.scale * self._scale
        self._update_child_transforms()

    def _update_child_transforms(self):
        if self.in_group:
            for layer in self._layers:
                layer.update_transform(self._absolute_transform)

    def _removal_cleanup(self, index):
        layer = self._layers[index]
        layer.update_transform(None)

    def _layer_update(self, index):
        layer = self._layers[index]
        layer.update_transform(self._absolute_transform)

    def append(self, layer):
        """Append a layer to the group. It will be drawn
        above other layers.
        """
        self.insert(len(self._layers), layer)

    def insert(self, index, layer):
        """Insert a layer into the group."""
        if not isinstance(layer, self._supported_types):
            raise ValueError("Invalid Group Member")
        if layer.in_group:
            raise ValueError("Layer already in a group.")
        if len(self._layers) == self._max_size:
            raise RuntimeError("Group full")
        self._layers.insert(index, layer)
        self._layer_update(index)

    def index(self, layer):
        """Returns the index of the first copy of layer.
        Raises ValueError if not found.
        """
        return self._layers.index(layer)

    def pop(self, index=-1):
        """Remove the ith item and return it."""
        self._removal_cleanup(index)
        return self._layers.pop(index)

    def remove(self, layer):
        """Remove the first copy of layer. Raises ValueError
        if it is not present."""
        index = self.index(layer)
        self._layers.pop(index)

    def __len__(self):
        """Returns the number of layers in a Group"""
        return len(self._layers)

    def __getitem__(self, index):
        """Returns the value at the given index."""
        return self._layers[index]

    def __setitem__(self, index, value):
        """Sets the value at the given index."""
        self._removal_cleanup(index)
        self._layers[index] = value
        self._layer_update(index)

    def __delitem__(self, index):
        """Deletes the value at the given index."""
        del self._layers[index]

    def _fill_area(self, buffer):
        if self._hidden_group:
            return

        for layer in self._layers:
            if isinstance(layer, (Group, TileGrid)):
                layer._fill_area(buffer)  # pylint: disable=protected-access

    @property
    def hidden(self):
        """True when the Group and all of it’s layers are not visible. When False, the
        Group’s layers are visible if they haven’t been hidden.
        """
        return self._hidden_group

    @hidden.setter
    def hidden(self, value):
        if not isinstance(value, (bool, int)):
            raise ValueError("Expecting a boolean or integer value")
        self._hidden_group = bool(value)

    @property
    def scale(self):
        """Scales each pixel within the Group in both directions. For example, when
        scale=2 each pixel will be represented by 2x2 pixels.
        """
        return self._scale

    @scale.setter
    def scale(self, value):
        self._set_scale(value)

    def _set_scale(self, value):
        # This is method allows the scale to be set by this class even when
        # the scale property is over-ridden by a subclass.
        if not isinstance(value, int) or value < 1:
            raise ValueError("Scale must be >= 1")
        if self._scale != value:
            parent_scale = self._absolute_transform.scale / self._scale
            self._absolute_transform.dx = (
                self._absolute_transform.dx / self._scale * value
            )
            self._absolute_transform.dy = (
                self._absolute_transform.dy / self._scale * value
            )
            self._absolute_transform.scale = parent_scale * value

            self._scale = value
            self._update_child_transforms()

    @property
    def x(self):
        """X position of the Group in the parent."""
        return self._group_x

    @x.setter
    def x(self, value):
        if not isinstance(value, int):
            raise ValueError("x must be an integer")
        if self._group_x != value:
            if self._absolute_transform.transpose_xy:
                dy_value = self._absolute_transform.dy / self._scale
                self._absolute_transform.y += dy_value * (value - self._group_x)
            else:
                dx_value = self._absolute_transform.dx / self._scale
                self._absolute_transform.x += dx_value * (value - self._group_x)
            self._group_x = value
            self._update_child_transforms()

    @property
    def y(self):
        """Y position of the Group in the parent."""
        return self._group_y

    @y.setter
    def y(self, value):
        if not isinstance(value, int):
            raise ValueError("y must be an integer")
        if self._group_y != value:
            if self._absolute_transform.transpose_xy:
                dx_value = self._absolute_transform.dx / self._scale
                self._absolute_transform.x += dx_value * (value - self._group_y)
            else:
                dy_value = self._absolute_transform.dy / self._scale
                self._absolute_transform.y += dy_value * (value - self._group_y)
            self._group_y = value
            self._update_child_transforms()
