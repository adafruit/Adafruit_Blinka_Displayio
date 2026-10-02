# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""Pixel values that do not fit a Bitmap, and integer-like values that do.

Run with ``python -m pytest tests``. The NumPy cases are skipped without NumPy.
"""

import bitmaptools
import displayio

try:
    import numpy
except ImportError:
    numpy = None

DEPTHS = ((4, 16), (8, 256), (16, 65536))


class Index:
    """An integer-like object that only implements __index__."""

    def __init__(self, value):
        self.value = value

    def __index__(self):
        return self.value


def raises(exception, func, *args):
    """Return the message of the exception func raises, failing if it raises none."""
    try:
        func(*args)
    except exception as ex:
        return str(ex)
    raise AssertionError(f"{func.__name__} did not raise {exception.__name__}")


def set_pixel(bitmap, value):
    bitmap[0, 0] = value


def check_stores_12(value):
    for _, count in DEPTHS:
        bitmap = displayio.Bitmap(2, 2, count)
        set_pixel(bitmap, value)
        assert bitmap[0, 0] == 12
        bitmap = displayio.Bitmap(2, 2, count)
        bitmaptools.fill_region(bitmap, 0, 0, 2, 2, value)
        assert bitmap[1, 1] == 12


def test_int_and_index_values():
    check_stores_12(12)
    check_stores_12(Index(12))


def test_numpy_values():
    if numpy is None:
        return
    for value in (numpy.uint8(12), numpy.uint16(12), numpy.int64(12)):
        check_stores_12(value)


def test_bool_value():
    bitmap = displayio.Bitmap(2, 2, 256)
    set_pixel(bitmap, True)
    assert bitmap[0, 0] == 1


def test_float_refused():
    for _, count in DEPTHS:
        bitmap = displayio.Bitmap(2, 2, count)
        raises(TypeError, set_pixel, bitmap, 12.0)
        raises(TypeError, bitmaptools.fill_region, bitmap, 0, 0, 2, 2, 12.0)


def test_out_of_range_raises():
    for count, top in ((256, 255), (65536, 65535)):
        bitmap = displayio.Bitmap(2, 2, count)
        for value in (top + 1, -1):
            assert (
                raises(ValueError, set_pixel, bitmap, value) == f"value must be 0-{top}"
            )
            assert (
                raises(ValueError, bitmaptools.fill_region, bitmap, 0, 0, 2, 2, value)
                == "out of range of target"
            )
        assert bitmap[0, 0] == 0


def test_under_8_bits_still_masks():
    bitmap = displayio.Bitmap(2, 2, 16)
    set_pixel(bitmap, 17)
    assert bitmap[0, 0] == 1
    bitmap.fill(16)
    assert bitmap[1, 1] == 0


def test_copies_truncate():
    source = displayio.Bitmap(2, 2, 65536)
    source.fill(256 + 7)
    for copy in (
        lambda dest: bitmaptools.blit(dest, source, 0, 0),
        lambda dest: bitmaptools.rotozoom(dest, source),
    ):
        dest = displayio.Bitmap(2, 2, 256)
        copy(dest)
        assert dest[0, 0] == 7
