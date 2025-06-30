# SPDX-FileCopyrightText: 2025 Tim Cocks
#
# SPDX-License-Identifier: MIT
"""
Collection of bitmap manipulation tools
"""

import math
import struct
from typing import Optional, Tuple, BinaryIO
import circuitpython_typing
from displayio import Bitmap, Colorspace


# pylint: disable=invalid-name, too-many-arguments, too-many-locals, too-many-branches, too-many-statements
def fill_region(dest_bitmap: Bitmap, x1: int, y1: int, x2: int, y2: int, value: int):
    """Draws the color value into the destination bitmap within the
    rectangular region bounded by (x1,y1) and (x2,y2), exclusive.

    :param bitmap dest_bitmap: Destination bitmap that will be written into
    :param int x1: x-pixel position of the first corner of the rectangular fill region
    :param int y1: y-pixel position of the first corner of the rectangular fill region
    :param int x2: x-pixel position of the second corner of the rectangular fill region (exclusive)
    :param int y2: y-pixel position of the second corner of the rectangular fill region (exclusive)
    :param int value: Bitmap palette index that will be written into the rectangular
           fill region in the destination bitmap"""

    for y in range(y1, y2):
        for x in range(x1, x2):
            dest_bitmap[x, y] = value


def draw_line(dest_bitmap: Bitmap, x1: int, y1: int, x2: int, y2: int, value: int):
    """Draws a line into a bitmap specified two endpoints (x1,y1) and (x2,y2).

    :param bitmap dest_bitmap: Destination bitmap that will be written into
    :param int x1: x-pixel position of the line's first endpoint
    :param int y1: y-pixel position of the line's first endpoint
    :param int x2: x-pixel position of the line's second endpoint
    :param int y2: y-pixel position of the line's second endpoint
    :param int value: Bitmap palette index that will be written into the
        line in the destination bitmap"""
    dx = abs(x2 - x1)
    sx = 1 if x1 < x2 else -1
    dy = -abs(y2 - y1)
    sy = 1 if y1 < y2 else -1
    error = dx + dy

    while True:
        dest_bitmap[x1, y1] = value
        if x1 == x2 and y1 == y2:
            break
        e2 = 2 * error
        if e2 >= dy:
            error += dy
            x1 += sx
        if e2 <= dx:
            error += dx
            y1 += sy


def draw_circle(dest_bitmap: Bitmap, x: int, y: int, radius: int, value: int):
    """Draws a circle into a bitmap specified using a center (x0,y0) and radius r.

    :param bitmap dest_bitmap: Destination bitmap that will be written into
    :param int x: x-pixel position of the circle's center
    :param int y: y-pixel position of the circle's center
    :param int radius: circle's radius
    :param int value: Bitmap palette index that will be written into the
           circle in the destination bitmap"""

    x = max(0, min(x, dest_bitmap.width - 1))
    y = max(0, min(y, dest_bitmap.height - 1))

    xb = 0
    yb = radius
    d = 3 - 2 * radius

    # Bresenham's circle algorithm
    while xb <= yb:
        dest_bitmap[xb + x, yb + y] = value
        dest_bitmap[-xb + x, -yb + y] = value
        dest_bitmap[-xb + x, yb + y] = value
        dest_bitmap[xb + x, -yb + y] = value
        dest_bitmap[yb + x, xb + y] = value
        dest_bitmap[-yb + x, xb + y] = value
        dest_bitmap[-yb + x, -xb + y] = value
        dest_bitmap[yb + x, -xb + y] = value

        if d <= 0:
            d = d + (4 * xb) + 6
        else:
            d = d + 4 * (xb - yb) + 10
            yb = yb - 1
        xb += 1


def draw_polygon(
    dest_bitmap: Bitmap,
    xs: circuitpython_typing.ReadableBuffer,
    ys: circuitpython_typing.ReadableBuffer,
    value: int,
    close: bool = True,
):
    """Draw a polygon connecting points on provided bitmap with provided value

    :param bitmap dest_bitmap: Destination bitmap that will be written into
    :param ReadableBuffer xs: x-pixel position of the polygon's vertices
    :param ReadableBuffer ys: y-pixel position of the polygon's vertices
    :param int value: Bitmap palette index that will be written into the
           line in the destination bitmap
    :param bool close: (Optional) Whether to connect first and last point. (True)
    """
    if len(xs) != len(ys):
        raise ValueError("Length of xs and ys must be equal.")

    for i in range(len(xs) - 1):
        cur_point = (xs[i], ys[i])
        next_point = (xs[i + 1], ys[i + 1])
        print(f"cur: {cur_point}, next: {next_point}")
        draw_line(
            dest_bitmap=dest_bitmap,
            x1=cur_point[0],
            y1=cur_point[1],
            x2=next_point[0],
            y2=next_point[1],
            value=value,
        )

    if close:
        print(f"close: {(xs[0], ys[0])} - {(xs[-1], ys[-1])}")
        draw_line(
            dest_bitmap=dest_bitmap,
            x1=xs[0],
            y1=ys[0],
            x2=xs[-1],
            y2=ys[-1],
            value=value,
        )


def blit(
    dest_bitmap: Bitmap,
    source_bitmap: Bitmap,
    x: int,
    y: int,
    *,
    x1: int = 0,
    y1: int = 0,
    x2: Optional[int] = None,
    y2: Optional[int] = None,
    skip_source_index: Optional[int] = None,
    skip_dest_index: Optional[int] = None,
):
    """Inserts the source_bitmap region defined by rectangular boundaries
    (x1,y1) and (x2,y2) into the bitmap at the specified (x,y) location.

    :param bitmap dest_bitmap: Destination bitmap that the area will
     be copied into.
    :param bitmap source_bitmap: Source bitmap that contains the graphical
     region to be copied
    :param int x: Horizontal pixel location in bitmap where source_bitmap
                  upper-left corner will be placed
    :param int y: Vertical pixel location in bitmap where source_bitmap upper-left
                  corner will be placed
    :param int x1: Minimum x-value for rectangular bounding box to be
     copied from the source bitmap
    :param int y1: Minimum y-value for rectangular bounding box to be
     copied from the source bitmap
    :param int x2: Maximum x-value (exclusive) for rectangular
     bounding box to be copied from the source bitmap.
     If unspecified or `None`, the source bitmap width is used.
    :param int y2: Maximum y-value (exclusive) for rectangular
     bounding box to be copied from the source bitmap.
     If unspecified or `None`, the source bitmap height is used.
    :param int skip_source_index: bitmap palette index in the source that
     will not be copied, set to None to copy all pixels
    :param int skip_dest_index: bitmap palette index in the
     destination bitmap that will not get overwritten by the
     pixels from the source"""

    # pylint: disable=invalid-name
    if x2 is None:
        x2 = source_bitmap.width
    if y2 is None:
        y2 = source_bitmap.height

    # Rearrange so that x1 < x2 and y1 < y2
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1

    # Ensure that x2 and y2 are within source bitmap size
    x2 = min(x2, source_bitmap.width)
    y2 = min(y2, source_bitmap.height)

    for y_count in range(y2 - y1):
        for x_count in range(x2 - x1):
            x_placement = x + x_count
            y_placement = y + y_count

            if (dest_bitmap.width > x_placement >= 0) and (
                dest_bitmap.height > y_placement >= 0
            ):  # ensure placement is within target bitmap
                # get the palette index from the source bitmap
                this_pixel_color = source_bitmap[
                    y1 + (y_count * source_bitmap.width) + x1 + x_count
                ]

                if (skip_source_index is None) or (
                    this_pixel_color != skip_source_index
                ):
                    if (skip_dest_index is None) or (
                        dest_bitmap[y_placement * dest_bitmap.width + x_placement]
                        != skip_dest_index
                    ):
                        dest_bitmap[
                            y_placement * dest_bitmap.width + x_placement
                        ] = this_pixel_color
            elif y_placement > dest_bitmap.height:
                break


def rotozoom(
    dest_bitmap: Bitmap,
    source_bitmap: Bitmap,
    *,
    ox: Optional[int] = None,
    oy: Optional[int] = None,
    dest_clip0: Optional[Tuple[int, int]] = None,
    dest_clip1: Optional[Tuple[int, int]] = None,
    px: Optional[int] = None,
    py: Optional[int] = None,
    source_clip0: Optional[Tuple[int, int]] = None,
    source_clip1: Optional[Tuple[int, int]] = None,
    angle: Optional[float] = None,
    scale: Optional[float] = None,
    skip_index: Optional[int] = None,
):
    """Inserts the source bitmap region into the destination bitmap with rotation
    (angle), scale and clipping (both on source and destination bitmaps).

    :param bitmap dest_bitmap: Destination bitmap that will be copied into
    :param bitmap source_bitmap: Source bitmap that contains the graphical region to be copied
    :param int ox: Horizontal pixel location in destination bitmap where source bitmap
           point (px,py) is placed. Defaults to None which causes it to use the horizontal
           midway point of the destination bitmap.
    :param int oy: Vertical pixel location in destination bitmap where source bitmap
           point (px,py) is placed. Defaults to None which causes it to use the vertical
           midway point of the destination bitmap.
    :param Tuple[int,int] dest_clip0: First corner of rectangular destination clipping
           region that constrains region of writing into destination bitmap
    :param Tuple[int,int] dest_clip1: Second corner of rectangular destination clipping
           region that constrains region of writing into destination bitmap
    :param int px: Horizontal pixel location in source bitmap that is placed into the
           destination bitmap at (ox,oy). Defaults to None which causes it to use the
           horizontal midway point in the source bitmap.
    :param int py: Vertical pixel location in source bitmap that is placed into the
           destination bitmap at (ox,oy). Defaults to None which causes it to use the
           vertical midway point in the source bitmap.
    :param Tuple[int,int] source_clip0: First corner of rectangular source clipping
           region that constrains region of reading from the source bitmap
    :param Tuple[int,int] source_clip1: Second corner of rectangular source clipping
           region that constrains region of reading from the source bitmap
    :param float angle: Angle of rotation, in radians (positive is clockwise direction).
           Defaults to None which gets treated as 0.0 radians or no rotation.
    :param float scale: Scaling factor. Defaults to None which gets treated as 1.0 or same
           as original source size.
    :param int skip_index: Bitmap palette index in the source that will not be copied,
           set to None to copy all pixels"""
    if ox is None:
        ox = dest_bitmap.width // 2
    if oy is None:
        oy = dest_bitmap.height // 2

    if dest_clip0 is None:
        dest_clip0 = (0, 0)
    if dest_clip1 is None:
        dest_clip1 = (dest_bitmap.width, dest_bitmap.height)

    if px is None:
        px = source_bitmap.width // 2
    if py is None:
        py = source_bitmap.height // 2

    if source_clip0 is None:
        source_clip0 = (0, 0)
    if source_clip1 is None:
        source_clip1 = (source_bitmap.width, source_bitmap.height)

    if angle is None:
        angle = 0.0
    if scale is None:
        scale = 1.0

    dest_clip0_x, dest_clip0_y = dest_clip0
    dest_clip1_x, dest_clip1_y = dest_clip1
    source_clip0_x, source_clip0_y = source_clip0
    source_clip1_x, source_clip1_y = source_clip1

    minx = dest_clip1_x
    miny = dest_clip1_y
    maxx = dest_clip0_x
    maxy = dest_clip0_y

    sin_angle = math.sin(angle)
    cos_angle = math.cos(angle)

    def update_bounds(dx, dy):
        nonlocal minx, maxx, miny, maxy
        if dx < minx:
            minx = int(dx)
        if dx > maxx:
            maxx = int(dx)
        if dy < miny:
            miny = int(dy)
        if dy > maxy:
            maxy = int(dy)

    w = source_bitmap.width
    h = source_bitmap.height

    dx = -cos_angle * px * scale + sin_angle * py * scale + ox
    dy = -sin_angle * px * scale - cos_angle * py * scale + oy
    update_bounds(dx, dy)

    dx = cos_angle * (w - px) * scale + sin_angle * py * scale + ox
    dy = sin_angle * (w - px) * scale - cos_angle * py * scale + oy
    update_bounds(dx, dy)

    dx = cos_angle * (w - px) * scale - sin_angle * (h - py) * scale + ox
    dy = sin_angle * (w - px) * scale + cos_angle * (h - py) * scale + oy
    update_bounds(dx, dy)

    dx = -cos_angle * px * scale - sin_angle * (h - py) * scale + ox
    dy = -sin_angle * px * scale + cos_angle * (h - py) * scale + oy
    update_bounds(dx, dy)

    # Clip to destination area
    minx = max(minx, dest_clip0_x)
    maxx = min(maxx, dest_clip1_x - 1)
    miny = max(miny, dest_clip0_y)
    maxy = min(maxy, dest_clip1_y - 1)

    dv_col = cos_angle / scale
    du_col = sin_angle / scale
    du_row = dv_col
    dv_row = -du_col

    startu = px - (ox * dv_col + oy * du_col)
    startv = py - (ox * dv_row + oy * du_row)

    rowu = startu + miny * du_col
    rowv = startv + miny * dv_col

    for y in range(miny, maxy + 1):
        u = rowu + minx * du_row
        v = rowv + minx * dv_row
        for x in range(minx, maxx + 1):
            if (source_clip0_x <= u < source_clip1_x) and (
                source_clip0_y <= v < source_clip1_y
            ):
                c = source_bitmap[int(u), int(v)]
                if skip_index is None or c != skip_index:
                    dest_bitmap[x, y] = c
            u += du_row
            v += dv_row
        rowu += du_col
        rowv += dv_col


def arrayblit(
    bitmap: Bitmap,
    data: circuitpython_typing.ReadableBuffer,
    x1: int = 0,
    y1: int = 0,
    x2: Optional[int] = None,
    y2: Optional[int] = None,
    skip_index: Optional[int] = None,
):
    """Inserts pixels from ``data`` into the rectangle
     of width×height pixels with the upper left corner at ``(x,y)``

    The values from ``data`` are taken modulo the number of color values
    available in the destination bitmap.

    If x1 or y1 are not specified, they are taken as 0.  If x2 or y2
    are not specified, or are given as None, they are taken as the width
    and height of the image.

    The coordinates affected by the blit are
    ``x1 <= x < x2`` and ``y1 <= y < y2``.

    ``data`` must contain at least as many elements as required.  If it
    contains excess elements, they are ignored.

    The blit takes place by rows, so the first elements of ``data`` go
    to the first row, the next elements to the next row, and so on.

    :param displayio.Bitmap bitmap: A writable bitmap
    :param ReadableBuffer data: Buffer containing the source pixel values
    :param int x1: The left corner of the area to blit into (inclusive)
    :param int y1: The top corner of the area to blit into (inclusive)
    :param int x2: The right of the area to blit into (exclusive)
    :param int y2: The bottom corner of the area to blit into (exclusive)
    :param int skip_index: Bitmap palette index in the source
     that will not be copied, set to None to copy all pixels

    """
    if x2 is None:
        x2 = bitmap.width
    if y2 is None:
        y2 = bitmap.height

    _value_count = 2**bitmap._bits_per_value  # pylint: disable=protected-access
    for y in range(y1, y2):
        for x in range(x1, x2):
            i = y * (x2 - x1) + x
            value = int(data[i] % _value_count)
            if skip_index is None or value != skip_index:
                bitmap[x, y] = value


def readinto(
    bitmap: Bitmap,
    file: BinaryIO,
    bits_per_pixel: int,
    element_size: int = 1,
    reverse_pixels_in_element: bool = False,
    swap_bytes: bool = False,
    reverse_rows: bool = False,
):
    """Reads from a binary file into a bitmap.

    The file must be positioned so that it consists of ``bitmap.height``
    rows of pixel data, where each row is the smallest multiple
    of ``element_size`` bytes that can hold ``bitmap.width`` pixels.

    The bytes in an element can be optionally swapped, and the pixels
    in an element can be reversed.  Also, therow loading direction can
     be reversed, which may be requires for loading certain bitmap files.

    This function doesn't parse image headers, but is useful to
    speed up loading of uncompressed image formats such as PCF glyph data.

    :param displayio.Bitmap bitmap: A writable bitmap
    :param typing.BinaryIO file: A file opened in binary mode
    :param int bits_per_pixel: Number of bits per pixel.
     Values 1, 2, 4, 8, 16, 24, and 32 are supported;
    :param int element_size: Number of bytes per element.
     Values of 1, 2, and 4 are supported, except that 24
     ``bits_per_pixel`` requires 1 byte per element.
    :param bool reverse_pixels_in_element: If set, the first pixel in a
      word is taken from the Most Significant Bits; otherwise,
      it is taken from the Least Significant Bits.
    :param bool swap_bytes_in_element: If the ``element_size`` is not 1,
     then reverse the byte order of each element read.
    :param bool reverse_rows: Reverse the direction of the row loading
     (required for some bitmap images).
    """
    width = bitmap.width
    height = bitmap.height
    bits_per_value = bitmap._bits_per_value  # pylint: disable=protected-access
    mask = (1 << bits_per_value) - 1

    elements_per_row = (width * bits_per_pixel + element_size * 8 - 1) // (
        element_size * 8
    )
    rowsize = element_size * elements_per_row

    for y in range(height):
        row_bytes = file.read(rowsize)
        if len(row_bytes) != rowsize:
            raise EOFError()

        # Convert the raw bytes into the appropriate type array for processing
        rowdata = bytearray(row_bytes)

        if swap_bytes:
            if element_size == 2:
                rowdata = bytearray(
                    b"".join(
                        struct.pack("<H", struct.unpack(">H", rowdata[i : i + 2])[0])
                        for i in range(0, len(rowdata), 2)
                    )
                )
            elif element_size == 4:
                rowdata = bytearray(
                    b"".join(
                        struct.pack("<I", struct.unpack(">I", rowdata[i : i + 4])[0])
                        for i in range(0, len(rowdata), 4)
                    )
                )

        y_draw = height - 1 - y if reverse_rows else y

        for x in range(width):
            value = 0
            if bits_per_pixel == 1:
                byte_offset = x // 8
                bit_offset = 7 - (x % 8) if reverse_pixels_in_element else x % 8
                value = (rowdata[byte_offset] >> bit_offset) & 0x1
            elif bits_per_pixel == 2:
                byte_offset = x // 4
                bit_index = 3 - (x % 4) if reverse_pixels_in_element else x % 4
                bit_offset = 2 * bit_index
                value = (rowdata[byte_offset] >> bit_offset) & 0x3
            elif bits_per_pixel == 4:
                byte_offset = x // 2
                bit_index = 1 - (x % 2) if reverse_pixels_in_element else x % 2
                bit_offset = 4 * bit_index
                value = (rowdata[byte_offset] >> bit_offset) & 0xF
            elif bits_per_pixel == 8:
                value = rowdata[x]
            elif bits_per_pixel == 16:
                value = struct.unpack_from("<H", rowdata, x * 2)[0]
            elif bits_per_pixel == 24:
                offset = x * 3
                value = (
                    (rowdata[offset] << 16)
                    | (rowdata[offset + 1] << 8)
                    | rowdata[offset + 2]
                )
            elif bits_per_pixel == 32:
                value = struct.unpack_from("<I", rowdata, x * 4)[0]

            bitmap[x, y_draw] = value & mask


class BlendMode:
    """
    Options for modes to use by alphablend() function.
    """

    # pylint: disable=too-few-public-methods

    Normal = "bitmaptools.BlendMode.Normal"
    Screen = "bitmaptools.BlendMode.Screen"


def alphablend(
    dest: Bitmap,
    source1: Bitmap,
    source2: Bitmap,
    colorspace: Colorspace,
    factor1: float = 0.5,
    factor2: Optional[float] = None,
    blendmode: BlendMode = BlendMode.Normal,
    skip_source1_index: Optional[int] = None,
    skip_source2_index: Optional[int] = None,
):
    """Alpha blend the two source bitmaps into the destination.

    It is permitted for the destination bitmap to be one of the two
    source bitmaps.

    :param bitmap dest_bitmap: Destination bitmap that will be written into
    :param bitmap source_bitmap_1: The first source bitmap
    :param bitmap source_bitmap_2: The second source bitmap
    :param float factor1: The proportion of bitmap 1 to mix in
    :param float factor2: The proportion of bitmap 2 to mix in.
      If specified as `None`, ``1-factor1`` is used.  Usually the proportions should sum to 1.
    :param displayio.Colorspace colorspace: The colorspace of the bitmaps.
      They must all have the same colorspace.  Only the following colorspaces are permitted:
      ``L8``, ``RGB565``, ``RGB565_SWAPPED``, ``BGR565`` and ``BGR565_SWAPPED``.
    :param bitmaptools.BlendMode blendmode: The blend mode to use. Default is Normal.
    :param int skip_source1_index: Bitmap palette or luminance index in
      source_bitmap_1 that will not be blended, set to None to blend all pixels
    :param int skip_source2_index: Bitmap palette or luminance index in
      source_bitmap_2 that will not be blended, set to None to blend all pixels

    For the L8 colorspace, the bitmaps must have a bits-per-value of 8.
    For the RGB colorspaces, they must have a bits-per-value of 16."""

    def clamp(val, minval, maxval):
        return max(minval, min(maxval, val))

    ifactor1 = int(factor1 * 256)
    ifactor2 = int(factor2 * 256)

    width, height = dest.width, dest.height

    if colorspace == "L8":
        for y in range(height):
            for x in range(width):
                sp1 = source1[x, y]
                sp2 = source2[x, y]
                blend_source1 = skip_source1_index is None or sp1 != skip_source1_index
                blend_source2 = skip_source2_index is None or sp2 != skip_source2_index

                if blend_source1 and blend_source2:
                    sda = sp1 * ifactor1
                    sca = sp2 * ifactor2

                    if blendmode == BlendMode.Screen:
                        blend = sca + sda - (sca * sda // 65536)
                    elif blendmode == BlendMode.Normal:
                        blend = sca + sda * (256 - ifactor2) // 256

                    denom = ifactor1 + ifactor2 - ifactor1 * ifactor2 // 256
                    pixel = blend // denom
                elif blend_source1:
                    pixel = sp1 * ifactor1 // 256
                elif blend_source2:
                    pixel = sp2 * ifactor2 // 256
                else:
                    pixel = dest[x, y]

                dest[x, y] = clamp(pixel, 0, 255)

    else:
        swap = colorspace in ("RGB565_SWAPPED", "BGR565_SWAPPED")
        r_mask = 0xF800
        g_mask = 0x07E0
        b_mask = 0x001F

        for y in range(height):
            for x in range(width):
                sp1 = source1[x, y]
                sp2 = source2[x, y]

                if swap:
                    sp1 = ((sp1 & 0xFF) << 8) | ((sp1 >> 8) & 0xFF)
                    sp2 = ((sp2 & 0xFF) << 8) | ((sp2 >> 8) & 0xFF)

                blend_source1 = skip_source1_index is None or sp1 != skip_source1_index
                blend_source2 = skip_source2_index is None or sp2 != skip_source2_index

                if blend_source1 and blend_source2:
                    ifactor_blend = ifactor1 + ifactor2 - ifactor1 * ifactor2 // 256

                    red_dca = ((sp1 & r_mask) >> 8) * ifactor1
                    grn_dca = ((sp1 & g_mask) >> 3) * ifactor1
                    blu_dca = ((sp1 & b_mask) << 3) * ifactor1

                    red_sca = ((sp2 & r_mask) >> 8) * ifactor2
                    grn_sca = ((sp2 & g_mask) >> 3) * ifactor2
                    blu_sca = ((sp2 & b_mask) << 3) * ifactor2

                    if blendmode == BlendMode.Screen:
                        red_blend = red_sca + red_dca - (red_sca * red_dca // 65536)
                        grn_blend = grn_sca + grn_dca - (grn_sca * grn_dca // 65536)
                        blu_blend = blu_sca + blu_dca - (blu_sca * blu_dca // 65536)
                    elif blendmode == BlendMode.Normal:
                        red_blend = red_sca + red_dca * (256 - ifactor2) // 256
                        grn_blend = grn_sca + grn_dca * (256 - ifactor2) // 256
                        blu_blend = blu_sca + blu_dca * (256 - ifactor2) // 256

                    r = ((red_blend // ifactor_blend) << 8) & r_mask
                    g = ((grn_blend // ifactor_blend) << 3) & g_mask
                    b = ((blu_blend // ifactor_blend) >> 3) & b_mask

                    pixel = (r & r_mask) | (g & g_mask) | (b & b_mask)

                    if swap:
                        pixel = ((pixel & 0xFF) << 8) | ((pixel >> 8) & 0xFF)

                elif blend_source1:
                    r = ((sp1 & r_mask) * ifactor1 // 256) & r_mask
                    g = ((sp1 & g_mask) * ifactor1 // 256) & g_mask
                    b = ((sp1 & b_mask) * ifactor1 // 256) & b_mask
                    pixel = r | g | b
                elif blend_source2:
                    r = ((sp2 & r_mask) * ifactor2 // 256) & r_mask
                    g = ((sp2 & g_mask) * ifactor2 // 256) & g_mask
                    b = ((sp2 & b_mask) * ifactor2 // 256) & b_mask
                    pixel = r | g | b
                else:
                    pixel = dest[x, y]

                print(f"pixel hex: {hex(pixel)}")
                dest[x, y] = pixel


class DitherAlgorithm:
    """
    Options for algorithm to use by dither() function.
    """

    # pylint: disable=too-few-public-methods

    Atkinson = "bitmaptools.DitherAlgorithm.Atkinson"
    FloydStenberg = "bitmaptools.DitherAlgorithm.FloydStenberg"

    atkinson = {
        "count": 4,
        "mx": 2,
        "dl": 256 // 8,
        "terms": [
            {"dx": 2, "dy": 0, "dl": 256 // 8},
            {"dx": -1, "dy": 1, "dl": 256 // 8},
            {"dx": 0, "dy": 1, "dl": 256 // 8},
            {"dx": 0, "dy": 2, "dl": 256 // 8},
        ],
    }

    floyd_stenberg = {
        "count": 3,
        "mx": 1,
        "dl": 7 * 256 // 16,
        "terms": [
            {"dx": -1, "dy": 1, "dl": 3 * 256 // 16},
            {"dx": 0, "dy": 1, "dl": 5 * 256 // 16},
            {"dx": 1, "dy": 1, "dl": 1 * 256 // 16},
        ],
    }

    algorithm_map = {Atkinson: atkinson, FloydStenberg: floyd_stenberg}


def dither(dest_bitmap, source_bitmap, colorspace, algorithm=DitherAlgorithm.Atkinson):
    """Convert the input image into a 2-level output image using the given dither algorithm.

    :param bitmap dest_bitmap: Destination bitmap.  It must have
      a value_count of 2 or 65536.  The stored values are 0 and the maximum pixel value.
    :param bitmap source_bitmap: Source bitmap that contains the
      graphical region to be dithered.  It must have a value_count of 65536.
    :param colorspace: The colorspace of the image.  The supported colorspaces
      are ``RGB565``, ``BGR565``, ``RGB565_SWAPPED``, and ``BGR565_SWAPPED``
    :param algorithm: The dither algorithm to use, one of the `DitherAlgorithm` values.
    """
    SWAP_BYTES = 1 << 0
    SWAP_RB = 1 << 1
    height, width = dest_bitmap.width, dest_bitmap.height
    swap_bytes = colorspace in (Colorspace.RGB565_SWAPPED, Colorspace.BGR565_SWAPPED)
    swap_rb = colorspace in (Colorspace.BGR565, Colorspace.BGR565_SWAPPED)
    algorithm_info = DitherAlgorithm.algorithm_map[algorithm]
    mx = algorithm_info["mx"]
    count = algorithm_info["count"]
    terms = algorithm_info["terms"]
    dl = algorithm_info["dl"]

    swap = 0
    if swap_bytes:
        swap |= SWAP_BYTES

    if swap_rb:
        swap |= SWAP_RB

    print(f"swap: {swap}")

    # Create row data arrays (3 rows with padding on both sides)
    rowdata = [[0] * (width + 2 * mx) for _ in range(3)]
    rows = [rowdata[0][mx:], rowdata[1][mx:], rowdata[2][mx:]]

    # Output array for one row at a time (padded to multiple of 32)
    out = [False] * (((width + 31) // 32) * 32)

    # Helper function to fill a row with luminance data
    def fill_row(bitmap, swap, luminance_data, y, mx):
        if y >= bitmap.height:
            return

        # Zero out padding area
        for i in range(mx):
            luminance_data[-mx + i] = 0
            luminance_data[bitmap.width + i] = 0

        if bitmap._bits_per_value == 8:  # pylint: disable=protected-access
            for x in range(bitmap.width):
                luminance_data[x] = bitmap[x, y]
        else:
            for x in range(bitmap.width):
                pixel = bitmap[x, y]
                if swap & SWAP_BYTES:
                    # Swap bytes (equivalent to __builtin_bswap16)
                    pixel = ((pixel & 0xFF) << 8) | ((pixel >> 8) & 0xFF)

                r = (pixel >> 8) & 0xF8
                g = (pixel >> 3) & 0xFC
                b = (pixel << 3) & 0xF8

                if swap & SWAP_BYTES:
                    r, b = b, r

                # Calculate luminance using same formula as C version
                luminance_data[x] = (r * 78 + g * 154 + b * 29) // 256

    # Helper function to write pixels to destination bitmap
    def write_pixels(bitmap, y, data):
        if bitmap._bits_per_value == 1:  # pylint: disable=protected-access
            for i in range(0, bitmap.width, 32):
                # Pack 32 bits into an integer
                p = 0
                for j in range(min(32, bitmap.width - i)):
                    p = p << 1
                    if data[i + j]:
                        p |= 1

                # Write packed value
                for j in range(min(32, bitmap.width - i)):
                    bitmap[i + j, y] = (p >> (31 - j)) & 1
        else:
            for i in range(bitmap.width):
                bitmap[i, y] = 65535 if data[i] else 0

    # Fill initial rows
    fill_row(source_bitmap, swap, rows[0], 0, mx)
    fill_row(source_bitmap, swap, rows[1], 1, mx)
    fill_row(source_bitmap, swap, rows[2], 2, mx)

    err = 0

    for y in range(height):
        # Going left to right
        for x in range(width):
            pixel_in = rows[0][x] + err
            pixel_out = pixel_in >= 128
            out[x] = pixel_out

            err = pixel_in - (255 if pixel_out else 0)

            # Distribute error to neighboring pixels
            for i in range(count):
                x1 = x + terms[i]["dx"]
                dy = terms[i]["dy"]

                rows[dy][x1] = ((terms[i]["dl"] * err) // 256) + rows[dy][x1]

            err = (err * dl) // 256

        write_pixels(dest_bitmap, y, out)

        # Cycle the rows
        rows[0], rows[1], rows[2] = rows[1], rows[2], rows[0]

        y += 1
        if y == height:
            break

        # Fill the next row for future processing
        fill_row(source_bitmap, swap, rows[2], y + 2, mx)

        # Going right to left
        for x in range(width - 1, -1, -1):
            pixel_in = rows[0][x] + err
            pixel_out = pixel_in >= 128
            out[x] = pixel_out

            err = pixel_in - (255 if pixel_out else 0)

            # Distribute error to neighboring pixels (in reverse direction)
            for i in range(count):
                x1 = x - terms[i]["dx"]
                dy = terms[i]["dy"]

                rows[dy][x1] = ((terms[i]["dl"] * err) // 256) + rows[dy][x1]

            err = (err * dl) // 256

        write_pixels(dest_bitmap, y, out)

        # Cycle the rows again
        rows[0], rows[1], rows[2] = rows[1], rows[2], rows[0]

        # Fill the next row for future processing
        fill_row(source_bitmap, swap, rows[2], y + 3, mx)


def boundary_fill(
    dest_bitmap: Bitmap,
    x: int,
    y: int,
    fill_color_value: int,
    replaced_color_value: Optional[int] = None,
):
    """Draws the color value into the destination bitmap enclosed
    area of pixels of the background_value color. Like "Paint Bucket"
    fill tool.

    :param bitmap dest_bitmap: Destination bitmap that will be written into
    :param int x: x-pixel position of the first pixel to check and fill if needed
    :param int y: y-pixel position of the first pixel to check and fill if needed
    :param int fill_color_value: Bitmap palette index that will be written into the
           enclosed area in the destination bitmap
    :param int replaced_color_value: Bitmap palette index that will filled with the
           value color in the enclosed area in the destination bitmap"""
    if fill_color_value == replaced_color_value:
        return
    if replaced_color_value == -1:
        replaced_color_value = dest_bitmap[x, y]

    fill_points = []
    fill_points.append((x, y))

    seen_points = []
    minx = x
    miny = y
    maxx = x
    maxy = y

    while len(fill_points) > 0:
        cur_point = fill_points.pop(0)
        seen_points.append(cur_point)
        cur_x = cur_point[0]
        cur_y = cur_point[1]

        cur_point_color = dest_bitmap[cur_x, cur_y]
        if replaced_color_value is not None and cur_point_color != replaced_color_value:
            continue
        if cur_x < minx:
            minx = cur_x
        if cur_y < miny:
            miny = cur_y
        if cur_x > maxx:
            maxx = cur_x
        if cur_y > maxy:
            maxy = cur_y

        dest_bitmap[cur_x, cur_y] = fill_color_value

        above_point = (cur_x, cur_y - 1)
        below_point = (cur_x, cur_y + 1)
        left_point = (cur_x - 1, cur_y)
        right_point = (cur_x + 1, cur_y)

        if (
            above_point[1] >= 0
            and above_point not in seen_points
            and above_point not in fill_points
        ):
            fill_points.append(above_point)
        if (
            below_point[1] < dest_bitmap.height
            and below_point not in seen_points
            and below_point not in fill_points
        ):
            fill_points.append(below_point)
        if (
            left_point[0] >= 0
            and left_point not in seen_points
            and left_point not in fill_points
        ):
            fill_points.append(left_point)
        if (
            right_point[0] < dest_bitmap.width
            and right_point not in seen_points
            and right_point not in fill_points
        ):
            fill_points.append(right_point)
