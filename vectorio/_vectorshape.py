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
from typing import Union, Tuple
from circuitpython_typing import WriteableBuffer
from displayio._colorconverter import ColorConverter
from displayio._colorspace import Colorspace
from displayio._palette import Palette
from displayio._area import Area
from displayio._structs import null_transform, InputPixelStruct, OutputPixelStruct

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


class _VectorShape:
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
        self._current_area_dirty = True
        self._current_area = Area(0, 0, 0, 0)
        self._ephemeral_dirty_area = Area(0, 0, 0, 0)
        self._absolute_transform = null_transform
        self._get_screen_area(self._current_area)

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
        moved = current_area != self._current_area
        if moved:
            # This will add _current_area (the old position) to dirty area
            self._current_area.union(
                self._ephemeral_dirty_area, self._ephemeral_dirty_area
            )
            # This will add the new position to the dirty area
            current_area.union(self._ephemeral_dirty_area, self._ephemeral_dirty_area)
            # Dirty area tracks the shape's footprint between draws.  It's reset on refresh finish.
            current_area.copy_into(self._current_area)
        self._current_area_dirty = True

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
        if self._ephemeral_dirty_area.empty() and not self._current_area_dirty:
            return
        # Reset dirty area to nothing
        self._ephemeral_dirty_area.x1 = self._ephemeral_dirty_area.x2
        self._current_area_dirty = False

        if isinstance(self._pixel_shader, (Palette, ColorConverter)):
            self._pixel_shader._finish_refresh()  # pylint: disable=protected-access

    def _get_refresh_areas(self, areas: list[Area]) -> None:
        if self._current_area_dirty or (
            isinstance(self._pixel_shader, (Palette, ColorConverter))
            and self._pixel_shader._needs_refresh  # pylint: disable=protected-access
        ):
            if not self._ephemeral_dirty_area.empty():
                # Both are dirty, check if we should combine the areas or draw separately
                # Draws as few pixels as possible both when animations move short distances
                # and large distances. The display core implementation currently doesn't
                # combine areas to reduce redrawing of masked areas. If it does, this could
                # be simplified to just return the 2 possibly overlapping areas.
                area_swap = Area()
                self._ephemeral_dirty_area.compute_overlap(
                    self._current_area, area_swap
                )
                overlap_size = area_swap.size()
                self._ephemeral_dirty_area.union(self._current_area, area_swap)
                union_size = area_swap.size()
                current_size = self._current_area.size()
                dirty_size = self._ephemeral_dirty_area.size()

                if union_size - dirty_size - current_size + overlap_size <= min(
                    dirty_size, current_size
                ):
                    # The excluded / non-overlapping area from the disjoint dirty and current
                    # areas is smaller than the smallest area we need to draw. Redrawing the
                    # overlapping area would cost more than just drawing the union disjoint
                    # area once.
                    area_swap.copy_into(self._ephemeral_dirty_area)
                else:
                    # The excluded area between the 2 dirty areas is larger than the smallest
                    # dirty area. It would be more costly to combine these areas than possibly
                    # redraw some overlap.
                    areas.append(self._current_area)
                areas.append(self._ephemeral_dirty_area)
            else:
                areas.append(self._current_area)
        elif not self._ephemeral_dirty_area.empty():
            areas.append(self._ephemeral_dirty_area)

    def _update_transform(self, group_transform) -> None:
        self._absolute_transform = (
            null_transform if group_transform is None else group_transform
        )
        self._shape_set_dirty()
