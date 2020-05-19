"""
`displayio`
"""

import os
import digitalio
import time

"""
import asyncio
import signal
import struct
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

class _DisplayioSingleton():
    def __init__(self):
        pass

def release_displays():
    """Releases any actively used displays so their busses and pins can be used again. This will also release the builtin display on boards that have one. You will need to reinitialize it yourself afterwards.

    Use this once in your code.py if you initialize a display. Place it right before the initialization so the display is active as long as possible.
    """
    _displays.clear()


class Bitmap:
    """Stores values of a certain size in a 2D array"""
    def __init__(self, width, height, value_count):
        """Create a Bitmap object with the given fixed size. Each pixel stores a value that is used to index into a corresponding palette. This enables differently colored sprites to share the underlying Bitmap. value_count is used to minimize the memory used to store the Bitmap.
        """
        pass
        
    def __getitem__(self, index):
        """
        Returns the value at the given index. The index can either be
        an x,y tuple or an int equal to `y * width + x`.
        """
        pass

    def __setitem__(self, index, value):
        """
        Sets the value at the given index. The index can either be
        an x,y tuple or an int equal to `y * width + x`.
        """
        pass
        
    def fill(self, value):
        """Fills the bitmap with the supplied palette index value."""
        pass

    @property
    def width(self):
        """Width of the bitmap. (read only)"""
        pass

    @property
    def height(self):
        """Height of the bitmap. (read only)"""
        pass


class ColorConverter:
    """Converts one color format to another."""
    def __init__(self):
        """Create a ColorConverter object to convert color formats.
        Only supports RGB888 to RGB565 currently.
        """
        self._dither = False
        
    def convert(self, color):
        "Converts the given RGB888 color to RGB565"
        pass

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
    def __init__(self, display_bus, init_sequence, *, width, height, colstart=0, rowstart=0, rotation=0, color_depth=16, grayscale=False, pixels_in_byte_share_row=True, bytes_per_cell=1, reverse_pixels_in_byte=False, set_column_command=0x2a, set_row_command=0x2b, write_ram_command=0x2c, set_vertical_scroll=0, backlight_pin=None, brightness_command=None, brightness=1.0, auto_brightness=False, single_byte_bounds=False, data_as_commands=False, auto_refresh=True, native_frames_per_second=60):
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
        self._display_bus = display_bus
        self._set_column_command=0x2a
        self._set_row_command=0x2b
        self._write_ram_command=0x2c
        self._brightness_command=brightness_command
        self._data_as_commands = data_as_commands
        self._single_byte_bounds = single_byte_bounds
        i = 0
        while i < len(init_sequence):
            command = bytes([init_sequence[i]])
            data_size = init_sequence[i + 1]
            delay = (data_size & 0x80) > 0
            data_size &= ~0x80
            data_byte = init_sequence[i + 2]
            if (self._single_byte_bounds):
                data = command + init_sequence[i + 2:i + 2 + data_size]
                display_bus.send(True, data, toggle_every_byte=True)
            else:
                display_bus.send(True, command, toggle_every_byte=True)
                if (data_size > 0):
                    display_bus.send(False, init_sequence[i + 2:i + 2 + data_size])
            delay_time_ms = 10
            if (delay):
                data_size += 1
                delay_time_ms = init_sequence[i + 1 + data_size]
                if (delay_time_ms == 255):
                    delay_time_ms = 500
            time.sleep(delay_time_ms / 1000)
            i += 2 + data_size
        
    def show(self, group):
        """Switches to displaying the given group of layers. When group is None, the default CircuitPython terminal will be shown.
        """
        pass

    def refresh(self, *, target_frames_per_second=60, minimum_frames_per_second=1):
        """When auto refresh is off, waits for the target frame rate and then refreshes the display, returning True. If the call has taken too long since the last refresh call for the given target frame rate, then the refresh returns False immediately without updating the screen to hopefully help getting caught up.

        If the time since the last successful refresh is below the minimum frame rate, then an exception will be raised. Set minimum_frames_per_second to 0 to disable.

        When auto refresh is on, updates the display immediately. (The display will also update without calls to this.)
        """
        pass
        
    def fill_row(self, y, buffer):
        pass

    @property
    def auto_refresh(self):
        pass

    @auto_refresh.setter
    def auto_refresh(self, value):
        pass

    @property
    def brightness(self):
        """The brightness of the display as a float. 0.0 is off and 1.0 is full `brightness`. When `auto_brightness` is True, the value of `brightness` will change automatically. If `brightness` is set, `auto_brightness` will be disabled and will be set to False.
        """
        pass

    @brightness.setter
    def brightness(self, value):
        pass

    @property
    def auto_brightness(self):
        """True when the display brightness is adjusted automatically, based on an ambient light sensor or other method. Note that some displays may have this set to True by default, but not actually implement automatic brightness adjustment. `auto_brightness` is set to False if `brightness` is set manually.
        """
        pass

    @auto_brightness.setter
    def auto_brightness(self, value):
        pass

    @property
    def width(self):
        pass

    @property
    def height(self):
        pass

    @property
    def rotation(self):
        """The rotation of the display as an int in degrees."""
        pass

    @rotation.setter
    def rotation(self, value):
        pass

    @property
    def bus(self):
        pass


class EPaperDisplay:
    def __init__(self, display_bus, start_sequence, stop_sequence, *, width, height, ram_width, ram_height, colstart=0, rowstart=0, rotation=0, set_column_window_command=None, set_row_window_command=None, single_byte_bounds=False, write_black_ram_command, black_bits_inverted=False, write_color_ram_command=None, color_bits_inverted=False, highlight_color=0x000000, refresh_display_command, refresh_time=40, busy_pin=None, busy_state=True, seconds_per_frame=180, always_toggle_chip_select=False):
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
    def __init__(self, spi_bus, *, command, chip_select, reset=None, baudrate=24000000, polarity=0, phase=0):
        """Create a FourWire object associated with the given pins.

        The SPI bus and pins are then in use by the display until displayio.release_displays() is called even after a reload. (It does this so CircuitPython can use the display after your code is done.) So, the first time you initialize a display bus in code.py you should call :py:func`displayio.release_displays` first, otherwise it will error after the first code.py run.
        """
        self._dc = digitalio.DigitalInOut(command)
        self._dc.switch_to_output()
        self.chip_select = digitalio.DigitalInOut(chip_select)
        self.chip_select.switch_to_output(value=True)

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
        
    def reset(self):
        if self._reset is not None:
            self.value = False
            time.sleep(0.001)
            self.value = True
            time.sleep(0.001)

    def send(self, command, data, *, toggle_every_byte=False):
        while self._spi.try_lock():
            pass
        self._dc.value = not command
        if (toggle_every_byte):
            for byte in data:
                self._spi.write(bytes([byte]))
                self.chip_select.value = True
                time.sleep(0.000001)
                self.chip_select.value = False
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
        pass
        
    def append(self, layer):
        """Append a layer to the group. It will be drawn
        above other layers.
        """
        pass

    def insert(self, index, layer):
        """Insert a layer into the group."""
        pass
        
    def index(self, layer):
        """Returns the index of the first copy of layer.
        Raises ValueError if not found.
        """
        pass
        
    def pop(self, index=-1):
        """Remove the ith item and return it."""
        pass
        
    def remove(self, layer):
        """Remove the first copy of layer. Raises ValueError
        if it is not present."""
        pass
        
    def __len__(self):
        """Returns the number of layers in a Group"""
        pass

    def __getitem__(self, index):
        """Returns the value at the given index."""
        pass

    def __setitem__(self, index, value):
        """Sets the value at the given index."""
        pass

    def __delitem__(self, index):
        """Deletes the value at the given index."""
        pass

    @property
    def hidden(self):
        pass

    @hidden.setter
    def hidden(self, value):
        pass

    @property
    def scale(self):
        pass

    @scale.setter
    def scale(self, value):
        pass

    @property
    def x(self):
        pass

    @x.setter
    def x(self, value):
        pass

    @property
    def y(self):
        pass

    @y.setter
    def y(self, value):
        pass


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
        pass

    @property
    def width(self):
        """Width of the bitmap. (read only)"""
        pass

    @property
    def height(self):
        """Height of the bitmap. (read only)"""
        pass


class Palette:
    """Map a pixel palette_index to a full color. Colors are transformed to the display’s format internally to save memory."""
    def __init__(self, color_count):
        """Create a Palette object to store a set number of colors."""
        pass

    def __len__(self):
        """Returns the number of colors in a Palette"""
        pass

    def __setitem__(self, index, value):
        """Sets the pixel color at the given index. The index should be an integer in the range 0 to color_count-1.

        The value argument represents a color, and can be from 0x000000 to 0xFFFFFF (to represent an RGB value). Value can be an int, bytes (3 bytes (RGB) or 4 bytes (RGB + pad byte)), bytearray, or a tuple or list of 3 integers.
        """
        pass

    def make_transparent(self, palette_index):
        pass

    def make_opaque(self, palette_index):
        pass


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


class Shape:
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
    def __init__(self, bitmap, *, pixel_shader, width=1, height=1, tile_width=None, tile_height=None, default_tile=0, x=0, y=0):
        """Create a TileGrid object. The bitmap is source for 2d pixels. The pixel_shader is used to convert the value and its location to a display native pixel color. This may be a simple color palette lookup, a gradient, a pattern or a color transformer.

        tile_width and tile_height match the height of the bitmap by default.
        """
        pass

    @property
    def hidden(self):
        """True when the TileGrid is hidden. This may be False even when a part of a hidden Group."""
        pass

    @hidden.setter
    def hidden(self, value):
        pass

    @property
    def x(self):
        """X position of the left edge in the parent."""
        pass

    @property
    def y(self):
        """Y position of the top edge in the parent."""
        pass

    @property
    def flip_x(self):
        """If true, the left edge rendered will be the right edge of the right-most tile."""
        pass

    @flip_x.setter
    def flip_x(self, value):
        pass

    @property
    def flip_y(self):
        """If true, the top edge rendered will be the bottom edge of the bottom-most tile."""
        pass

    @flip_y.setter
    def flip_y(self, value):
        pass

    @property
    def transpose_xy(self):
        """If true, the TileGrid’s axis will be swapped. When combined with mirroring, any 90 degree
        rotation can be achieved along with the corresponding mirrored version.
        """
        pass

    @transpose_xy.setter
    def transpose_xy(self, value):
        pass

    @property
    def pixel_shader(self):
        """The pixel shader of the tilegrid."""
        pass

    def __getitem__(self, index):
        """Returns the tile index at the given index. The index can either be an x,y tuple or an int equal to ``y * width + x``'."""
        pass

    def __setitem__(self, index, value):
        """Sets the tile index at the given index. The index can either be an x,y tuple or an int equal to ``y * width + x``."""
        pass
