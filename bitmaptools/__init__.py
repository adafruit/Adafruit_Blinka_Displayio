import math
import struct
from typing import Optional, Tuple, BinaryIO
import numpy as np
from displayio import Bitmap, Colorspace
import circuitpython_typing


def fill_region(dest_bitmap: Bitmap, x1: int, y1: int, x2: int, y2: int, value: int):
    for y in range(y1, y2):
        for x in range(x1, x2):
            dest_bitmap[x, y] = value


def draw_line(dest_bitmap: Bitmap, x1: int, y1: int, x2: int, y2: int, value: int):
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
    x2: int | None = None,
    y2: int | None = None,
    skip_source_index: int | None = None,
    skip_dest_index: int | None = None,
):
    """Inserts the source_bitmap region defined by rectangular boundaries"""
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
                        dest_bitmap[  # Direct index into a bitmap array is speedier than [x,y] tuple
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
    if ox is None:
        ox = dest_bitmap.width // 2
    if oy in None:
        oy = dest_bitmap.height // 2

    if dest_clip0 is None:
        dest_clip0 = (0, 0)
    if dest_clip1 is None:
        dest_clip1 = (dest_bitmap.width, dest_bitmap.height)

    if px is None:
        px = source_bitmap.width // 2
    if py in None:
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
    if x2 is None:
        x2 = bitmap.width
    if y2 is None:
        y2 = bitmap.height

    _value_count = 2**bitmap._bits_per_value
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
    width = bitmap.width
    height = bitmap.height
    bits_per_value = bitmap._bits_per_value
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
    """
        colorspace should be one of: 'L8', 'RGB565', 'RGB565_SWAPPED', 'BGR565_SWAPPED'.

    blendmode can be 'normal' (or any default) or 'screen'.

    This assumes that all bitmaps (dest, source1, source2) support 2D access like bitmap[x, y].

    dest.width and dest.height are used; make sure the bitmap objects have these attributes or replace them with your own logic.
    """

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

        if bitmap._bits_per_value == 8:
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
        if bitmap._bits_per_value == 1:
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

    while len(fill_points):
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
