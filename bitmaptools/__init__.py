import math
from typing import Optional, Tuple

from displayio import Bitmap
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


def draw_polygon(dest_bitmap: Bitmap,
                 xs: circuitpython_typing.ReadableBuffer,
                 ys: circuitpython_typing.ReadableBuffer,
                 value: int, close: bool | None = True):
    if len(xs) != len(ys):
        raise ValueError("Length of xs and ys must be equal.")

    for i in range(len(xs) - 1):
        cur_point = (xs[i], ys[i])
        next_point = (xs[i + 1], ys[i + 1])
        print(f"cur: {cur_point}, next: {next_point}")
        draw_line(dest_bitmap=dest_bitmap,
                  x1=cur_point[0], y1=cur_point[1],
                  x2=next_point[0], y2=next_point[1],
                  value=value)

    if close:
        print(f"close: {(xs[0], ys[0])} - {(xs[-1], ys[-1])}")
        draw_line(dest_bitmap=dest_bitmap,
                  x1=xs[0], y1=ys[0],
                  x2=xs[-1], y2=ys[-1],
                  value=value)


def blit(dest_bitmap: Bitmap, source_bitmap: Bitmap,
         x: int, y: int, *,
         x1: int = 0, y1: int = 0,
         x2: int | None = None, y2: int | None = None,
         skip_source_index: int | None = None,
         skip_dest_index: int | None = None):
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

                if (skip_source_index is None) or (this_pixel_color != skip_source_index):
                    if (skip_dest_index is None) or (
                            dest_bitmap[y_placement * dest_bitmap.width + x_placement] != skip_dest_index):
                        dest_bitmap[  # Direct index into a bitmap array is speedier than [x,y] tuple
                            y_placement * dest_bitmap.width + x_placement
                            ] = this_pixel_color
            elif y_placement > dest_bitmap.height:
                break


def rotozoom(
        dest_bitmap,
        source_bitmap,
        *,
        ox: int,
        oy: int,
        dest_clip0: Tuple[int, int],
        dest_clip1: Tuple[int, int],
        px: int,
        py: int,
        source_clip0: Tuple[int, int],
        source_clip1: Tuple[int, int],
        angle: float,
        scale: float,
        skip_index: int,
):
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
            if (source_clip0_x <= u < source_clip1_x) and (source_clip0_y <= v < source_clip1_y):
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
        x1: int = 0, y1: int = 0,
        x2: int | None = None, y2: int | None = None,
        skip_index: int | None = None):

    if x2 is None:
        x2 = bitmap.width
    if y2 is None:
        y2 = bitmap.height

    _value_count = 2 ** bitmap._bits_per_value
    for y in range(y1, y2):
        for x in range(x1, x2):
            i = y * (x2 - x1) + x
            value = int(data[i] % _value_count)
            if skip_index is None or value != skip_index:
                bitmap[x, y] = value
