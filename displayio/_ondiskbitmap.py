# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
# SPDX-FileCopyrightText: 2021 James Carr
#
# SPDX-License-Identifier: MIT

"""
`displayio.ondiskbitmap`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams, James Carr

"""

from typing import Union, BinaryIO
from ._colorconverter import ColorConverter
from ._palette import Palette

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"


def _read_uint32(buffer: bytes, idx: int) -> int:
    return (
        buffer[idx]
        | buffer[idx + 1] << 8
        | buffer[idx + 2] << 16
        | buffer[idx + 3] << 24
    )


def _read_word(header: bytes, idx: int) -> int:
    return _read_uint32(header, idx * 2)


class OnDiskBitmap:
    # pylint: disable=too-many-instance-attributes
    """
    Loads values straight from disk. This minimizes memory use but can lead to much slower pixel
    load times. These load times may result in frame tearing where only part of the image is
    visible.

    It's easiest to use on a board with a built in display such as the `Hallowing M0 Express
    <https://www.adafruit.com/product/3900>`_.

    .. code-block:: Python

        import board
        import displayio
        import time
        import pulseio

        board.DISPLAY.auto_brightness = False
        board.DISPLAY.brightness = 0
        splash = displayio.Group()
        board.DISPLAY.show(splash)

        odb = displayio.OnDiskBitmap(\'/sample.bmp\')
        face = displayio.TileGrid(odb, pixel_shader=odb.pixel_shader)
        splash.append(face)
        # Wait for the image to load.
        board.DISPLAY.refresh(target_frames_per_second=60)

        # Fade up the backlight
        for i in range(100):
          board.DISPLAY.brightness = 0.01 * i
          time.sleep(0.05)

        # Wait forever
        while True:
          pass

    """

    def __init__(self, file: Union[str, BinaryIO]) -> None:
        # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        """
        Create an OnDiskBitmap object with the given file.

        :param file file: The name of the bitmap file. For backwards compatibility, a file opened
            in binary mode may also be passed.

        Older versions of CircuitPython required a file opened in binary mode. CircuitPython 7.0
        modified OnDiskBitmap so that it takes a filename instead, and opens the file internally.
        A future version of CircuitPython will remove the ability to pass in an opened file.
        """

        if isinstance(file, str):
            file = open(file, "rb")  # pylint: disable=consider-using-with

        if not (file.readable() and file.seekable()):
            raise TypeError("file must be a file opened in byte mode")

        self._pixel_shader_base: Union[ColorConverter, Palette, None] = None

        try:
            self._file = file
            file.seek(0)
            bmp_header = file.read(138)

            if len(bmp_header) != 138 or bmp_header[0:2] != b"BM":
                raise ValueError("Invalid BMP file")

            self._data_offset = _read_word(bmp_header, 5)

            header_size = _read_word(bmp_header, 7)
            bits_per_pixel = bmp_header[14 * 2] | bmp_header[14 * 2 + 1] << 8
            compression = _read_word(bmp_header, 15)
            number_of_colors = _read_word(bmp_header, 23)

            indexed = bits_per_pixel <= 8
            self._bitfield_compressed = compression == 3
            self._bits_per_pixel = bits_per_pixel
            self._width = _read_word(bmp_header, 9)
            self._height = _read_word(bmp_header, 11)

            self._colorconverter = ColorConverter()

            if bits_per_pixel == 16:
                if header_size >= 56 or self._bitfield_compressed:
                    self._r_bitmask = _read_word(bmp_header, 27)
                    self._g_bitmask = _read_word(bmp_header, 29)
                    self._b_bitmask = _read_word(bmp_header, 31)
                else:
                    # No compression or short header mean 5:5:5
                    self._r_bitmask = 0x7C00
                    self._g_bitmask = 0x03E0
                    self._b_bitmask = 0x001F
            elif indexed:
                if number_of_colors == 0:
                    number_of_colors = 1 << bits_per_pixel

                palette = Palette(number_of_colors)

                if number_of_colors > 1:
                    palette_size = number_of_colors * 4
                    palette_offset = 0xE + header_size

                    file.seek(palette_offset)

                    palette_data = file.read(palette_size)
                    if len(palette_data) != palette_size:
                        raise ValueError("Unable to read color palette data")

                    for i in range(number_of_colors):
                        palette[i] = _read_uint32(palette_data, i * 4)
                else:
                    palette[0] = 0x000000
                    palette[1] = 0xFFFFFF
                self._palette = palette
            elif header_size not in (12, 40, 108, 124):
                raise ValueError(
                    "Only Windows format, uncompressed BMP supported: "
                    f"given header size is {header_size}"
                )

            if bits_per_pixel == 8 and number_of_colors == 0:
                raise ValueError(
                    "Only monochrome, indexed 4bpp or 8bpp, and 16bpp or greater BMPs supported: "
                    f"{bits_per_pixel} bpp given"
                )

            bytes_per_pixel = (
                self._bits_per_pixel // 8 if (self._bits_per_pixel // 8) else 1
            )
            pixels_per_byte = 8 // self._bits_per_pixel
            if pixels_per_byte == 0:
                self._stride = self._width * bytes_per_pixel
                if self._stride % 4 != 0:
                    self._stride += 4 - self._stride % 4
            else:
                bit_stride = self._width * self._bits_per_pixel
                if bit_stride % 32 != 0:
                    bit_stride += 32 - bit_stride % 32
                self._stride = bit_stride // 8
        except IOError as error:
            raise OSError from error

    @property
    def width(self) -> int:
        """
        Width of the bitmap. (read only)

        :type: int
        """

        return self._width

    @property
    def height(self) -> int:
        """
        Height of the bitmap. (read only)

        :type: int
        """

        return self._height

    @property
    def pixel_shader(self) -> Union[ColorConverter, Palette]:
        """
        The image's pixel_shader. The type depends on the underlying `Bitmap`'s structure. The
        pixel shader can be modified (e.g., to set the transparent pixel or, for paletted images,
        to update the palette)

        :type: Union[ColorConverter, Palette]
        """

        return self._pixel_shader_base

    @property
    def _colorconverter(self) -> ColorConverter:
        return self._pixel_shader_base

    @_colorconverter.setter
    def _colorconverter(self, colorconverter: ColorConverter) -> None:
        self._pixel_shader_base = colorconverter

    @property
    def _palette(self) -> Palette:
        return self._pixel_shader_base

    @_palette.setter
    def _palette(self, palette: Palette) -> None:
        self._pixel_shader_base = palette

    def _get_pixel(self, x: int, y: int) -> int:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return 0

        bytes_per_pixel = (
            self._bits_per_pixel // 8 if (self._bits_per_pixel // 8) else 1
        )
        pixels_per_byte = 8 // self._bits_per_pixel
        if pixels_per_byte == 0:
            location = (
                self._data_offset
                + (self.height - y - 1) * self._stride
                + x * bytes_per_pixel
            )
        else:
            location = (
                self._data_offset
                + (self.height - y - 1) * self._stride
                + x // pixels_per_byte
            )

        self._file.seek(location)

        pixel_data = self._file.read(bytes_per_pixel)
        if len(pixel_data) == bytes_per_pixel:
            if bytes_per_pixel == 1:
                offset = (x % pixels_per_byte) * self._bits_per_pixel
                mask = (1 << self._bits_per_pixel) - 1
                return (pixel_data[0] >> ((8 - self._bits_per_pixel) - offset)) & mask
            if bytes_per_pixel == 2:
                pixel_data = pixel_data[0] | pixel_data[1] << 8
                if self._g_bitmask == 0x07E0:  # 565
                    red = (pixel_data & self._r_bitmask) >> 11
                    green = (pixel_data & self._g_bitmask) >> 5
                    blue = pixel_data & self._b_bitmask
                else:  # 555
                    red = (pixel_data & self._r_bitmask) >> 10
                    green = (pixel_data & self._g_bitmask) >> 4
                    blue = pixel_data & self._b_bitmask
                return red << 19 | green << 10 | blue << 3
            if bytes_per_pixel == 4 and self._bitfield_compressed:
                return pixel_data[0] | pixel_data[1] << 8 | pixel_data[2] << 16

            pixel = pixel_data[0] | pixel_data[1] << 8 | pixel_data[2] << 16
            if bytes_per_pixel == 4:
                pixel |= pixel_data[3] << 24
            return pixel
        return 0

    def _finish_refresh(self) -> None:
        pass
