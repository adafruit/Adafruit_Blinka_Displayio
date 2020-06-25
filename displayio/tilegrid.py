# The MIT License (MIT)
#
# Copyright (c) 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
`displayio.tilegrid`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

from recordclass import recordclass
from PIL import Image
from displayio.bitmap import Bitmap
from displayio.colorconverter import ColorConverter
from displayio.ondiskbitmap import OnDiskBitmap
from displayio.shape import Shape
from displayio.palette import Palette

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

Rectangle = recordclass("Rectangle", "x1 y1 x2 y2")
Transform = recordclass("Transform", "x y dx dy scale transpose_xy mirror_x mirror_y")

# pylint: disable=too-many-instance-attributes
class TileGrid:
    """Position a grid of tiles sourced from a bitmap and pixel_shader combination. Multiple
    grids can share bitmaps and pixel shaders.

    A single tile grid is also known as a Sprite.
    """

    def __init__(
        self,
        bitmap,
        *,
        pixel_shader,
        width=1,
        height=1,
        tile_width=None,
        tile_height=None,
        default_tile=0,
        x=0,
        y=0
    ):
        """Create a TileGrid object. The bitmap is source for 2d pixels. The pixel_shader is
        used to convert the value and its location to a display native pixel color. This may
        be a simple color palette lookup, a gradient, a pattern or a color transformer.

        tile_width and tile_height match the height of the bitmap by default.
        """
        if not isinstance(bitmap, (Bitmap, OnDiskBitmap, Shape)):
            raise ValueError("Unsupported Bitmap type")
        self._bitmap = bitmap
        bitmap_width = bitmap.width
        bitmap_height = bitmap.height

        if pixel_shader is not None and not isinstance(
            pixel_shader, (ColorConverter, Palette)
        ):
            raise ValueError("Unsupported Pixel Shader type")
        self._pixel_shader = pixel_shader
        if isinstance(self._pixel_shader, ColorConverter):
            self._pixel_shader._rgba = True  # pylint: disable=protected-access
        self._hidden = False
        self._x = x
        self._y = y
        self._width = width  # Number of Tiles Wide
        self._height = height  # Number of Tiles High
        self._transpose_xy = False
        self._flip_x = False
        self._flip_y = False
        self._top_left_x = 0
        self._top_left_y = 0
        if tile_width is None:
            tile_width = bitmap_width
        if tile_height is None:
            tile_height = bitmap_height
        if bitmap_width % tile_width != 0:
            raise ValueError("Tile width must exactly divide bitmap width")
        self._tile_width = tile_width
        if bitmap_height % tile_height != 0:
            raise ValueError("Tile height must exactly divide bitmap height")
        self._tile_height = tile_height
        if not 0 <= default_tile <= 255:
            raise ValueError("Default Tile is out of range")
        self._pixel_width = width * tile_width
        self._pixel_height = height * tile_height
        self._tiles = (self._width * self._height) * [default_tile]
        self.in_group = False
        self._absolute_transform = Transform(0, 0, 1, 1, 1, False, False, False)
        self._current_area = Rectangle(0, 0, self._pixel_width, self._pixel_height)
        self._moved = False

    def update_transform(self, absolute_transform):
        """Update the parent transform and child transforms"""
        self._absolute_transform = absolute_transform
        if self._absolute_transform is not None:
            self._update_current_x()
            self._update_current_y()

    def _update_current_x(self):
        if self._transpose_xy:
            width = self._pixel_height
        else:
            width = self._pixel_width
        if self._absolute_transform.transpose_xy:
            self._current_area.y1 = (
                self._absolute_transform.y + self._absolute_transform.dy * self._x
            )
            self._current_area.y2 = (
                self._absolute_transform.y
                + self._absolute_transform.dy * (self._x + width)
            )
            if self._current_area.y2 < self._current_area.y1:
                self._current_area.y1, self._current_area.y2 = (
                    self._current_area.y2,
                    self._current_area.y1,
                )
        else:
            self._current_area.x1 = (
                self._absolute_transform.x + self._absolute_transform.dx * self._x
            )
            self._current_area.x2 = (
                self._absolute_transform.x
                + self._absolute_transform.dx * (self._x + width)
            )
            if self._current_area.x2 < self._current_area.x1:
                self._current_area.x1, self._current_area.x2 = (
                    self._current_area.x2,
                    self._current_area.x1,
                )

    def _update_current_y(self):
        if self._transpose_xy:
            height = self._pixel_width
        else:
            height = self._pixel_height
        if self._absolute_transform.transpose_xy:
            self._current_area.x1 = (
                self._absolute_transform.x + self._absolute_transform.dx * self._y
            )
            self._current_area.x2 = (
                self._absolute_transform.x
                + self._absolute_transform.dx * (self._y + height)
            )
            if self._current_area.x2 < self._current_area.x1:
                self._current_area.x1, self._current_area.x2 = (
                    self._current_area.x2,
                    self._current_area.x1,
                )
        else:
            self._current_area.y1 = (
                self._absolute_transform.y + self._absolute_transform.dy * self._y
            )
            self._current_area.y2 = (
                self._absolute_transform.y
                + self._absolute_transform.dy * (self._y + height)
            )
            if self._current_area.y2 < self._current_area.y1:
                self._current_area.y1, self._current_area.y2 = (
                    self._current_area.y2,
                    self._current_area.y1,
                )

    def _shade(self, pixel_value):
        if isinstance(self._pixel_shader, Palette):
            return self._pixel_shader[pixel_value]["rgba"]
        if isinstance(self._pixel_shader, ColorConverter):
            return self._pixel_shader.convert(pixel_value)
        return pixel_value

    def _apply_palette(self, image):
        image.putpalette(
            self._pixel_shader._get_palette()  # pylint: disable=protected-access
        )

    def _add_alpha(self, image):
        alpha = self._bitmap._image.copy().convert(  # pylint: disable=protected-access
            "P"
        )
        alpha.putpalette(
            self._pixel_shader._get_alpha_palette()  # pylint: disable=protected-access
        )
        image.putalpha(alpha.convert("L"))

    # pylint: disable=too-many-locals
    def _fill_area(self, buffer):
        """Draw onto the image"""
        if self._hidden:
            return

        image = Image.new(
            "RGBA",
            (self._width * self._tile_width, self._height * self._tile_height),
            (0, 0, 0, 0),
        )

        tile_count_x = self._bitmap.width // self._tile_width
        x = self._x
        y = self._y

        for tile_x in range(self._width):
            for tile_y in range(self._height):
                tile_index = self._tiles[tile_y * self._width + tile_x]
                tile_index_x = tile_index % tile_count_x
                tile_index_y = tile_index // tile_count_x
                tile_image = self._bitmap._image  # pylint: disable=protected-access
                if isinstance(self._pixel_shader, Palette):
                    tile_image = tile_image.copy().convert("P")
                    self._apply_palette(tile_image)
                    tile_image = tile_image.convert("RGBA")
                    self._add_alpha(tile_image)
                elif isinstance(self._pixel_shader, ColorConverter):
                    # This will be needed for eInks, grayscale, and monochrome displays
                    pass
                image.alpha_composite(
                    tile_image,
                    dest=(tile_x * self._tile_width, tile_y * self._tile_height),
                    source=(
                        tile_index_x * self._tile_width,
                        tile_index_y * self._tile_height,
                    ),
                )

        if self._absolute_transform is not None:
            if self._absolute_transform.scale > 1:
                image = image.resize(
                    (
                        self._pixel_width * self._absolute_transform.scale,
                        self._pixel_height * self._absolute_transform.scale,
                    ),
                    resample=Image.NEAREST,
                )
            if self._absolute_transform.mirror_x:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
            if self._absolute_transform.mirror_y:
                image = image.transpose(Image.FLIP_TOP_BOTTOM)
            if self._absolute_transform.transpose_xy:
                image = image.transpose(Image.TRANSPOSE)
            x *= self._absolute_transform.dx
            y *= self._absolute_transform.dy
            x += self._absolute_transform.x
            y += self._absolute_transform.y
        buffer.alpha_composite(image, (x, y))

    # pylint: enable=too-many-locals

    @property
    def hidden(self):
        """True when the TileGrid is hidden. This may be False even
        when a part of a hidden Group."""
        return self._hidden

    @hidden.setter
    def hidden(self, value):
        if not isinstance(value, (bool, int)):
            raise ValueError("Expecting a boolean or integer value")
        self._hidden = bool(value)

    @property
    def x(self):
        """X position of the left edge in the parent."""
        return self._x

    @x.setter
    def x(self, value):
        if not isinstance(value, int):
            raise TypeError("X should be a integer type")
        if self._x != value:
            self._x = value
            self._update_current_x()

    @property
    def y(self):
        """Y position of the top edge in the parent."""
        return self._y

    @y.setter
    def y(self, value):
        if not isinstance(value, int):
            raise TypeError("Y should be a integer type")
        if self._y != value:
            self._y = value
            self._update_current_y()

    @property
    def flip_x(self):
        """If true, the left edge rendered will be the right edge of the right-most tile."""
        return self._flip_x

    @flip_x.setter
    def flip_x(self, value):
        if not isinstance(value, bool):
            raise TypeError("Flip X should be a boolean type")
        if self._flip_x != value:
            self._flip_x = value

    @property
    def flip_y(self):
        """If true, the top edge rendered will be the bottom edge of the bottom-most tile."""
        return self._flip_y

    @flip_y.setter
    def flip_y(self, value):
        if not isinstance(value, bool):
            raise TypeError("Flip Y should be a boolean type")
        if self._flip_y != value:
            self._flip_y = value

    @property
    def transpose_xy(self):
        """If true, the TileGrid’s axis will be swapped. When combined with mirroring, any 90
        degree rotation can be achieved along with the corresponding mirrored version.
        """
        return self._transpose_xy

    @transpose_xy.setter
    def transpose_xy(self, value):
        if not isinstance(value, bool):
            raise TypeError("Transpose XY should be a boolean type")
        if self._transpose_xy != value:
            self._transpose_xy = value
            self._update_current_x()
            self._update_current_y()

    @property
    def pixel_shader(self):
        """The pixel shader of the tilegrid."""
        return self._pixel_shader

    def __getitem__(self, index):
        """Returns the tile index at the given index. The index can either be
        an x,y tuple or an int equal to ``y * width + x``'.
        """
        if isinstance(index, (tuple, list)):
            x = index[0]
            y = index[1]
            index = y * self._width + x
        elif isinstance(index, int):
            x = index % self._width
            y = index // self._width
        if x > self._width or y > self._height or index >= len(self._tiles):
            raise ValueError("Tile index out of bounds")
        return self._tiles[index]

    def __setitem__(self, index, value):
        """Sets the tile index at the given index. The index can either be
        an x,y tuple or an int equal to ``y * width + x``.
        """
        if isinstance(index, (tuple, list)):
            x = index[0]
            y = index[1]
            index = y * self._width + x
        elif isinstance(index, int):
            x = index % self._width
            y = index // self._width
        if x > self._width or y > self._height or index >= len(self._tiles):
            raise ValueError("Tile index out of bounds")
        if not 0 <= value <= 255:
            raise ValueError("Tile value out of bounds")
        self._tiles[index] = value


# pylint: enable=too-many-instance-attributes
