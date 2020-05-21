"""
`displayio`
"""

import os
import digitalio
import time
import struct
import numpy
from collections import namedtuple
from PIL import Image, ImageDraw, ImagePalette

"""
import asyncio
import signal
import subprocess
"""

# Don't import pillow if we're running in the CI. We could mock it out but that
# would require mocking in all reverse dependencies.
if "GITHUB_ACTION" not in os.environ and "READTHEDOCS" not in os.environ:
    # This will only work on Linux
    pass
else:
    # this would be for Github Actions
    utils = None  # pylint: disable=invalid-name

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

_displays = []
_groups = []

Rectangle = namedtuple("Rectangle", "x1 y1 x2 y2")

class _DisplayioSingleton:
    def __init__(self):
        pass


def release_displays():
    """Releases any actively used displays so their busses and pins can be used again.

    Use this once in your code.py if you initialize a display. Place it right before the initialization so the display is active as long as possible.
    """
    for _disp in _displays:
        _disp._release()
    _displays.clear()


class Bitmap:
    """Stores values of a certain size in a 2D array"""

    def __init__(self, width, height, value_count):
        """Create a Bitmap object with the given fixed size. Each pixel stores a value that is used to index into a corresponding palette. This enables differently colored sprites to share the underlying Bitmap. value_count is used to minimize the memory used to store the Bitmap.
        """
        self._width = width
        self._height = height
        self._read_only = False

        if value_count < 0:
            raise ValueError("value_count must be > 0")

        bits = 1
        while (value_count - 1) >> bits:
            if bits < 8:
                bits = bits << 1
            else:
                bits += 8

        self._bits_per_value = bits

        if (
            self._bits_per_value > 8
            and self._bits_per_value != 16
            and self._bits_per_value != 32
        ):
            raise NotImplementedError("Invalid bits per value")

        self._data = (width * height) * [0]
        self._dirty_area = Rectangle(0, 0, width, height)

    def __getitem__(self, index):
        """
        Returns the value at the given index. The index can either be
        an x,y tuple or an int equal to `y * width + x`.
        """
        if isinstance(index, (tuple, list)):
            index = index[1] * self._width + index[0]
        return self._data[index]

    def __setitem__(self, index, value):
        """
        Sets the value at the given index. The index can either be
        an x,y tuple or an int equal to `y * width + x`.
        """
        if self._read_only:
            raise RuntimeError("Read-only object")
        if isinstance(index, (tuple, list)):
            x = index[0]
            y = index[1]
            index = y * self._width + x
        elif ininstance(index, int):
            x = index % self._width
            y = index // self._width
        self._data[index] = value
        if self._dirty_area.x1 == self._dirty_area.x2:
            self._dirty_area.x1 = x
            self._dirty_area.x2 = x + 1
            self._dirty_area.y1 = y
            self._dirty_area.y2 = y + 1
        else:
            if x < self._dirty_area.x1:
                self._dirty_area.x1 = x
            elif x >= self._dirty_area.x2:
                self._dirty_area.x2 = x + 1
            if y < self._dirty_area.y1:
                self._dirty_area.y1 = y
            elif y >= self._dirty_area.y2:
                self._dirty_area.y2 = y + 1

    def _finish_refresh(self):
        self._dirty_area.x1 = 0
        self._dirty_area.x2 = 0

    def fill(self, value):
        """Fills the bitmap with the supplied palette index value."""
        self._data = (self._width * self._height) * [value]
        self._dirty_area = Rectangle(0, 0, self._width, self._height)

    @property
    def width(self):
        """Width of the bitmap. (read only)"""
        return self._width

    @property
    def height(self):
        """Height of the bitmap. (read only)"""
        return self._height


class ColorConverter:
    """Converts one color format to another. Color converter based on original displayio
    code for consistency.
    """

    def __init__(self, *, dither=False):
        """Create a ColorConverter object to convert color formats.
        Only supports RGB888 to RGB565 currently.
        :param bool dither: Adds random noise to dither the output image
        """
        self._dither = dither
        self._depth = 16

    def _compute_rgb565(self, color):
        self._depth = 16
        return (color >> 19) << 11 | ((color >> 10) & 0x3F) << 5 | (color >> 3) & 0x1F

    def _compute_luma(self, color):
        r8 = color >> 16
        g8 = (color >> 8) & 0xFF
        b8 = color & 0xFF
        return (r8 * 19) / 255 + (g8 * 182) / 255 + (b8 + 54) / 255

    def _compute_chroma(self, color):
        r8 = color >> 16
        g8 = (color >> 8) & 0xFF
        b8 = color & 0xFF
        return max(r8, g8, b8) - min(r8, g8, b8)

    def _compute_hue(self, color):
        r8 = color >> 16
        g8 = (color >> 8) & 0xFF
        b8 = color & 0xFF
        max_color = max(r8, g8, b8)
        chroma = self._compute_chroma(color)
        if chroma == 0:
            return 0
        hue = 0
        if max_color == r8:
            hue = (((g8 - b8) * 40) / chroma) % 240
        elif max_color == g8:
            hue = (((b8 - r8) + (2 * chroma)) * 40) / chroma
        elif max_color == b8:
            hue = (((r8 - g8) + (4 * chroma)) * 40) / chroma
        if hue < 0:
            hue += 240

        return hue

    def _dither_noise_1(self, noise):
        n = (n >> 13) ^ n
        nn = (n * (n * n * 60493 + 19990303) + 1376312589) & 0x7FFFFFFF
        return (nn / (1073741824.0 * 2)) * 255

    def _dither_noise_2(self, x, y):
        return self._dither_noise_1(x + y * 0xFFFF)

    def _compute_tricolor(self):
        pass

    def convert(self, color):
        "Converts the given RGB888 color to RGB565"
        if self._dither:
            return color  # To Do: return a dithered color
        else:
            return self._compute_rgb565(color)

    @property
    def dither(self):
        "When true the color converter dithers the output by adding random noise when truncating to display bitdepth"
        return self._dither

    @dither.setter
    def dither(self, value):
        if not isinstance(value, bool):
            raise ValueError("Value should be boolean")
        self._dither = value


class Display:
    """This initializes a display and connects it into CircuitPython. Unlike other objects in CircuitPython, Display objects live until ``displayio.release_displays()`` is called. This is done so that CircuitPython can use the display itself.

    Most people should not use this class directly. Use a specific display driver instead that will contain the initialization sequence at minimum.
    
    .. class:: Display(display_bus, init_sequence, *, width, height, colstart=0, rowstart=0, rotation=0, color_depth=16, grayscale=False, pixels_in_byte_share_row=True, bytes_per_cell=1, reverse_pixels_in_byte=False, set_column_command=0x2a, set_row_command=0x2b, write_ram_command=0x2c, set_vertical_scroll=0, backlight_pin=None, brightness_command=None, brightness=1.0, auto_brightness=False, single_byte_bounds=False, data_as_commands=False, auto_refresh=True, native_frames_per_second=60)
    
    """

    def __init__(
        self,
        display_bus,
        init_sequence,
        *,
        width,
        height,
        colstart=0,
        rowstart=0,
        rotation=0,
        color_depth=16,
        grayscale=False,
        pixels_in_byte_share_row=True,
        bytes_per_cell=1,
        reverse_pixels_in_byte=False,
        set_column_command=0x2A,
        set_row_command=0x2B,
        write_ram_command=0x2C,
        set_vertical_scroll=0,
        backlight_pin=None,
        brightness_command=None,
        brightness=1.0,
        auto_brightness=False,
        single_byte_bounds=False,
        data_as_commands=False,
        auto_refresh=True,
        native_frames_per_second=60
    ):
        """Create a Display object on the given display bus (`displayio.FourWire` or `displayio.ParallelBus`).

        The ``init_sequence`` is bitpacked to minimize the ram impact. Every command begins with a command byte followed by a byte to determine the parameter count and if a delay is need after. When the top bit of the second byte is 1, the next byte will be the delay time in milliseconds. The remaining 7 bits are the parameter count excluding any delay byte. The third through final bytes are the remaining command parameters. The next byte will begin a new command definition. Here is a portion of ILI9341 init code:
        .. code-block:: python
        
            init_sequence = (b"\xe1\x0f\x00\x0E\x14\x03\x11\x07\x31\xC1\x48\x08\x0F\x0C\x31\x36\x0F" # Set Gamma
                b"\x11\x80\x78"# Exit Sleep then delay 0x78 (120ms)
                b"\x29\x80\x78"# Display on then delay 0x78 (120ms)
            )
            display = displayio.Display(display_bus, init_sequence, width=320, height=240)
        
        The first command is 0xe1 with 15 (0xf) parameters following. The second and third are 0x11 and 0x29 respectively with delays (0x80) of 120ms (0x78) and no parameters. Multiple byte literals (b”“) are merged together on load. The parens are needed to allow byte literals on subsequent lines.

        The initialization sequence should always leave the display memory access inline with the scan of the display to minimize tearing artifacts.
        """
        self._bus = display_bus
        self._set_column_command = set_column_command
        self._set_row_command = set_row_command
        self._write_ram_command = write_ram_command
        self._brightness_command = brightness_command
        self._data_as_commands = data_as_commands
        self._single_byte_bounds = single_byte_bounds
        self._width = width
        self._height = height
        self._colstart = colstart
        self._rowstart = rowstart
        self._rotation = rotation
        self._auto_brightness = auto_brightness
        self._brightness = brightness
        self._auto_refresh = auto_refresh
        self._initialize(init_sequence)
        self._buffer = Image.new("RGB", (width, height))
        self._subrectangles = []
        self._bounds_encoding = ">BB" if single_byte_bounds else ">HH"
        self._groups = []
        _displays.append(self)
        if self._auto_refresh:
            self.refresh()

    def _initialize(self, init_sequence):
        i = 0
        while i < len(init_sequence):
            command = init_sequence[i]
            data_size = init_sequence[i + 1]
            delay = (data_size & 0x80) > 0
            data_size &= ~0x80
            data_byte = init_sequence[i + 2]
            self._write(command, init_sequence[i + 2 : i + 2 + data_size])
            delay_time_ms = 10
            if delay:
                data_size += 1
                delay_time_ms = init_sequence[i + 1 + data_size]
                if delay_time_ms == 255:
                    delay_time_ms = 500
            time.sleep(delay_time_ms / 1000)
            i += 2 + data_size

    def _write(self, command, data):
        if self._single_byte_bounds:
            self._bus.send(True, bytes([command]) + data, toggle_every_byte=True)
        else:
            self._bus.send(True, bytes([command]), toggle_every_byte=True)
            self._bus.send(False, data)

    def _release(self):
        self._bus.release()
        self._bus = None

    def show(self, group):
        """Switches to displaying the given group of layers. When group is None, the default CircuitPython terminal will be shown.
        """
        self._groups.append(group)

    def _group_to_buffer(self, group):
        """ go through any children and call this function then add group to buffer"""
        for layer_number in range(len(group.layers)):
            layer = group.layers[layer_number]
            if isinstance(layer, Group):
                self._group_to_buffer(layer)
            elif isinstance(layer, TileGrid):
                # Get the TileGrid Info and draw to buffer
                pass
            else:
                raise TypeError("Invalid layer type found in group")

    def refresh(self, *, target_frames_per_second=60, minimum_frames_per_second=1):
        """When auto refresh is off, waits for the target frame rate and then refreshes the display, returning True. If the call has taken too long since the last refresh call for the given target frame rate, then the refresh returns False immediately without updating the screen to hopefully help getting caught up.

        If the time since the last successful refresh is below the minimum frame rate, then an exception will be raised. Set minimum_frames_per_second to 0 to disable.

        When auto refresh is on, updates the display immediately. (The display will also update without calls to this.)
        """
        
        # Go through groups and and add each to buffer
        #for group in self._groups:
            
        
        # Eventually calculate dirty rectangles here
        self._subrectangles.append(Rectangle(0, 0, self._width, self._height))
        
        for area in self._subrectangles:
            self._refresh_display_area(area)
        
        if self._auto_refresh:
            self.refresh()

    def _refresh_display_area(self, rectangle):
        """Loop through dirty rectangles and redraw that area."""
        """Read or write a block of data."""
        data = numpy.array(self._buffer.crop(rectangle).convert("RGB")).astype("uint16")
        color = (
            ((data[:, :, 0] & 0xF8) << 8)
            | ((data[:, :, 1] & 0xFC) << 3)
            | (data[:, :, 2] >> 3)
        )
        
        pixels = list(numpy.dstack(((color >> 8) & 0xFF, color & 0xFF)).flatten().tolist())
        
        self._write(
            self._set_column_command,
            self._encode_pos(rectangle.x1 + self._colstart, rectangle.x2 + self._colstart)
        )
        self._write(
            self._set_row_command,
            self._encode_pos(rectangle.y1 + self._rowstart, rectangle.y2 + self._rowstart)
        )
        self._write(self._write_ram_command, pixels)

    def _encode_pos(self, x, y):
        """Encode a postion into bytes."""
        return struct.pack(self._bounds_encoding, x, y)

    def fill_row(self, y, buffer):
        pass

    @property
    def auto_refresh(self):
        return self._auto_refresh

    @auto_refresh.setter
    def auto_refresh(self, value):
        self._auto_refresh = value

    @property
    def brightness(self):
        """The brightness of the display as a float. 0.0 is off and 1.0 is full `brightness`. When `auto_brightness` is True, the value of `brightness` will change automatically. If `brightness` is set, `auto_brightness` will be disabled and will be set to False.
        """
        return self._brightness

    @brightness.setter
    def brightness(self, value):
        self._brightness = value

    @property
    def auto_brightness(self):
        """True when the display brightness is adjusted automatically, based on an ambient light sensor or other method. Note that some displays may have this set to True by default, but not actually implement automatic brightness adjustment. `auto_brightness` is set to False if `brightness` is set manually.
        """
        return self._auto_brightness

    @auto_brightness.setter
    def auto_brightness(self, value):
        self._auto_brightness = value

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def rotation(self):
        """The rotation of the display as an int in degrees."""
        return self._rotation

    @rotation.setter
    def rotation(self, value):
        if value not in (0, 90, 180, 270):
            raise ValueError("Rotation must be 0/90/180/270")
        self._rotation = value

    @property
    def bus(self):
        return self._bus


class EPaperDisplay:
    def __init__(
        self,
        display_bus,
        start_sequence,
        stop_sequence,
        *,
        width,
        height,
        ram_width,
        ram_height,
        colstart=0,
        rowstart=0,
        rotation=0,
        set_column_window_command=None,
        set_row_window_command=None,
        single_byte_bounds=False,
        write_black_ram_command,
        black_bits_inverted=False,
        write_color_ram_command=None,
        color_bits_inverted=False,
        highlight_color=0x000000,
        refresh_display_command,
        refresh_time=40,
        busy_pin=None,
        busy_state=True,
        seconds_per_frame=180,
        always_toggle_chip_select=False
    ):
        """
        Create a EPaperDisplay object on the given display bus (displayio.FourWire or displayio.ParallelBus).

        The start_sequence and stop_sequence are bitpacked to minimize the ram impact. Every command begins with a command byte followed by a byte to determine the parameter count and if a delay is need after. When the top bit of the second byte is 1, the next byte will be the delay time in milliseconds. The remaining 7 bits are the parameter count excluding any delay byte. The third through final bytes are the remaining command parameters. The next byte will begin a new command definition.
        """
        pass

    def show(self, group):
        """Switches to displaying the given group of layers. When group is None, the default CircuitPython terminal will be shown.
        """
        pass

    def refresh(self):
        """Refreshes the display immediately or raises an exception if too soon. Use ``time.sleep(display.time_to_refresh)`` to sleep until a refresh can occur.
        """
        pass

    @property
    def time_to_refresh(self):
        """Time, in fractional seconds, until the ePaper display can be refreshed."""
        return 0

    @property
    def width(self):
        pass

    @property
    def height(self):
        pass

    @property
    def bus(self):
        pass


class FourWire:
    """Manage updating a display over SPI four wire protocol in the background while
    Python code runs. It doesn’t handle display initialization.
    """

    def __init__(
        self,
        spi_bus,
        *,
        command,
        chip_select,
        reset=None,
        baudrate=24000000,
        polarity=0,
        phase=0
    ):
        """Create a FourWire object associated with the given pins.

        The SPI bus and pins are then in use by the display until displayio.release_displays() is called even after a reload. (It does this so CircuitPython can use the display after your code is done.) So, the first time you initialize a display bus in code.py you should call :py:func`displayio.release_displays` first, otherwise it will error after the first code.py run.
        """
        self._dc = digitalio.DigitalInOut(command)
        self._dc.switch_to_output()
        self._chip_select = digitalio.DigitalInOut(chip_select)
        self._chip_select.switch_to_output(value=True)

        if reset is not None:
            self._reset = digitalio.DigitalInOut(reset)
            self._reset.switch_to_output(value=True)
        else:
            self._reset = None
        self._spi = spi_bus
        while self._spi.try_lock():
            pass
        self._spi.configure(baudrate=baudrate, polarity=polarity, phase=phase)
        self._spi.unlock()

    def _release(self):
        self.reset()
        self._spi.deinit()
        self._dc.deinit()
        self._chip_select.deinit()
        if self._reset is not None:
            self._reset.deinit()

    def reset(self):
        if self._reset is not None:
            self._reset.value = False
            time.sleep(0.001)
            self._reset.value = True
            time.sleep(0.001)

    def send(self, is_command, data, *, toggle_every_byte=False):
        while self._spi.try_lock():
            pass
        self._dc.value = not is_command
        if toggle_every_byte:
            for byte in data:
                self._spi.write(bytes([byte]))
                self._chip_select.value = True
                time.sleep(0.000001)
                self._chip_select.value = False
        else:
            self._spi.write(data)
        self._spi.unlock()


class Group:
    """Manage a group of sprites and groups and how they are inter-related."""

    def __init__(self, *, max_size=4, scale=1, x=0, y=0):
        """Create a Group of a given size and scale. Scale is in
        one dimension. For example, scale=2 leads to a layer’s
        pixel being 2x2 pixels when in the group.
        """
        if not isinstance(max_size, int) or max_size < 1:
            raise ValueError("Max Size must be an integer and >= 1")
        self._max_size = max_size
        if not isinstance(scale, int) or scale < 1:
            raise ValueError("Scale must be an integer and >= 1")
        self._scale = scale
        self._x = x
        self._y = y
        self._hidden = False
        self._layers = []
        self._supported_types = (TileGrid, Group)

    def append(self, layer):
        """Append a layer to the group. It will be drawn
        above other layers.
        """
        if not isinstance(layer, self._supported_types):
            raise ValueError("Invalid Group Memeber")
        if len(self._layers) == self._max_size:
            raise RuntimeError("Group full")
        self._layers.append(layer)

    def insert(self, index, layer):
        """Insert a layer into the group."""
        if not isinstance(layer, self._supported_types):
            raise ValueError("Invalid Group Memeber")
        if len(self._layers) == self._max_size:
            raise RuntimeError("Group full")
        self._layers.insert(index, layer)

    def index(self, layer):
        """Returns the index of the first copy of layer.
        Raises ValueError if not found.
        """
        pass

    def pop(self, index=-1):
        """Remove the ith item and return it."""
        return self._layers.pop(index)

    def remove(self, layer):
        """Remove the first copy of layer. Raises ValueError
        if it is not present."""
        pass

    def __len__(self):
        """Returns the number of layers in a Group"""
        return len(self._layers)

    def __getitem__(self, index):
        """Returns the value at the given index."""
        return self._layers[index]

    def __setitem__(self, index, value):
        """Sets the value at the given index."""
        self._layers[index] = value

    def __delitem__(self, index):
        """Deletes the value at the given index."""
        del self._layers[index]

    @property
    def hidden(self):
        return self._hidden

    @hidden.setter
    def hidden(self, value):
        if not isinstance(value, (bool, int)):
            raise ValueError("Expecting a boolean or integer value")
        self._hidden = bool(value)

    @property
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, value):
        if not isinstance(value, int) or value < 1:
            raise ValueError("Scale must be an integer and at least 1")
        self._scale = value

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        if not isinstance(value, int):
            raise ValueError("x must be an integer")
        self._x = value

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value):
        if not isinstance(value, int):
            raise ValueError("y must be an integer")
        self._y = value


class I2CDisplay:
    """Manage updating a display over I2C in the background while Python code runs. It doesn’t handle display initialization.
    """

    def __init__(self, i2c_bus, *, device_address, reset=None):
        """Create a I2CDisplay object associated with the given I2C bus and reset pin.

        The I2C bus and pins are then in use by the display until displayio.release_displays() is called even after a reload. (It does this so CircuitPython can use the display after your code is done.) So, the first time you initialize a display bus in code.py you should call :py:func`displayio.release_displays` first, otherwise it will error after the first code.py run.
        """
        pass

    def reset(self):
        pass

    def send(self, command, data):
        pass


class OnDisplayBitmap:
    """
    Loads values straight from disk. This minimizes memory use but can lead to much slower pixel load times.
    These load times may result in frame tearing where only part of the image is visible."""

    def __init__(self, file):
        self._image = Image.open(file)

    @property
    def width(self):
        """Width of the bitmap. (read only)"""
        return self._image.width

    @property
    def height(self):
        """Height of the bitmap. (read only)"""
        return self._image.height


class Palette:
    """Map a pixel palette_index to a full color. Colors are transformed to the display’s format internally to save memory."""

    def __init__(self, color_count):
        """Create a Palette object to store a set number of colors."""
        self._needs_refresh = False
        
        self._colors = []
        for _ in range(color_count):
            self._colors.append(self._make_color(0))

    def _make_color(self, value):
        color = {
            "transparent": False,
            "rgb888": 0,
        }
        color_converter = ColorConverter()
        if isinstance(value, (tuple, list, bytes, bytearray)):
            value = (value[0] & 0xFF) << 16 | (value[1] & 0xFF) << 8 | value[2] & 0xFF
        elif isinstance(value, int):
            if not 0 <= value <= 0xFFFFFF:
                raise ValueError("Color must be between 0x000000 and 0xFFFFFF")
        else:
            raise TypeError("Color buffer must be a buffer, tuple, list, or int")
        color["rgb888"] = value
        self._needs_refresh = True

        return color

    def __len__(self):
        """Returns the number of colors in a Palette"""
        return len(self._colors)

    def __setitem__(self, index, value):
        """Sets the pixel color at the given index. The index should be an integer in the range 0 to color_count-1.

        The value argument represents a color, and can be from 0x000000 to 0xFFFFFF (to represent an RGB value). Value can be an int, bytes (3 bytes (RGB) or 4 bytes (RGB + pad byte)), bytearray, or a tuple or list of 3 integers.
        """
        if self._colors[index]["rgb888"] != value:
            self._colors[index] = self._make_color(value)

    def __getitem__(self, index):
        pass

    def make_transparent(self, palette_index):
        self._colors[palette_index].transparent = True

    def make_opaque(self, palette_index):
        self._colors[palette_index].transparent = False

    def _pil_palette(self):
        "Generate a Pillow ImagePalette and return it"
        palette = []
        for channel in range(3):
            for color in self._colors:
                palette.append(color >> (8 * (2 - channel)) & 0xFF)
            
        return ImagePalette(mode='RGB', palette=palette, size=self._color_count)


class ParallelBus:
    """Manage updating a display over 8-bit parallel bus in the background while Python code runs.
    This protocol may be refered to as 8080-I Series Parallel Interface in datasheets.
    It doesn’t handle display initialization.
    """

    def __init__(self, i2c_bus, *, device_address, reset=None):
        """Create a ParallelBus object associated with the given pins. The bus is inferred from data0 by implying the next 7 additional pins on a given GPIO port.

        The parallel bus and pins are then in use by the display until displayio.release_displays() is called even after a reload. (It does this so CircuitPython can use the display after your code is done.) So, the first time you initialize a display bus in code.py you should call :py:func`displayio.release_displays` first, otherwise it will error after the first code.py run.
        """
        pass

    def reset(self):
        """Performs a hardware reset via the reset pin. Raises an exception if called when no reset pin is available.
        """
        pass

    def send(self, command, data):
        """Sends the given command value followed by the full set of data. Display state, such as
        vertical scroll, set via ``send`` may or may not be reset once the code is done.
        """
        pass


class Shape(Bitmap):
    """Create a Shape object with the given fixed size. Each pixel is one bit and is stored by the column
    boundaries of the shape on each row. Each row’s boundary defaults to the full row.
    """

    def __init__(self, width, height, *, mirror_x=False, mirror_y=False):
        """Create a Shape object with the given fixed size. Each pixel is one bit and is stored by the
        column boundaries of the shape on each row. Each row’s boundary defaults to the full row.
        """
        pass

    def set_boundary(self, y, start_x, end_x):
        """Loads pre-packed data into the given row."""
        pass


class TileGrid:
    """Position a grid of tiles sourced from a bitmap and pixel_shader combination. Multiple grids can share bitmaps and pixel shaders.

    A single tile grid is also known as a Sprite.
    """

    def __init__(
        self,
        bitmap,
        *,
        pixel_shader,
        width=1,
        height=1,
        tile_width=None,
        tile_height=None,
        default_tile=0,
        x=0,
        y=0
    ):
        """Create a TileGrid object. The bitmap is source for 2d pixels. The pixel_shader is used to convert the value and its location to a display native pixel color. This may be a simple color palette lookup, a gradient, a pattern or a color transformer.

        tile_width and tile_height match the height of the bitmap by default.
        """
        if not isinstance(bitmap, (Bitmap, OnDiskBitmap, Shape)):
            raise ValueError("Unsupported Bitmap type")
        self._bitmap = bitmap
        bitmap_width = bitmap.width
        bitmap_height = bitmap.height
        
        if not isinstance(pixel_shader, (ColorConverter, Palette)):
            raise ValueError("Unsupported Pixel Shader type")
        self._pixel_shader = pixel_shader
        self_hidden = False
        self._x = x
        self._y = y
        self._width = width # Number of Tiles Wide
        self._height = height # Number of Tiles High
        if tile_width is None:
            tile_width = bitmap_width
        if tile_height is None:
            tile_height = bitmap_height
        if bitmap_width % tile_width != 0:
            raise ValueError("Tile width must exactly divide bitmap width")
        self._tile_width = tile_width
        if bitmap_height % tile_height != 0:
            raise ValueError("Tile height must exactly divide bitmap height")
        self._tile_height = tile_height
        self._tiles = (self._width * self._height) * [default_tile]


    @property
    def hidden(self):
        """True when the TileGrid is hidden. This may be False even when a part of a hidden Group."""
        return self_hidden

    @hidden.setter
    def hidden(self, value):
        self._hidden = value

    @property
    def x(self):
        """X position of the left edge in the parent."""
        return self._x

    @property
    def y(self):
        """Y position of the top edge in the parent."""
        return self._y

    @property
    def flip_x(self):
        """If true, the left edge rendered will be the right edge of the right-most tile."""
        return self._flip_x

    @flip_x.setter
    def flip_x(self, value):
        if not isinstance(value, bool):
            raise TypeError("Flip X should be a boolean type")
        self._flip_x = value

    @property
    def flip_y(self):
        """If true, the top edge rendered will be the bottom edge of the bottom-most tile."""
        return self._flip_y

    @flip_y.setter
    def flip_y(self, value):
        if not isinstance(value, bool):
            raise TypeError("Flip Y should be a boolean type")
        self._flip_y = value

    @property
    def transpose_xy(self):
        """If true, the TileGrid’s axis will be swapped. When combined with mirroring, any 90 degree
        rotation can be achieved along with the corresponding mirrored version.
        """
        return self._transpose_xy

    @transpose_xy.setter
    def transpose_xy(self, value):
        if not isinstance(value, bool):
            raise TypeError("Transpose XY should be a boolean type")
        self._transpose_xy = value

    @property
    def pixel_shader(self):
        """The pixel shader of the tilegrid."""
        pass

    def __getitem__(self, index):
        """Returns the tile index at the given index. The index can either be
        an x,y tuple or an int equal to ``y * width + x``'.
        """
        if isinstance(index, (tuple, list)):
            x = index[0]
            y = index[1]
            index = y * self._width + x
        elif ininstance(index, int):
            x = index % self._width
            y = index // self._width
        if x > self._width or y > self._height:
            raise ValueError("Tile index out of bounds")
        return self._tiles[index]

    def __setitem__(self, index, value):
        """Sets the tile index at the given index. The index can either be
        an x,y tuple or an int equal to ``y * width + x``.
        """
        if isinstance(index, (tuple, list)):
            x = index[0]
            y = index[1]
            index = y * self._width + x
        elif ininstance(index, int):
            x = index % self._width
            y = index // self._width
        if x > width or y > self._height or index > len(self._tiles):
            raise ValueError("Tile index out of bounds")
        if not 0 <= value <= 255:
            raise ValueError("Tile value out of bounds")
        self._tiles[index] = value
