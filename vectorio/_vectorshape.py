# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`vectorio._vectorshape`
================================================================================

vectorio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

import struct
from collections import deque
from typing import Union, Tuple
from circuitpython_typing import WriteableBuffer
from displayio._colorconverter import ColorConverter
from displayio._colorspace import Colorspace
from displayio._palette import Palette
from displayio._area import Area
from displayio._structs import null_transform, InputPixelStruct, OutputPixelStruct

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


# How the loop below decides whether a pixel is covered. A rectangle and a circle
# are a couple of comparisons, so the loop does them itself rather than calling the
# shape once per pixel. Anything else asks the shape.
_COVER_RECTANGLE = 0
_COVER_CIRCLE = 1
_COVER_ASK_SHAPE = 2


def _shape_fast_path(colorspace: Colorspace, shape, pixel_shader):
    """(color, how to test coverage, the two numbers that test needs) for a stock
    shape, or None when the loop below does not apply: another display depth, a
    dithered or subclassed palette, a shape that is not one of the three here, or a
    color index outside the palette."""
    # pylint: disable=protected-access, unidiomatic-typecheck, import-outside-toplevel
    if colorspace.depth != 16:
        return None
    if type(pixel_shader) is not Palette or pixel_shader._dither:
        return None
    # Imported here because each shape module imports this one
    from ._circle import Circle
    from ._polygon import Polygon
    from ._rectangle import Rectangle

    # Exact types, since a subclass may return something else from _get_pixel
    kind = type(shape)
    if kind is Rectangle:
        # _get_pixel is 0 <= x < width and 0 <= y < height
        cover = (_COVER_RECTANGLE, shape._width, shape._height)
    elif kind is Circle:
        # _get_pixel works out to x * x + y * y <= radius * radius
        cover = (_COVER_CIRCLE, shape._radius, shape._radius * shape._radius)
    elif kind is Polygon:
        cover = (_COVER_ASK_SHAPE, 0, 0)
    else:
        return None
    index = shape._color_index - 1
    if not 0 <= index < len(pixel_shader):
        return None
    input_pixel = InputPixelStruct()
    output_pixel = OutputPixelStruct()
    input_pixel.pixel = index
    output_pixel.pixel = 0
    output_pixel.opaque = True
    pixel_shader._get_color(colorspace, input_pixel, output_pixel)
    if not output_pixel.opaque:
        return None
    return (output_pixel.pixel,) + cover


def _fill_shape_pixels(buffer, mask, cover, geometry, shape, transform) -> bool:
    # pylint: disable=too-many-arguments, too-many-locals, too-many-branches
    # pylint: disable=too-many-statements, protected-access, invalid-name
    """The pixel loop of _VectorShape._fill_area for one of the stock shapes with a
    Palette on a 16 bit display. Same shape as the loop it replaces, but the color is
    resolved once, the screen to shape transform is worked out here, and a rectangle
    or a circle is tested with a couple of comparisons instead of a call per pixel.
    The transform leaves one shape coordinate the same all the way along a row, so a
    row outside the shape is skipped whole. Returns False if any pixel of the area
    was left uncovered."""
    color, how, cover_a, cover_b = cover
    start_px, linestride_px, x1, y1, x2, y2 = geometry
    transpose, shape_origin_x, shape_origin_y, sign_x, sign_y = transform
    get_pixel = shape._get_pixel
    if transpose:
        # x and y swap roles, so the shape's x is what stays fixed along a row
        row_origin, row_sign = shape_origin_x, sign_x
        col_origin, col_sign = shape_origin_y, sign_y
        row_len, col_len = cover_a, cover_b
    else:
        row_origin, row_sign = shape_origin_y, sign_y
        col_origin, col_sign = shape_origin_x, sign_x
        row_len, col_len = cover_b, cover_a

    full_coverage = True
    row_start_px = start_px
    for y in range(y1, y2):
        row_coord = (y - row_origin) * row_sign
        limit = 0
        if how == _COVER_RECTANGLE:
            if not 0 <= row_coord < row_len:
                full_coverage = False  # the whole row is outside the rectangle
                row_start_px += linestride_px
                continue
            limit = col_len
        elif how == _COVER_CIRCLE:
            if row_coord > cover_a or row_coord < -cover_a:
                full_coverage = False  # the whole row is outside the circle
                row_start_px += linestride_px
                continue
            limit = cover_b - row_coord * row_coord
        for x in range(x1, x2):
            pixel_index = row_start_px + (x - x1)
            if mask[pixel_index >> 5] & (1 << (pixel_index & 31)):
                continue
            col_coord = (x - col_origin) * col_sign
            if how == _COVER_RECTANGLE:
                covered = 0 <= col_coord < limit
            elif how == _COVER_CIRCLE:
                covered = col_coord * col_coord <= limit
            elif transpose:
                covered = get_pixel(row_coord, col_coord) != 0
            else:
                covered = get_pixel(col_coord, row_coord) != 0
            if not covered:
                # vectorio shapes use 0 to mean the area is not covered
                full_coverage = False
                continue
            mask[pixel_index >> 5] |= 1 << (pixel_index & 31)
            buffer[pixel_index] = color
        row_start_px += linestride_px
    return full_coverage


class _VectorShape:
    _dirty_area_sentinel = object()

    def __init__(
        self,
        pixel_shader: Union[ColorConverter, Palette],
        x: int,
        y: int,
    ):
        self._x = x
        self._y = y
        self._pixel_shader = pixel_shader
        self._hidden = False
        self._current_area = Area(0, 0, 0, 0)
        self._ephemeral_dirty_area = Area(0, 0, 0, 0)
        self._refresh_current_area = Area(0, 0, 0, 0)
        self._refresh_area_swap = Area(0, 0, 0, 0)
        # deque append and popleft are thread-safe in CPython. Dirty areas queued
        # during display I/O remain separate from the refresh-owned areas above.
        self._pending_dirty_areas = deque()
        self._refresh_state_dirty = False
        self._absolute_transform = null_transform
        self._get_screen_area(self._current_area)
        initial_area = Area()
        self._current_area.copy_into(initial_area)
        self._pending_dirty_areas.append(initial_area)

    @property
    def x(self) -> int:
        """X position of the center point of the circle in the parent."""
        return self._x

    @x.setter
    def x(self, value: int) -> None:
        if self._x == value:
            return
        self._x = value
        self._shape_set_dirty()

    @property
    def y(self) -> int:
        """Y position of the center point of the circle in the parent."""
        return self._y

    @y.setter
    def y(self, value: int) -> None:
        if self._y == value:
            return
        self._y = value
        self._shape_set_dirty()

    @property
    def hidden(self) -> bool:
        """Hide the circle or not."""
        return self._hidden

    @hidden.setter
    def hidden(self, value: bool) -> None:
        self._hidden = value
        self._shape_set_dirty()

    @property
    def location(self) -> Tuple[int, int]:
        """(X,Y) position of the center point of the circle in the parent."""
        return (self._x, self._y)

    @location.setter
    def location(self, value: Tuple[int, int]) -> None:
        if len(value) != 2:
            raise ValueError("location must be a list or tuple with exactly 2 integers")
        x = value[0]
        y = value[1]
        dirty = False
        if self._x != x:
            self._x = x
            dirty = True
        if self._y != y:
            self._y = y
            dirty = True
        if dirty:
            self._shape_set_dirty()

    @property
    def pixel_shader(self) -> Union[ColorConverter, Palette]:
        """The pixel shader of the circle."""
        return self._pixel_shader

    @pixel_shader.setter
    def pixel_shader(self, value: Union[ColorConverter, Palette]) -> None:
        self._pixel_shader = value

    def _get_area(self, _out_area: Area) -> Area:
        raise NotImplementedError("Subclass must implement _get_area")

    def _get_pixel(self, _x: int, _y: int) -> int:
        raise NotImplementedError("Subclass must implement _get_pixel")

    def _shape_set_dirty(self) -> None:
        current_area = Area()
        self._get_screen_area(current_area)
        current_area.copy_into(self._current_area)
        self._pending_dirty_areas.append(current_area)

    def _get_dirty_area(self, out_area: Area) -> Area:
        out_area.x1 = out_area.x2
        self._ephemeral_dirty_area.union(self._current_area, out_area)
        return True  # For now just always redraw.

    def _get_screen_area(self, out_area) -> Area:
        self._get_area(out_area)
        if self._absolute_transform.transpose_xy:
            x = self._absolute_transform.x + self._absolute_transform.dx * self._y
            y = self._absolute_transform.y + self._absolute_transform.dy * self._x
            if self._absolute_transform.dx < 1:
                out_area.y1 = out_area.y1 * -1 + 1
                out_area.y2 = out_area.y2 * -1 + 1
            if self._absolute_transform.dy < 1:
                out_area.x1 = out_area.x1 * -1 + 1
                out_area.x2 = out_area.x2 * -1 + 1
            self._area_transpose(out_area)
        else:
            x = self._absolute_transform.x + self._absolute_transform.dx * self._x
            y = self._absolute_transform.y + self._absolute_transform.dy * self._y
            if self._absolute_transform.dx < 1:
                out_area.x1 = out_area.x1 * -1 + 1
                out_area.x2 = out_area.x2 * -1 + 1
            if self._absolute_transform.dy < 1:
                out_area.y1 = out_area.y1 * -1 + 1
                out_area.y2 = out_area.y2 * -1 + 1
        out_area.canon()
        out_area.shift(x, y)

    @staticmethod
    def _area_transpose(to_transpose: Area) -> Area:
        to_transpose.x1, to_transpose.y1 = to_transpose.y1, to_transpose.x1
        to_transpose.x2, to_transpose.y2 = to_transpose.y2, to_transpose.x2

    def _screen_to_shape_coordinates(self, x: int, y: int) -> Tuple[int, int]:
        """Get the target pixel based on the shape's coordinate space"""
        if self._absolute_transform.transpose_xy:
            out_shape_x = (
                y - self._absolute_transform.y - self._absolute_transform.dy * self._x
            )
            out_shape_y = (
                x - self._absolute_transform.x - self._absolute_transform.dx * self._y
            )

            if self._absolute_transform.dx < 1:
                out_shape_x *= -1
            if self._absolute_transform.dy < 1:
                out_shape_y *= -1
        else:
            out_shape_x = (
                x - self._absolute_transform.x - self._absolute_transform.dx * self._x
            )
            out_shape_y = (
                y - self._absolute_transform.y - self._absolute_transform.dy * self._y
            )

            if self._absolute_transform.dx < 1:
                out_shape_x *= -1
            if self._absolute_transform.dy < 1:
                out_shape_y *= -1

            # It's mirrored via dx. Maybe we need to add support for also separately mirroring?
            # if self.absolute_transform.mirror_x:
            #    pixel_to_get_x = (
            #        (shape_area.x2 - shape_area.x1)
            #        - (pixel_to_get_x - shape_area.x1)
            #        + shape_area.x1
            #        - 1
            #    )
            # if self.absolute_transform.mirror_y:
            #    pixel_to_get_y = (
            #        (shape_area.y2 - shape_area.y1)
            #        - (pixel_to_get_y - shape_area.y1)
            #        + +shape_area.y1
            #        - 1
            #    )

        return out_shape_x, out_shape_y

    def _shape_contains(self, x: int, y: int) -> bool:
        shape_x, shape_y = self._screen_to_shape_coordinates(x, y)
        return self._get_pixel(shape_x, shape_y) != 0

    def _fill_area(
        self,
        colorspace: Colorspace,
        area: Area,
        mask: WriteableBuffer,
        buffer: WriteableBuffer,
    ) -> bool:
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        if self._hidden:
            return False

        overlap = Area()
        if not area.compute_overlap(self._current_area, overlap):
            return False

        full_coverage = area == overlap
        pixels_per_byte = 8 // colorspace.depth
        linestride_px = area.width()
        line_dirty_offset_px = (overlap.y1 - area.y1) * linestride_px
        column_dirty_offset_px = overlap.x1 - area.x1

        cover = _shape_fast_path(colorspace, self, self._pixel_shader)
        if cover is not None:
            xform = self._absolute_transform
            if xform.transpose_xy:
                origin_x = xform.y + xform.dy * self._x
                origin_y = xform.x + xform.dx * self._y
            else:
                origin_x = xform.x + xform.dx * self._x
                origin_y = xform.y + xform.dy * self._y
            transform = (
                xform.transpose_xy,
                origin_x,
                origin_y,
                -1 if xform.dx < 1 else 1,
                -1 if xform.dy < 1 else 1,
            )
            geometry = (
                line_dirty_offset_px + column_dirty_offset_px,
                linestride_px,
                overlap.x1,
                overlap.y1,
                overlap.x2,
                overlap.y2,
            )
            covered = _fill_shape_pixels(
                buffer.cast("B").cast("H"), mask, cover, geometry, self, transform
            )
            return full_coverage and covered

        input_pixel = InputPixelStruct()
        output_pixel = OutputPixelStruct()

        shape_area = Area()
        self._get_area(shape_area)

        mask_start_px = line_dirty_offset_px

        for input_pixel.y in range(overlap.y1, overlap.y2):
            mask_start_px += column_dirty_offset_px
            for input_pixel.x in range(overlap.x1, overlap.x2):
                # Check the mask first to see if the pixel has already been set.
                pixel_index = mask_start_px + (input_pixel.x - overlap.x1)
                mask_doubleword = mask[pixel_index // 32]
                mask_bit = pixel_index % 32
                if (mask_doubleword & (1 << mask_bit)) != 0:
                    continue
                output_pixel.pixel = 0

                # Cast input screen coordinates to shape coordinates to pick the pixel to draw
                pixel_to_get_x, pixel_to_get_y = self._screen_to_shape_coordinates(
                    input_pixel.x, input_pixel.y
                )
                input_pixel.pixel = self._get_pixel(pixel_to_get_x, pixel_to_get_y)

                # vectorio shapes use 0 to mean "area is not covered."
                # We can skip all the rest of the work for this pixel
                # if it's not currently covered by the shape.
                if input_pixel.pixel == 0:
                    full_coverage = False
                else:
                    # Pixel is not transparent. Let's pull the pixel value index down
                    # to 0-base for more error-resistant palettes.
                    input_pixel.pixel -= 1
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

                    mask[pixel_index // 32] |= 1 << (pixel_index % 32)
                    if colorspace.depth == 16:
                        struct.pack_into(
                            "H",
                            buffer.cast("B"),
                            pixel_index * 2,
                            output_pixel.pixel,
                        )
                    elif colorspace.depth == 32:
                        struct.pack_into(
                            "I",
                            buffer.cast("B"),
                            pixel_index * 4,
                            output_pixel.pixel,
                        )
                    elif colorspace.depth == 8:
                        buffer.cast("B")[pixel_index] = output_pixel.pixel & 0xFF
                    elif colorspace.depth < 8:
                        # Reorder the offsets to pack multiple rows into
                        # a byte (meaning they share a column).
                        if not colorspace.pixels_in_byte_share_row:
                            row = pixel_index // linestride_px
                            col = pixel_index % linestride_px
                            # Dividing by pixels_per_byte does truncated division
                            # even if we multiply it back out
                            pixel_index = (
                                col * pixels_per_byte
                                + (row // pixels_per_byte)
                                * pixels_per_byte
                                * linestride_px
                                + (row % pixels_per_byte)
                            )
                        shift = (pixel_index % pixels_per_byte) * colorspace.depth
                        if colorspace.reverse_pixels_in_byte:
                            # Reverse the shift by subtracting it from the leftmost shift
                            shift = (pixels_per_byte - 1) * colorspace.depth - shift
                        buffer.cast("B")[pixel_index // pixels_per_byte] |= (
                            output_pixel.pixel << shift
                        )
            mask_start_px += linestride_px - column_dirty_offset_px

        return full_coverage

    def _finish_refresh(self) -> None:
        if not self._refresh_state_dirty:
            return
        self._refresh_state_dirty = False

        if isinstance(self._pixel_shader, (Palette, ColorConverter)):
            self._pixel_shader._finish_refresh()  # pylint: disable=protected-access

    def _consume_dirty_areas(self) -> bool:
        """Collect a stable snapshot of the dirty areas queued for this refresh."""
        # The sentinel is an atomic frame boundary. Anything appended after it
        # remains queued for the next refresh.
        self._pending_dirty_areas.append(self._dirty_area_sentinel)
        area = self._pending_dirty_areas.popleft()
        if area is self._dirty_area_sentinel:
            self._ephemeral_dirty_area.x1 = self._ephemeral_dirty_area.x2
            return False

        self._refresh_current_area.union(area, self._ephemeral_dirty_area)
        area.copy_into(self._refresh_current_area)
        while True:
            area = self._pending_dirty_areas.popleft()
            if area is self._dirty_area_sentinel:
                break
            self._refresh_current_area.union(area, self._refresh_area_swap)
            self._refresh_area_swap.union(
                self._ephemeral_dirty_area, self._ephemeral_dirty_area
            )
            area.copy_into(self._refresh_current_area)
        return True

    def _prepare_full_refresh(self) -> None:
        """Consume dirty state covered by a full display refresh."""
        shader_dirty = (
            isinstance(self._pixel_shader, (Palette, ColorConverter))
            and self._pixel_shader._needs_refresh  # pylint: disable=protected-access
        )
        self._refresh_state_dirty = self._consume_dirty_areas() or shader_dirty

    def _get_refresh_areas(self, areas: list[Area]) -> None:
        shader_dirty = (
            isinstance(self._pixel_shader, (Palette, ColorConverter))
            and self._pixel_shader._needs_refresh  # pylint: disable=protected-access
        )
        if not self._pending_dirty_areas and not shader_dirty:
            return

        shape_dirty = self._consume_dirty_areas()
        self._refresh_state_dirty = shape_dirty or shader_dirty
        current_area = self._refresh_current_area
        ephemeral_dirty_area = self._ephemeral_dirty_area
        if shape_dirty or shader_dirty:
            if not ephemeral_dirty_area.empty():
                # Both are dirty, check if we should combine the areas or draw separately
                # Draws as few pixels as possible both when animations move short distances
                # and large distances. The display core implementation currently doesn't
                # combine areas to reduce redrawing of masked areas. If it does, this could
                # be simplified to just return the 2 possibly overlapping areas.
                area_swap = self._refresh_area_swap
                ephemeral_dirty_area.compute_overlap(current_area, area_swap)
                overlap_size = area_swap.size()
                ephemeral_dirty_area.union(current_area, area_swap)
                union_size = area_swap.size()
                current_size = current_area.size()
                dirty_size = ephemeral_dirty_area.size()

                if union_size - dirty_size - current_size + overlap_size <= min(
                    dirty_size, current_size
                ):
                    # The excluded / non-overlapping area from the disjoint dirty and current
                    # areas is smaller than the smallest area we need to draw. Redrawing the
                    # overlapping area would cost more than just drawing the union disjoint
                    # area once.
                    area_swap.copy_into(ephemeral_dirty_area)
                else:
                    # The excluded area between the 2 dirty areas is larger than the smallest
                    # dirty area. It would be more costly to combine these areas than possibly
                    # redraw some overlap.
                    areas.append(current_area)
                areas.append(ephemeral_dirty_area)
            else:
                areas.append(current_area)
        elif not ephemeral_dirty_area.empty():
            areas.append(ephemeral_dirty_area)

    def _update_transform(self, group_transform) -> None:
        self._absolute_transform = (
            null_transform if group_transform is None else group_transform
        )
        self._shape_set_dirty()
