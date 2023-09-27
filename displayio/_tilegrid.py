# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.tilegrid`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

import struct
from typing import Union, Optional, Tuple
from circuitpython_typing import WriteableBuffer
from ._bitmap import Bitmap
from ._colorconverter import ColorConverter
from ._ondiskbitmap import OnDiskBitmap
from ._shape import Shape
from ._palette import Palette
from ._structs import (
    InputPixelStruct,
    OutputPixelStruct,
    null_transform,
)
from ._colorspace import Colorspace
from ._area import Area

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class TileGrid:
    # pylint: disable=too-many-instance-attributes, too-many-statements
    """Position a grid of tiles sourced from a bitmap and pixel_shader combination. Multiple
    grids can share bitmaps and pixel shaders.

    A single tile grid is also known as a Sprite.
    """

    def __init__(
        self,
        bitmap: Union[Bitmap, OnDiskBitmap, Shape],
        *,
        pixel_shader: Union[ColorConverter, Palette],
        width: int = 1,
        height: int = 1,
        tile_width: Optional[int] = None,
        tile_height: Optional[int] = None,
        default_tile: int = 0,
        x: int = 0,
        y: int = 0,
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
        self._hidden_tilegrid = False
        self._hidden_by_parent = False
        self._rendered_hidden = False
        self._name = "Tilegrid"
        self._x = x
        self._y = y
        self._width_in_tiles = width
        self._height_in_tiles = height
        self._transpose_xy = False
        self._flip_x = False
        self._flip_y = False
        self._top_left_x = 0
        self._top_left_y = 0
        if tile_width is None or tile_width == 0:
            tile_width = bitmap_width
        if tile_height is None or tile_width == 0:
            tile_height = bitmap_height
        if tile_width < 1 or tile_height < 1:
            raise ValueError("Tile width and height must be greater than 0")
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
        self._tiles = bytearray(
            (self._width_in_tiles * self._height_in_tiles) * [default_tile]
        )
        self._in_group = False
        self._absolute_transform = None
        self._current_area = Area(0, 0, self._pixel_width, self._pixel_height)
        self._dirty_area = Area(0, 0, 0, 0)
        self._previous_area = Area(0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF)
        self._moved = False
        self._full_change = True
        self._partial_change = True
        self._bitmap_width_in_tiles = bitmap_width // tile_width
        self._tiles_in_bitmap = self._bitmap_width_in_tiles * (
            bitmap_height // tile_height
        )

    def _update_transform(self, absolute_transform):
        """Update the parent transform and child transforms"""
        self._in_group = absolute_transform is not None
        self._absolute_transform = absolute_transform
        if self._absolute_transform is not None:
            self._moved = True
            self._update_current_x()
            self._update_current_y()

    def _update_current_x(self):
        if self._transpose_xy:
            width = self._pixel_height
        else:
            width = self._pixel_width

        absolute_transform = (
            null_transform
            if self._absolute_transform is None
            else self._absolute_transform
        )

        if absolute_transform.transpose_xy:
            self._current_area.y1 = (
                absolute_transform.y + absolute_transform.dy * self._x
            )
            self._current_area.y2 = absolute_transform.y + absolute_transform.dy * (
                self._x + width
            )
            if self._current_area.y2 < self._current_area.y1:
                self._current_area.y1, self._current_area.y2 = (
                    self._current_area.y2,
                    self._current_area.y1,
                )
        else:
            self._current_area.x1 = (
                absolute_transform.x + absolute_transform.dx * self._x
            )
            self._current_area.x2 = absolute_transform.x + absolute_transform.dx * (
                self._x + width
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

        absolute_transform = (
            null_transform
            if self._absolute_transform is None
            else self._absolute_transform
        )

        if absolute_transform.transpose_xy:
            self._current_area.x1 = (
                absolute_transform.x + absolute_transform.dx * self._y
            )
            self._current_area.x2 = absolute_transform.x + absolute_transform.dx * (
                self._y + height
            )
            if self._current_area.x2 < self._current_area.x1:
                self._current_area.x1, self._current_area.x2 = (
                    self._current_area.x2,
                    self._current_area.x1,
                )
        else:
            self._current_area.y1 = (
                absolute_transform.y + absolute_transform.dy * self._y
            )
            self._current_area.y2 = absolute_transform.y + absolute_transform.dy * (
                self._y + height
            )
            if self._current_area.y2 < self._current_area.y1:
                self._current_area.y1, self._current_area.y2 = (
                    self._current_area.y2,
                    self._current_area.y1,
                )

    def _shade(self, pixel_value):
        if isinstance(self._pixel_shader, Palette):
            return self._pixel_shader[pixel_value]
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

    def _fill_area(
        self,
        colorspace: Colorspace,
        area: Area,
        mask: WriteableBuffer,
        buffer: WriteableBuffer,
    ) -> bool:
        """Draw onto the image"""
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements

        # If no tiles are present we have no impact
        tiles = self._tiles

        if tiles is None or len(tiles) == 0:
            return False

        if self._hidden_tilegrid or self._hidden_by_parent:
            return False
        overlap = Area()  # area, current_area, overlap
        if not area.compute_overlap(self._current_area, overlap):
            return False
        # else:
        #    print("Checking", area.x1, area.y1, area.x2, area.y2)
        #    print("Overlap", overlap.x1, overlap.y1, overlap.x2, overlap.y2)

        if self._bitmap.width <= 0 or self._bitmap.height <= 0:
            return False

        x_stride = 1
        y_stride = area.width()

        flip_x = self._flip_x
        flip_y = self._flip_y
        if self._transpose_xy != self._absolute_transform.transpose_xy:
            flip_x, flip_y = flip_y, flip_x

        start = 0
        if (self._absolute_transform.dx < 0) != flip_x:
            start += (area.x2 - area.x1 - 1) * x_stride
            x_stride *= -1
        if (self._absolute_transform.dy < 0) != flip_y:
            start += (area.y2 - area.y1 - 1) * y_stride
            y_stride *= -1

        # Track if this layer finishes filling in the given area. We can ignore any remaining
        # layers at that point.
        full_coverage = area == overlap

        transformed = Area()
        area.transform_within(
            flip_x != (self._absolute_transform.dx < 0),
            flip_y != (self._absolute_transform.dy < 0),
            self.transpose_xy != self._absolute_transform.transpose_xy,
            overlap,
            self._current_area,
            transformed,
        )

        start_x = transformed.x1 - self._current_area.x1
        end_x = transformed.x2 - self._current_area.x1
        start_y = transformed.y1 - self._current_area.y1
        end_y = transformed.y2 - self._current_area.y1

        if (self._absolute_transform.dx < 0) != flip_x:
            x_shift = area.x2 - overlap.x2
        else:
            x_shift = overlap.x1 - area.x1
        if (self._absolute_transform.dy < 0) != flip_y:
            y_shift = area.y2 - overlap.y2
        else:
            y_shift = overlap.y1 - area.y1

        # This untransposes x and y so it aligns with bitmap rows
        if self._transpose_xy != self._absolute_transform.transpose_xy:
            x_stride, y_stride = y_stride, x_stride
            x_shift, y_shift = y_shift, x_shift

        pixels_per_byte = 8 // colorspace.depth

        input_pixel = InputPixelStruct()
        output_pixel = OutputPixelStruct()
        for input_pixel.y in range(start_y, end_y):
            row_start = (
                start + (input_pixel.y - start_y + y_shift) * y_stride
            )  # In Pixels
            local_y = input_pixel.y // self._absolute_transform.scale
            for input_pixel.x in range(start_x, end_x):
                # Compute the destination pixel in the buffer and mask based on the transformations
                offset = (
                    row_start + (input_pixel.x - start_x + x_shift) * x_stride
                )  # In Pixels

                # Check the mask first to see if the pixel has already been set
                if mask[offset // 8] & (1 << (offset % 8)):
                    continue
                local_x = input_pixel.x // self._absolute_transform.scale
                tile_location = (
                    (local_y // self._tile_height + self._top_left_y)
                    % self._height_in_tiles
                ) * self._width_in_tiles + (
                    local_x // self._tile_width + self._top_left_x
                ) % self._width_in_tiles
                input_pixel.tile = tiles[tile_location]
                input_pixel.tile_x = (
                    input_pixel.tile % self._bitmap_width_in_tiles
                ) * self._tile_width + local_x % self._tile_width
                input_pixel.tile_y = (
                    input_pixel.tile // self._bitmap_width_in_tiles
                ) * self._tile_height + local_y % self._tile_height

                output_pixel.pixel = 0
                input_pixel.pixel = 0

                # We always want to read bitmap pixels by row first and then transpose into
                # the destination buffer because most bitmaps are row associated.
                if isinstance(self._bitmap, (Bitmap, Shape, OnDiskBitmap)):
                    input_pixel.pixel = (
                        self._bitmap._get_pixel(  # pylint: disable=protected-access
                            input_pixel.tile_x, input_pixel.tile_y
                        )
                    )

                output_pixel.opaque = True
                if self._pixel_shader is None:
                    output_pixel.pixel = input_pixel.pixel
                elif isinstance(self._pixel_shader, Palette):
                    self._pixel_shader._get_color(  # pylint: disable=protected-access
                        colorspace, input_pixel, output_pixel
                    )
                elif isinstance(self._pixel_shader, ColorConverter):
                    self._pixel_shader._convert(  # pylint: disable=protected-access
                        colorspace, input_pixel, output_pixel
                    )

                if not output_pixel.opaque:
                    full_coverage = False
                else:
                    mask[offset // 8] |= 1 << (offset % 8)
                    # print("Mask", mask)
                    if colorspace.depth == 16:
                        struct.pack_into(
                            "H",
                            buffer,
                            offset * 2,
                            output_pixel.pixel,
                        )
                    elif colorspace.depth == 32:
                        struct.pack_into(
                            "I",
                            buffer,
                            offset * 4,
                            output_pixel.pixel,
                        )
                    elif colorspace.depth == 8:
                        buffer[offset] = output_pixel.pixel & 0xFF
                    elif colorspace.depth < 8:
                        # Reorder the offsets to pack multiple rows into
                        # a byte (meaning they share a column).
                        if not colorspace.pixels_in_byte_share_row:
                            width = area.width()
                            row = offset // width
                            col = offset % width
                            # Dividing by pixels_per_byte does truncated division
                            # even if we multiply it back out
                            offset = (
                                col * pixels_per_byte
                                + (row // pixels_per_byte) * width
                                + (row % pixels_per_byte)
                            )
                        shift = (offset % pixels_per_byte) * colorspace.depth
                        if colorspace.reverse_pixels_in_byte:
                            # Reverse the shift by subtracting it from the leftmost shift
                            shift = (pixels_per_byte - 1) * colorspace.depth - shift
                        buffer[offset // pixels_per_byte] |= output_pixel.pixel << shift

        return full_coverage

    def _finish_refresh(self):
        first_draw = self._previous_area.x1 == self._previous_area.x2
        hidden = self._hidden_tilegrid or self._hidden_by_parent
        if not first_draw and hidden:
            self._previous_area.x2 = self._previous_area.x1
        elif self._moved or first_draw:
            self._current_area.copy_into(self._previous_area)

        self._moved = False
        self._full_change = False
        self._partial_change = False
        if isinstance(self._pixel_shader, (Palette, ColorConverter)):
            self._pixel_shader._finish_refresh()  # pylint: disable=protected-access
        if isinstance(self._bitmap, (Bitmap, Shape)):
            self._bitmap._finish_refresh()  # pylint: disable=protected-access

    def _get_refresh_areas(self, areas: list[Area]) -> None:
        # pylint: disable=invalid-name, too-many-branches, too-many-statements
        first_draw = self._previous_area.x1 == self._previous_area.x2
        hidden = self._hidden_tilegrid or self._hidden_by_parent

        # Check hidden first because it trumps all other changes
        if hidden:
            self._rendered_hidden = True
            if not first_draw:
                areas.append(self._previous_area)
            return
        if self._moved and not first_draw:
            self._previous_area.union(self._current_area, self._dirty_area)
            if self._dirty_area.size() < 2 * self._pixel_width * self._pixel_height:
                areas.append(self._dirty_area)
                return
            areas.append(self._current_area)
            areas.append(self._previous_area)
            return

        tail = areas[-1] if areas else None
        # If we have an in-memory bitmap, then check it for modifications
        if isinstance(self._bitmap, Bitmap):
            self._bitmap._get_refresh_areas(areas)  # pylint: disable=protected-access
            refresh_area = areas[-1] if areas else None
            if refresh_area != tail:
                # Special case a TileGrid that shows a full bitmap and use its
                # dirty area. Copy it to ours so we can transform it.
                if self._tiles_in_bitmap == 1:
                    refresh_area.copy_into(self._dirty_area)
                    self._partial_change = True
                else:
                    self._full_change = True
        elif isinstance(self._bitmap, Shape):
            self._bitmap._get_refresh_areas(areas)  # pylint: disable=protected-access
            refresh_area = areas[-1] if areas else None
            if refresh_area != tail:
                refresh_area.copy_into(self._dirty_area)
                self._partial_change = True

        self._full_change = self._full_change or (
            isinstance(self._pixel_shader, (Palette, ColorConverter))
            and self._pixel_shader._needs_refresh  # pylint: disable=protected-access
        )
        if self._full_change or first_draw:
            areas.append(self._current_area)
            return

        if self._partial_change:
            x = self._x
            y = self._y
            if self._absolute_transform.transpose_xy:
                x, y = y, x
            x1 = self._dirty_area.x1
            x2 = self._dirty_area.x2
            if self._flip_x:
                x1 = self._pixel_width - x1
                x2 = self._pixel_width - x2
            y1 = self._dirty_area.y1
            y2 = self._dirty_area.y2
            if self._flip_y:
                y1 = self._pixel_height - y1
                y2 = self._pixel_height - y2
            if self._transpose_xy != self._absolute_transform.transpose_xy:
                x1, y1 = y1, x1
                x2, y2 = y2, x2
            self._dirty_area.x1 = (
                self._absolute_transform.x + self._absolute_transform.dx * (x + x1)
            )
            self._dirty_area.y1 = (
                self._absolute_transform.y + self._absolute_transform.dy * (y + y1)
            )
            self._dirty_area.x2 = (
                self._absolute_transform.x + self._absolute_transform.dx * (x + x2)
            )
            self._dirty_area.y2 = (
                self._absolute_transform.y + self._absolute_transform.dy * (y + y2)
            )
            if self._dirty_area.y2 < self._dirty_area.y1:
                self._dirty_area.y1, self._dirty_area.y2 = (
                    self._dirty_area.y2,
                    self._dirty_area.y1,
                )
            if self._dirty_area.x2 < self._dirty_area.x1:
                self._dirty_area.x1, self._dirty_area.x2 = (
                    self._dirty_area.x2,
                    self._dirty_area.x1,
                )
            areas.append(self._dirty_area)

    def _set_hidden(self, hidden: bool) -> None:
        self._hidden_tilegrid = hidden
        self._rendered_hidden = False
        if not hidden:
            self._full_change = True

    def _set_hidden_by_parent(self, hidden: bool) -> None:
        self._hidden_by_parent = hidden
        self._rendered_hidden = False
        if not hidden:
            self._full_change = True

    def _get_rendered_hidden(self) -> bool:
        return self._rendered_hidden

    def _set_all_tiles(self, tile_index: int) -> None:
        """Set all tiles to the given tile index"""
        if tile_index >= self._tiles_in_bitmap:
            raise ValueError("Tile index out of bounds")
        self._tiles = bytearray(
            (self._width_in_tiles * self._height_in_tiles) * [tile_index]
        )
        self._full_change = True

    def _set_tile(self, x: int, y: int, tile_index: int) -> None:
        self._tiles[y * self._width_in_tiles + x] = tile_index
        temp_area = Area()
        if not self._partial_change:
            tile_area = self._dirty_area
        else:
            tile_area = temp_area
        top_x = (x - self._top_left_x) % self._width_in_tiles
        if top_x < 0:
            top_x += self._width_in_tiles
        tile_area.x1 = top_x * self._tile_width
        tile_area.x2 = tile_area.x1 + self._tile_width
        top_y = (y - self._top_left_y) % self._height_in_tiles
        if top_y < 0:
            top_y += self._height_in_tiles
        tile_area.y1 = top_y * self._tile_height
        tile_area.y2 = tile_area.y1 + self._tile_height

        if self._partial_change:
            self._dirty_area.union(temp_area, self._dirty_area)

        self._partial_change = True

    def _set_top_left(self, x: int, y: int) -> None:
        self._top_left_x = x
        self._top_left_y = y
        self._full_change = True

    @property
    def hidden(self) -> bool:
        """True when the TileGrid is hidden. This may be False even
        when a part of a hidden Group."""
        return self._hidden_tilegrid

    @hidden.setter
    def hidden(self, value: bool):
        if not isinstance(value, (bool, int)):
            raise ValueError("Expecting a boolean or integer value")
        value = bool(value)
        self._set_hidden(value)

    @property
    def x(self) -> int:
        """X position of the left edge in the parent."""
        return self._x

    @x.setter
    def x(self, value: int):
        if not isinstance(value, int):
            raise TypeError("X should be a integer type")
        if self._x != value:
            self._moved = True
            self._x = value
            if self._absolute_transform is not None:
                self._update_current_x()

    @property
    def y(self) -> int:
        """Y position of the top edge in the parent."""
        return self._y

    @y.setter
    def y(self, value: int):
        if not isinstance(value, int):
            raise TypeError("Y should be a integer type")
        if self._y != value:
            self._moved = True
            self._y = value
            if self._absolute_transform is not None:
                self._update_current_y()

    @property
    def flip_x(self) -> bool:
        """If true, the left edge rendered will be the right edge of the right-most tile."""
        return self._flip_x

    @flip_x.setter
    def flip_x(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("Flip X should be a boolean type")
        if self._flip_x != value:
            self._flip_x = value
            self._full_change = True

    @property
    def flip_y(self) -> bool:
        """If true, the top edge rendered will be the bottom edge of the bottom-most tile."""
        return self._flip_y

    @flip_y.setter
    def flip_y(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("Flip Y should be a boolean type")
        if self._flip_y != value:
            self._flip_y = value
            self._full_change = True

    @property
    def transpose_xy(self) -> bool:
        """If true, the TileGrid's axis will be swapped. When combined with mirroring, any 90
        degree rotation can be achieved along with the corresponding mirrored version.
        """
        return self._transpose_xy

    @transpose_xy.setter
    def transpose_xy(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("Transpose XY should be a boolean type")
        if self._transpose_xy != value:
            self._transpose_xy = value
            if self._pixel_width == self._pixel_height:
                self._full_change = True
                return
            self._update_current_x()
            self._update_current_y()
            self._moved = True

    @property
    def pixel_shader(self) -> Union[ColorConverter, Palette]:
        """The pixel shader of the tilegrid."""
        return self._pixel_shader

    @pixel_shader.setter
    def pixel_shader(self, new_pixel_shader: Union[ColorConverter, Palette]) -> None:
        if not isinstance(new_pixel_shader, ColorConverter) and not isinstance(
            new_pixel_shader, Palette
        ):
            raise TypeError(
                "Unsupported Type: new_pixel_shader must be ColorConverter or Palette"
            )

        self._pixel_shader = new_pixel_shader
        self._full_change = True

    @property
    def bitmap(self) -> Union[Bitmap, OnDiskBitmap, Shape]:
        """The Bitmap, OnDiskBitmap, or Shape that is assigned to this TileGrid"""
        return self._bitmap

    @bitmap.setter
    def bitmap(self, new_bitmap: Union[Bitmap, OnDiskBitmap, Shape]) -> None:
        if (
            not isinstance(new_bitmap, Bitmap)
            and not isinstance(new_bitmap, OnDiskBitmap)
            and not isinstance(new_bitmap, Shape)
        ):
            raise TypeError(
                "Unsupported Type: new_bitmap must be Bitmap, OnDiskBitmap, or Shape"
            )

        if (
            new_bitmap.width != self.bitmap.width
            or new_bitmap.height != self.bitmap.height
        ):
            raise ValueError("New bitmap must be same size as old bitmap")

        self._bitmap = new_bitmap
        self._full_change = True

    def _extract_and_check_index(self, index):
        if isinstance(index, (tuple, list)):
            x = index[0]
            y = index[1]
            index = y * self._width_in_tiles + x
        elif isinstance(index, int):
            x = index % self._width_in_tiles
            y = index // self._width_in_tiles
        if (
            x > self._width_in_tiles
            or y > self._height_in_tiles
            or index >= len(self._tiles)
        ):
            raise ValueError("Tile index out of bounds")
        return x, y

    def __getitem__(self, index: Union[Tuple[int, int], int]) -> int:
        """Returns the tile index at the given index. The index can either be
        an x,y tuple or an int equal to ``y * width + x``'.
        """
        x, y = self._extract_and_check_index(index)
        return self._tiles[y * self._width_in_tiles + x]

    def __setitem__(self, index: Union[Tuple[int, int], int], value: int) -> None:
        """Sets the tile index at the given index. The index can either be
        an x,y tuple or an int equal to ``y * width + x``.
        """
        x, y = self._extract_and_check_index(index)
        if not 0 <= value <= 255:
            raise ValueError("Tile value out of bounds")
        self._set_tile(x, y, value)

    @property
    def width(self) -> int:
        """Width in tiles"""
        return self._width_in_tiles

    @property
    def height(self) -> int:
        """Height in tiles"""
        return self._height_in_tiles

    @property
    def tile_width(self) -> int:
        """Width of each tile in pixels"""
        return self._tile_width

    @property
    def tile_height(self) -> int:
        """Height of each tile in pixels"""
        return self._tile_height
