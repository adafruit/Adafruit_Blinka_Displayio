from displayio import Bitmap
import circuitpython_typing

def fill_region(dest_bitmap: Bitmap, x1: int, y1: int, x2: int, y2: int, value: int):
    for y in range(y1, y2):
        for x in range(x1, x2):
            dest_bitmap[x,y] = value

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

    for i in range(len(xs)-1):
        cur_point = (xs[i], ys[i])
        next_point = (xs[i+1], ys[i+1])
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
                    if (skip_dest_index is None) or (dest_bitmap[y_placement * dest_bitmap.width + x_placement] != skip_dest_index):
                        dest_bitmap[  # Direct index into a bitmap array is speedier than [x,y] tuple
                            y_placement * dest_bitmap.width + x_placement
                        ] = this_pixel_color
            elif y_placement > dest_bitmap.height:
                break