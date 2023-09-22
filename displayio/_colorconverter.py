# SPDX-FileCopyrightText: 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`displayio.colorconverter`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

from ._colorspace import Colorspace
from ._structs import ColorspaceStruct, InputPixelStruct, OutputPixelStruct
from ._helpers import clamp, bswap16


class ColorConverter:
    """Converts one color format to another. Color converter based on original displayio
    code for consistency.
    """

    def __init__(
        self, *, input_colorspace: Colorspace = Colorspace.RGB888, dither: bool = False
    ):
        """Create a ColorConverter object to convert color formats.
        Only supports rgb888 to RGB565 currently.
        :param bool dither: Adds random noise to dither the output image
        """
        self._dither = dither
        self._transparent_color = None
        self._rgba = False  # Todo set Output colorspace depth to 32 maybe?
        self._input_colorspace = input_colorspace
        self._output_colorspace = ColorspaceStruct(16)
        self._cached_colorspace = None
        self._cached_input_pixel = None
        self._cached_output_color = None
        self._needs_refresh = False

    @staticmethod
    def _dither_noise_1(noise):
        noise = (noise >> 13) ^ noise
        more_noise = (
            noise * (noise * noise * 60493 + 19990303) + 1376312589
        ) & 0x7FFFFFFF
        return clamp(int((more_noise / (1073741824.0 * 2)) * 255), 0, 0xFFFFFFFF)

    @staticmethod
    def _dither_noise_2(x, y):
        return ColorConverter._dither_noise_1(x + y * 0xFFFF)

    @staticmethod
    def _compute_rgb565(color_rgb888: int):
        red5 = color_rgb888 >> 19
        grn6 = (color_rgb888 >> 10) & 0x3F
        blu5 = (color_rgb888 >> 3) & 0x1F
        return red5 << 11 | grn6 << 5 | blu5

    @staticmethod
    def _compute_rgb332(color_rgb888: int):
        red3 = color_rgb888 >> 21
        grn2 = (color_rgb888 >> 13) & 0x7
        blu2 = (color_rgb888 >> 6) & 0x3
        return red3 << 5 | grn2 << 3 | blu2

    @staticmethod
    def _compute_rgbd(color_rgb888: int):
        red1 = (color_rgb888 >> 23) & 0x1
        grn1 = (color_rgb888 >> 15) & 0x1
        blu1 = (color_rgb888 >> 7) & 0x1
        return red1 << 3 | grn1 << 2 | blu1 << 1  # | dummy

    @staticmethod
    def _compute_luma(color_rgb888: int):
        red8 = color_rgb888 >> 16
        grn8 = (color_rgb888 >> 8) & 0xFF
        blu8 = color_rgb888 & 0xFF
        return (red8 * 19 + grn8 * 182 + blu8 + 54) // 255

    @staticmethod
    def _compute_chroma(color_rgb888: int):
        red8 = color_rgb888 >> 16
        grn8 = (color_rgb888 >> 8) & 0xFF
        blu8 = color_rgb888 & 0xFF
        return max(red8, grn8, blu8) - min(red8, grn8, blu8)

    @staticmethod
    def _compute_hue(color_rgb888: int):
        red8 = color_rgb888 >> 16
        grn8 = (color_rgb888 >> 8) & 0xFF
        blu8 = color_rgb888 & 0xFF
        max_color = max(red8, grn8, blu8)
        chroma = max_color - min(red8, grn8, blu8)
        if chroma == 0:
            return 0
        hue = 0
        if max_color == red8:
            hue = (((grn8 - blu8) * 40) // chroma) % 240
        elif max_color == grn8:
            hue = (((blu8 - red8) + (2 * chroma)) * 40) // chroma
        elif max_color == blu8:
            hue = (((red8 - grn8) + (4 * chroma)) * 40) // chroma
        if hue < 0:
            hue += 240

        return hue

    @staticmethod
    def _compute_sevencolor(color_rgb888: int):
        # pylint: disable=too-many-return-statements
        chroma = ColorConverter._compute_chroma(color_rgb888)
        if chroma >= 64:
            hue = ColorConverter._compute_hue(color_rgb888)
            # Red 0
            if hue < 10:
                return 0x4
            # Orange 21
            if hue < 21 + 10:
                return 0x6
            # Yellow 42
            if hue < 42 + 21:
                return 0x5
            # Green 85
            if hue < 85 + 42:
                return 0x2
            # Blue 170
            if hue < 170 + 42:
                return 0x3
            # The rest is red to 255
            return 0x4
        luma = ColorConverter._compute_luma(color_rgb888)
        if luma >= 128:
            return 0x1  # White
        return 0x0  # Black

    @staticmethod
    def _compute_tricolor(
        colorspace: ColorspaceStruct, pixel_hue: int, color: int
    ) -> int:
        hue_diff = colorspace.tricolor_hue - pixel_hue
        if -10 <= hue_diff <= 10 or hue_diff <= -220 or hue_diff >= 220:
            if colorspace.grayscale:
                color = 0
            else:
                color = 1
        elif not colorspace.grayscale:
            color = 0
        return color

    def convert(self, color: int) -> int:
        "Converts the given rgb888 color to RGB565"
        if isinstance(color, int):
            color = ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF, 255)
        elif isinstance(color, tuple):
            if len(color) == 3:
                color = (color[0], color[1], color[2], 255)
            elif len(color) != 4:
                raise ValueError("Color must be a 3 or 4 value tuple")
        else:
            raise ValueError("Color must be an integer or 3 or 4 value tuple")

        input_pixel = InputPixelStruct(color)
        output_pixel = OutputPixelStruct()

        self._convert(self._output_colorspace, input_pixel, output_pixel)

        return output_pixel.pixel

    def _convert(
        self,
        colorspace: Colorspace,
        input_pixel: InputPixelStruct,
        output_color: OutputPixelStruct,
    ) -> None:
        pixel = input_pixel.pixel

        if self._transparent_color == pixel:
            output_color.opaque = False
            return

        if (
            not self._dither
            and self._cached_colorspace == self._output_colorspace
            and self._cached_input_pixel == input_pixel.pixel
        ):
            output_color = self._cached_output_color
            return

        rgb888_pixel = input_pixel
        rgb888_pixel.pixel = self._convert_pixel(
            self._input_colorspace, input_pixel.pixel
        )
        self._convert_color(colorspace, self._dither, rgb888_pixel, output_color)

        if not self._dither:
            self._cached_colorspace = colorspace
            self._cached_input_pixel = input_pixel.pixel
            self._cached_output_color = output_color.pixel

    @staticmethod
    def _convert_pixel(colorspace: Colorspace, pixel: int) -> int:
        pixel = clamp(pixel, 0, 0xFFFFFFFF)
        if colorspace in (
            Colorspace.RGB565_SWAPPED,
            Colorspace.RGB555_SWAPPED,
            Colorspace.BGR565_SWAPPED,
            Colorspace.BGR555_SWAPPED,
        ):
            pixel = bswap16(pixel)
        if colorspace in (Colorspace.RGB565, Colorspace.RGB565_SWAPPED):
            red8 = (pixel >> 11) << 3
            grn8 = ((pixel >> 5) << 2) & 0xFF
            blu8 = (pixel << 3) & 0xFF
            return (red8 << 16) | (grn8 << 8) | blu8
        if colorspace in (Colorspace.RGB555, Colorspace.RGB555_SWAPPED):
            red8 = (pixel >> 10) << 3
            grn8 = ((pixel >> 5) << 3) & 0xFF
            blu8 = (pixel << 3) & 0xFF
            return (red8 << 16) | (grn8 << 8) | blu8
        if colorspace in (Colorspace.BGR565, Colorspace.BGR565_SWAPPED):
            blu8 = (pixel >> 11) << 3
            grn8 = ((pixel >> 5) << 2) & 0xFF
            red8 = (pixel << 3) & 0xFF
            return (red8 << 16) | (grn8 << 8) | blu8
        if colorspace in (Colorspace.BGR555, Colorspace.BGR555_SWAPPED):
            blu8 = (pixel >> 10) << 3
            grn8 = ((pixel >> 5) << 3) & 0xFF
            red8 = (pixel << 3) & 0xFF
            return (red8 << 16) | (grn8 << 8) | blu8
        if colorspace == Colorspace.L8:
            return (pixel & 0xFF) & 0x01010101
        return pixel

    @staticmethod
    def _convert_color(
        colorspace: ColorspaceStruct,
        dither: bool,
        input_pixel: InputPixelStruct,
        output_color: OutputPixelStruct,
    ) -> None:
        # pylint: disable=too-many-return-statements, too-many-branches, too-many-statements
        pixel = input_pixel.pixel
        if dither:
            rand_red = ColorConverter._dither_noise_2(input_pixel.x, input_pixel.y)
            rand_grn = ColorConverter._dither_noise_2(input_pixel.x + 33, input_pixel.y)
            rand_blu = ColorConverter._dither_noise_2(input_pixel.x, input_pixel.y + 33)

            red8 = pixel >> 16
            grn8 = (pixel >> 8) & 0xFF
            blu8 = pixel & 0xFF

            if colorspace.depth == 16:
                blu8 = min(255, blu8 + (rand_blu & 0x07))
                red8 = min(255, red8 + (rand_red & 0x07))
                grn8 = min(255, grn8 + (rand_grn & 0x03))
            else:
                bitmask = 0xFF >> colorspace.depth
                blu8 = min(255, blu8 + (rand_blu & bitmask))
                red8 = min(255, red8 + (rand_red & bitmask))
                grn8 = min(255, grn8 + (rand_grn & bitmask))
            pixel = (red8 << 16) | (grn8 << 8) | blu8

        if colorspace.depth == 16:
            packed = ColorConverter._compute_rgb565(pixel)
            if colorspace.reverse_bytes_in_word:
                packed = bswap16(packed)
            output_color.pixel = packed
            output_color.opaque = True
            return
        if colorspace.tricolor:
            output_color.pixel = ColorConverter._compute_luma(pixel) >> (
                8 - colorspace.depth
            )
            if ColorConverter._compute_chroma(pixel) <= 16:
                if not colorspace.grayscale:
                    output_color.pixel = 0
                output_color.opaque = True
                return
            pixel_hue = ColorConverter._compute_hue(pixel)
            output_color.pixel = ColorConverter._compute_tricolor(
                colorspace, pixel_hue, output_color.pixel
            )
            return
        if colorspace.grayscale and colorspace.depth <= 8:
            bitmask = (1 << colorspace.depth) - 1
            output_color.pixel = (
                ColorConverter._compute_luma(pixel) >> colorspace.grayscale_bit
            ) & bitmask
            output_color.opaque = True
            return
        if colorspace.depth == 32:
            output_color.pixel = pixel
            output_color.opaque = True
            return
        if colorspace.depth == 8 and colorspace.grayscale:
            packed = ColorConverter._compute_rgb332(pixel)
            output_color.pixel = packed
            output_color.opaque = True
            return
        if colorspace.depth == 4:
            if colorspace.sevencolor:
                packed = ColorConverter._compute_sevencolor(pixel)
            else:
                packed = ColorConverter._compute_rgbd(pixel)
            output_color.pixel = packed
            output_color.opaque = True
            return
        output_color.opaque = False

    def make_transparent(self, color: int) -> None:
        """Set the transparent color or index for the ColorConverter. This will
        raise an Exception if there is already a selected transparent index.
        """
        self._transparent_color = color

    def make_opaque(self, _color: int) -> None:
        """Make the ColorConverter be opaque and have no transparent pixels."""
        self._transparent_color = None

    @property
    def dither(self) -> bool:
        """When true the color converter dithers the output by adding
        random noise when truncating to display bitdepth
        """
        return self._dither

    @dither.setter
    def dither(self, value: bool):
        if not isinstance(value, bool):
            raise ValueError("Value should be boolean")
        self._dither = value
