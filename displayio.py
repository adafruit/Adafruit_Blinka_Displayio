# The MIT License (MIT)
#
# Copyright (c) 2020 Melissa LeBlanc-Williams for Adafruit Industries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
`displayio`
================================================================================

displayio for Blinka

**Software and Dependencies:**

* Adafruit Blinka:
  https://github.com/adafruit/Adafruit_Blinka/releases

* Author(s): Melissa LeBlanc-Williams

"""

import time
import struct
import threading
import numpy
import digitalio
from PIL import Image
from recordclass import recordclass

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_displayio.git"

# pylint: disable=unnecessary-pass, unused-argument, too-many-lines

_displays = []

Rectangle = recordclass("Rectangle", "x1 y1 x2 y2")
Transform = recordclass("Transform", "x y dx dy scale transpose_xy mirror_x mirror_y")


def release_displays():
    """Releases any actively used displays so their busses and pins can be used again.

    Use this once in your code.py if you initialize a display. Place it right before the
    initialization so the display is active as long as possible.
    """
    for _disp in _displays:
        _disp._release()  # pylint: disable=protected-access
    _displays.clear()


class Bitmap:
    """Stores values of a certain size in a 2D array"""

    def __init__(self, width, height, value_count):
        """Create a Bitmap object with the given fixed size. Each pixel stores a value that is
        used to index into a corresponding palette. This enables differently colored sprites to
        share the underlying Bitmap. value_count is used to minimize the memory used to store
        the Bitmap.
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
            index = (index[1] * self._width) + index[0]
        if index >= len(self._data):
            raise ValueError("Index {} is out of range".format(index))
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
        elif isinstance(index, int):
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
        Only supports rgb888 to RGB565 currently.
        :param bool dither: Adds random noise to dither the output image
        """
        self._dither = dither
        self._depth = 16

    # pylint: disable=no-self-use
    def _compute_rgb565(self, color):
        self._depth = 16
        return (color >> 19) << 11 | ((color >> 10) & 0x3F) << 5 | (color >> 3) & 0x1F

    def _compute_luma(self, color):
        red = color >> 16
        green = (color >> 8) & 0xFF
        blue = color & 0xFF
        return (red * 19) / 255 + (green * 182) / 255 + (blue + 54) / 255

    def _compute_chroma(self, color):
        red = color >> 16
        green = (color >> 8) & 0xFF
        blue = color & 0xFF
        return max(red, green, blue) - min(red, green, blue)

    def _compute_hue(self, color):
        red = color >> 16
        green = (color >> 8) & 0xFF
        blue = color & 0xFF
        max_color = max(red, green, blue)
        chroma = self._compute_chroma(color)
        if chroma == 0:
            return 0
        hue = 0
        if max_color == red:
            hue = (((green - blue) * 40) / chroma) % 240
        elif max_color == green:
            hue = (((blue - red) + (2 * chroma)) * 40) / chroma
        elif max_color == blue:
            hue = (((red - green) + (4 * chroma)) * 40) / chroma
        if hue < 0:
            hue += 240

        return hue

    def _dither_noise_1(self, noise):
        noise = (noise >> 13) ^ noise
        more_noise = (
            noise * (noise * noise * 60493 + 19990303) + 1376312589
        ) & 0x7FFFFFFF
        return (more_noise / (1073741824.0 * 2)) * 255

    def _dither_noise_2(self, x, y):
        return self._dither_noise_1(x + y * 0xFFFF)

    def _compute_tricolor(self):
        pass

    def convert(self, color):
        "Converts the given rgb888 color to RGB565"
        if self._dither:
            return color  # To Do: return a dithered color
        return self._compute_rgb565(color)

    # pylint: enable=no-self-use

    @property
    def dither(self):
        """When true the color converter dithers the output by adding
        random noise when truncating to display bitdepth
        """
        return self._dither

    @dither.setter
    def dither(self, value):
        if not isinstance(value, bool):
            raise ValueError("Value should be boolean")
        self._dither = value


# pylint: disable=too-many-instance-attributes
class Display:
    """This initializes a display and connects it into CircuitPython. Unlike other objects
    in CircuitPython, Display objects live until ``displayio.release_displays()`` is called.
    This is done so that CircuitPython can use the display itself.

    Most people should not use this class directly. Use a specific display driver instead
    that will contain the initialization sequence at minimum.

    .. class::
        Display(display_bus, init_sequence, *, width, height, colstart=0, rowstart=0, rotation=0,
        color_depth=16, grayscale=False, pixels_in_byte_share_row=True, bytes_per_cell=1,
        reverse_pixels_in_byte=False, set_column_command=0x2a, set_row_command=0x2b,
        write_ram_command=0x2c, set_vertical_scroll=0, backlight_pin=None, brightness_command=None,
        brightness=1.0, auto_brightness=False, single_byte_bounds=False, data_as_commands=False,
        auto_refresh=True, native_frames_per_second=60)
    """

    # pylint: disable=too-many-locals
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
        """Create a Display object on the given display bus (`displayio.FourWire` or
        `displayio.ParallelBus`).

        The ``init_sequence`` is bitpacked to minimize the ram impact. Every command begins
        with a command byte followed by a byte to determine the parameter count and if a
        delay is need after. When the top bit of the second byte is 1, the next byte will be
        the delay time in milliseconds. The remaining 7 bits are the parameter count
        excluding any delay byte. The third through final bytes are the remaining command
        parameters. The next byte will begin a new command definition. Here is a portion of
        ILI9341 init code:
        .. code-block:: python

            init_sequence = (
                b"\xe1\x0f\x00\x0E\x14\x03\x11\x07\x31\xC1\x48\x08\x0F\x0C\x31\x36\x0F"
                b"\x11\x80\x78"# Exit Sleep then delay 0x78 (120ms)
                b"\x29\x80\x78"# Display on then delay 0x78 (120ms)
            )
            display = displayio.Display(display_bus, init_sequence, width=320, height=240)

        The first command is 0xe1 with 15 (0xf) parameters following. The second and third
        are 0x11 and 0x29 respectively with delays (0x80) of 120ms (0x78) and no parameters.
        Multiple byte literals (b”“) are merged together on load. The parens are needed to
        allow byte literals on subsequent lines.

        The initialization sequence should always leave the display memory access inline with
        the scan of the display to minimize tearing artifacts.
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
        self._buffer = Image.new("RGBA", (width, height))
        self._subrectangles = []
        self._bounds_encoding = ">BB" if single_byte_bounds else ">HH"
        self._current_group = None
        _displays.append(self)
        self._refresh_thread = None
        if self._auto_refresh:
            self.auto_refresh = True

    # pylint: enable=too-many-locals

    def _initialize(self, init_sequence):
        i = 0
        while i < len(init_sequence):
            command = init_sequence[i]
            data_size = init_sequence[i + 1]
            delay = (data_size & 0x80) > 0
            data_size &= ~0x80
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
        """Switches to displaying the given group of layers. When group is None, the
        default CircuitPython terminal will be shown.
        """
        self._current_group = group

    def refresh(self, *, target_frames_per_second=60, minimum_frames_per_second=1):
        """When auto refresh is off, waits for the target frame rate and then refreshes the
        display, returning True. If the call has taken too long since the last refresh call
        for the given target frame rate, then the refresh returns False immediately without
        updating the screen to hopefully help getting caught up.

        If the time since the last successful refresh is below the minimum frame rate, then
        an exception will be raised. Set minimum_frames_per_second to 0 to disable.

        When auto refresh is on, updates the display immediately. (The display will also
        update without calls to this.)
        """
        # Go through groups and and add each to buffer
        if self._current_group is not None:
            buffer = Image.new("RGBA", (self._width, self._height))
            # Recursively have everything draw to the image
            self._current_group._fill_area(buffer)  # pylint: disable=protected-access
            # save image to buffer (or probably refresh buffer so we can compare)
            self._buffer.paste(buffer)
        time.sleep(1)
        # Eventually calculate dirty rectangles here
        self._subrectangles.append(Rectangle(0, 0, self._width, self._height))

        for area in self._subrectangles:
            self._refresh_display_area(area)

    def _refresh_loop(self):
        while self._auto_refresh:
            self.refresh()

    def _refresh_display_area(self, rectangle):
        """Loop through dirty rectangles and redraw that area."""
        data = numpy.array(self._buffer.crop(rectangle).convert("RGB")).astype("uint16")
        color = (
            ((data[:, :, 0] & 0xF8) << 8)
            | ((data[:, :, 1] & 0xFC) << 3)
            | (data[:, :, 2] >> 3)
        )

        pixels = list(
            numpy.dstack(((color >> 8) & 0xFF, color & 0xFF)).flatten().tolist()
        )

        self._write(
            self._set_column_command,
            self._encode_pos(
                rectangle.x1 + self._colstart, rectangle.x2 + self._colstart
            ),
        )
        self._write(
            self._set_row_command,
            self._encode_pos(
                rectangle.y1 + self._rowstart, rectangle.y2 + self._rowstart
            ),
        )
        self._write(self._write_ram_command, pixels)

    def _encode_pos(self, x, y):
        """Encode a postion into bytes."""
        return struct.pack(self._bounds_encoding, x, y)

    def fill_row(self, y, buffer):
        """Extract the pixels from a single row"""
        pass

    @property
    def auto_refresh(self):
        """True when the display is refreshed automatically."""
        return self._auto_refresh

    @auto_refresh.setter
    def auto_refresh(self, value):
        self._auto_refresh = value
        if self._refresh_thread is None:
            self._refresh_thread = threading.Thread(
                target=self._refresh_loop, daemon=True
            )
        if value and not self._refresh_thread.is_alive():
            # Start the thread
            self._refresh_thread.start()
        elif not value and self._refresh_thread.is_alive():
            # Stop the thread
            self._refresh_thread.join()

    @property
    def brightness(self):
        """The brightness of the display as a float. 0.0 is off and 1.0 is full `brightness`.
        When `auto_brightness` is True, the value of `brightness` will change automatically.
        If `brightness` is set, `auto_brightness` will be disabled and will be set to False.
        """
        return self._brightness

    @brightness.setter
    def brightness(self, value):
        self._brightness = value

    @property
    def auto_brightness(self):
        """True when the display brightness is adjusted automatically, based on an ambient
        light sensor or other method. Note that some displays may have this set to True by
        default, but not actually implement automatic brightness adjustment.
        `auto_brightness` is set to False if `brightness` is set manually.
        """
        return self._auto_brightness

    @auto_brightness.setter
    def auto_brightness(self, value):
        self._auto_brightness = value

    @property
    def width(self):
        """Display Width"""
        return self._width

    @property
    def height(self):
        """Display Height"""
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
        """Current Display Bus"""
        return self._bus


# pylint: enable=too-many-instance-attributes


class EPaperDisplay:
    """Manage updating an epaper display over a display bus

    This initializes an epaper display and connects it into CircuitPython. Unlike other
    objects in CircuitPython, EPaperDisplay objects live until
    displayio.release_displays() is called. This is done so that CircuitPython can use
    the display itself.

    Most people should not use this class directly. Use a specific display driver instead
    that will contain the startup and shutdown sequences at minimum.
    """

    # pylint: disable=too-many-locals
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
        Create a EPaperDisplay object on the given display bus (displayio.FourWire or
        displayio.ParallelBus).

        The start_sequence and stop_sequence are bitpacked to minimize the ram impact. Every
        command begins with a command byte followed by a byte to determine the parameter
        count and if a delay is need after. When the top bit of the second byte is 1, the
        next byte will be the delay time in milliseconds. The remaining 7 bits are the
        parameter count excluding any delay byte. The third through final bytes are the
        remaining command parameters. The next byte will begin a new command definition.
        """
        pass

    # pylint: enable=too-many-locals

    def show(self, group):
        """Switches to displaying the given group of layers. When group is None, the default
        CircuitPython terminal will be shown (eventually).
        """
        pass

    def refresh(self):
        """Refreshes the display immediately or raises an exception if too soon. Use
        ``time.sleep(display.time_to_refresh)`` to sleep until a refresh can occur.
        """
        pass

    @property
    def time_to_refresh(self):
        """Time, in fractional seconds, until the ePaper display can be refreshed."""
        return 0

    @property
    def width(self):
        """Display Width"""
        pass

    @property
    def height(self):
        """Display Height"""
        pass

    @property
    def bus(self):
        """Current Display Bus"""
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

        The SPI bus and pins are then in use by the display until
        displayio.release_displays() is called even after a reload. (It does this so
        CircuitPython can use the display after your code is done.)
        So, the first time you initialize a display bus in code.py you should call
        :py:func`displayio.release_displays` first, otherwise it will error after the
        first code.py run.
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
        """Performs a hardware reset via the reset pin.
        Raises an exception if called when no reset pin is available.
        """
        if self._reset is not None:
            self._reset.value = False
            time.sleep(0.001)
            self._reset.value = True
            time.sleep(0.001)
        else:
            raise RuntimeError("No reset pin defined")

    def send(self, is_command, data, *, toggle_every_byte=False):
        """Sends the given command value followed by the full set of data. Display state,
        such as vertical scroll, set via ``send`` may or may not be reset once the code is
        done.
        """
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
            raise ValueError("Max Size must be >= 1")
        self._max_size = max_size
        if not isinstance(scale, int) or scale < 1:
            raise ValueError("Scale must be >= 1")
        self._scale = scale
        self._x = x
        self._y = y
        self._hidden = False
        self._layers = []
        self._supported_types = (TileGrid, Group)
        self._absolute_transform = None
        self.in_group = False
        self._absolute_transform = Transform(0, 0, 1, 1, 1, False, False, False)

    def update_transform(self, parent_transform):
        """Update the parent transform and child transforms"""
        self.in_group = parent_transform is not None
        if self.in_group:
            x = self._x
            y = self._y
            if parent_transform.transpose_xy:
                x, y = y, x
            self._absolute_transform.x = parent_transform.x + parent_transform.dx * x
            self._absolute_transform.y = parent_transform.y + parent_transform.dy * y
            self._absolute_transform.dx = parent_transform.dx * self._scale
            self._absolute_transform.dy = parent_transform.dy * self._scale
            self._absolute_transform.transpose_xy = parent_transform.transpose_xy
            self._absolute_transform.mirror_x = parent_transform.mirror_x
            self._absolute_transform.mirror_y = parent_transform.mirror_y
            self._absolute_transform.scale = parent_transform.scale * self._scale
        self._update_child_transforms()

    def _update_child_transforms(self):
        if self.in_group:
            for layer in self._layers:
                layer.update_transform(self._absolute_transform)

    def _removal_cleanup(self, index):
        layer = self._layers[index]
        layer.update_transform(None)

    def _layer_update(self, index):
        layer = self._layers[index]
        layer.update_transform(self._absolute_transform)

    def append(self, layer):
        """Append a layer to the group. It will be drawn
        above other layers.
        """
        self.insert(len(self._layers), layer)

    def insert(self, index, layer):
        """Insert a layer into the group."""
        if not isinstance(layer, self._supported_types):
            raise ValueError("Invalid Group Member")
        if layer.in_group:
            raise ValueError("Layer already in a group.")
        if len(self._layers) == self._max_size:
            raise RuntimeError("Group full")
        self._layers.insert(index, layer)
        self._layer_update(index)

    def index(self, layer):
        """Returns the index of the first copy of layer.
        Raises ValueError if not found.
        """
        return self._layers.index(layer)

    def pop(self, index=-1):
        """Remove the ith item and return it."""
        self._removal_cleanup(index)
        return self._layers.pop(index)

    def remove(self, layer):
        """Remove the first copy of layer. Raises ValueError
        if it is not present."""
        index = self.index(layer)
        self._layers.pop(index)

    def __len__(self):
        """Returns the number of layers in a Group"""
        return len(self._layers)

    def __getitem__(self, index):
        """Returns the value at the given index."""
        return self._layers[index]

    def __setitem__(self, index, value):
        """Sets the value at the given index."""
        self._removal_cleanup(index)
        self._layers[index] = value
        self._layer_update(index)

    def __delitem__(self, index):
        """Deletes the value at the given index."""
        del self._layers[index]

    def _fill_area(self, buffer):
        if self._hidden:
            return

        for layer in self._layers:
            if isinstance(layer, (Group, TileGrid)):
                layer._fill_area(buffer)  # pylint: disable=protected-access

    @property
    def hidden(self):
        """True when the Group and all of it’s layers are not visible. When False, the
        Group’s layers are visible if they haven’t been hidden.
        """
        return self._hidden

    @hidden.setter
    def hidden(self, value):
        if not isinstance(value, (bool, int)):
            raise ValueError("Expecting a boolean or integer value")
        self._hidden = bool(value)

    @property
    def scale(self):
        """Scales each pixel within the Group in both directions. For example, when
        scale=2 each pixel will be represented by 2x2 pixels.
        """
        return self._scale

    @scale.setter
    def scale(self, value):
        if not isinstance(value, int) or value < 1:
            raise ValueError("Scale must be >= 1")
        if self._scale != value:
            parent_scale = self._absolute_transform.scale / self._scale
            self._absolute_transform.dx = (
                self._absolute_transform.dx / self._scale * value
            )
            self._absolute_transform.dy = (
                self._absolute_transform.dy / self._scale * value
            )
            self._absolute_transform.scale = parent_scale * value

            self._scale = value
            self._update_child_transforms()

    @property
    def x(self):
        """X position of the Group in the parent."""
        return self._x

    @x.setter
    def x(self, value):
        if not isinstance(value, int):
            raise ValueError("x must be an integer")
        if self._x != value:
            if self._absolute_transform.transpose_xy:
                dy_value = self._absolute_transform.dy / self._scale
                self._absolute_transform.y += dy_value * (value - self._x)
            else:
                dx_value = self._absolute_transform.dx / self._scale
                self._absolute_transform.x += dx_value * (value - self._x)
            self._x = value
            self._update_child_transforms()

    @property
    def y(self):
        """Y position of the Group in the parent."""
        return self._y

    @y.setter
    def y(self, value):
        if not isinstance(value, int):
            raise ValueError("y must be an integer")
        if self._y != value:
            if self._absolute_transform.transpose_xy:
                dx_value = self._absolute_transform.dx / self._scale
                self._absolute_transform.x += dx_value * (value - self._y)
            else:
                dy_value = self._absolute_transform.dy / self._scale
                self._absolute_transform.y += dy_value * (value - self._y)
            self._y = value
            self._update_child_transforms()


class I2CDisplay:
    """Manage updating a display over I2C in the background while Python code runs.
    It doesn’t handle display initialization.
    """

    def __init__(self, i2c_bus, *, device_address, reset=None):
        """Create a I2CDisplay object associated with the given I2C bus and reset pin.

        The I2C bus and pins are then in use by the display until displayio.release_displays() is
        called even after a reload. (It does this so CircuitPython can use the display after your
        code is done.) So, the first time you initialize a display bus in code.py you should call
        :py:func`displayio.release_displays` first, otherwise it will error after the first
        code.py run.
        """
        pass

    def reset(self):
        """Performs a hardware reset via the reset pin. Raises an exception if called
        when no reset pin is available.
        """
        pass

    def send(self, command, data):
        """Sends the given command value followed by the full set of data. Display state,
        such as vertical scroll, set via send may or may not be reset once the code is
        done.
        """
        pass


class OnDiskBitmap:
    """
    Loads values straight from disk. This minimizes memory use but can lead to much slower
    pixel load times. These load times may result in frame tearing where only part of the
    image is visible."""

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
    """Map a pixel palette_index to a full color. Colors are transformed to the display’s
    format internally to save memory.
    """

    def __init__(self, color_count):
        """Create a Palette object to store a set number of colors."""
        self._needs_refresh = False

        self._colors = []
        for _ in range(color_count):
            self._colors.append(self._make_color(0))
            self._update_rgba(len(self._colors) - 1)

    def _update_rgba(self, index):
        color = self._colors[index]["rgb888"]
        transparent = self._colors[index]["transparent"]
        self._colors[index]["rgba"] = (
            color >> 16,
            (color >> 8) & 0xFF,
            color & 0xFF,
            0 if transparent else 0xFF,
        )

    def _make_color(self, value, transparent=False):
        color = {
            "transparent": transparent,
            "rgb888": 0,
            "rgba": (0, 0, 0, 255),
        }
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
        """Sets the pixel color at the given index. The index should be
        an integer in the range 0 to color_count-1.

        The value argument represents a color, and can be from 0x000000 to 0xFFFFFF
        (to represent an RGB value). Value can be an int, bytes (3 bytes (RGB) or
        4 bytes (RGB + pad byte)), bytearray, or a tuple or list of 3 integers.
        """
        if self._colors[index]["rgb888"] != value:
            self._colors[index] = self._make_color(value)
            self._update_rgba(index)

    def __getitem__(self, index):
        if not 0 <= index < len(self._colors):
            raise ValueError("Palette index out of range")
        return self._colors[index]

    def make_transparent(self, palette_index):
        """Set the palette index to be a transparent color"""
        self._colors[palette_index]["transparent"] = True
        self._update_rgba(palette_index)

    def make_opaque(self, palette_index):
        """Set the palette index to be an opaque color"""
        self._colors[palette_index]["transparent"] = False
        self._update_rgba(palette_index)


class ParallelBus:
    """Manage updating a display over 8-bit parallel bus in the background while Python code
    runs. This protocol may be refered to as 8080-I Series Parallel Interface in datasheets.
    It doesn’t handle display initialization.
    """

    def __init__(self, i2c_bus, *, device_address, reset=None):
        """Create a ParallelBus object associated with the given pins. The
        bus is inferred from data0 by implying the next 7 additional pins on a given GPIO
        port.

        The parallel bus and pins are then in use by the display until
        displayio.release_displays() is called even after a reload. (It does this so
        CircuitPython can use the display after your code is done.) So, the first time you
        initialize a display bus in code.py you should call
        :py:func`displayio.release_displays` first, otherwise it will error after the first
        code.py run.
        """
        pass

    def reset(self):
        """Performs a hardware reset via the reset pin. Raises an exception if called when
        no reset pin is available.
        """
        pass

    def send(self, command, data):
        """Sends the given command value followed by the full set of data. Display state,
        such as vertical scroll, set via ``send`` may or may not be reset once the code is
        done.
        """
        pass


class Shape(Bitmap):
    """Create a Shape object with the given fixed size. Each pixel is one bit and is stored
    by the column boundaries of the shape on each row. Each row’s boundary defaults to the
    full row.
    """

    def __init__(self, width, height, *, mirror_x=False, mirror_y=False):
        """Create a Shape object with the given fixed size. Each pixel is one bit and is
        stored by the column boundaries of the shape on each row. Each row’s boundary
        defaults to the full row.
        """
        super().__init__(width, height, 2)

    def set_boundary(self, y, start_x, end_x):
        """Loads pre-packed data into the given row."""
        pass


# pylint: disable=too-many-instance-attributes
class TileGrid:
    """Position a grid of tiles sourced from a bitmap and pixel_shader combination. Multiple
    grids can share bitmaps and pixel shaders.

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
        """Create a TileGrid object. The bitmap is source for 2d pixels. The pixel_shader is
        used to convert the value and its location to a display native pixel color. This may
        be a simple color palette lookup, a gradient, a pattern or a color transformer.

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
        self._hidden = False
        self._x = x
        self._y = y
        self._width = width  # Number of Tiles Wide
        self._height = height  # Number of Tiles High
        self._transpose_xy = False
        self._flip_x = False
        self._flip_y = False
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
        if not 0 <= default_tile <= 255:
            raise ValueError("Default Tile is out of range")
        self._pixel_width = width * tile_width
        self._pixel_height = height * tile_height
        self._tiles = (self._width * self._height) * [default_tile]
        self.in_group = False
        self._absolute_transform = Transform(0, 0, 1, 1, 1, False, False, False)
        self._current_area = Rectangle(0, 0, self._pixel_width, self._pixel_height)
        self._moved = False

    def update_transform(self, absolute_transform):
        """Update the parent transform and child transforms"""
        self._absolute_transform = absolute_transform
        if self._absolute_transform is not None:
            self._update_current_x()
            self._update_current_y()

    def _update_current_x(self):
        if self._transpose_xy:
            width = self._pixel_height
        else:
            width = self._pixel_width
        if self._absolute_transform.transpose_xy:
            self._current_area.y1 = (
                self._absolute_transform.y + self._absolute_transform.dy * self._x
            )
            self._current_area.y2 = (
                self._absolute_transform.y
                + self._absolute_transform.dy * (self._x + width)
            )
            if self._current_area.y2 < self._current_area.y1:
                self._current_area.y1, self._current_area.y2 = (
                    self._current_area.y2,
                    self._current_area.y1,
                )
        else:
            self._current_area.x1 = (
                self._absolute_transform.x + self._absolute_transform.dx * self._x
            )
            self._current_area.x2 = (
                self._absolute_transform.x
                + self._absolute_transform.dx * (self._x + width)
            )
            if self._current_area.x2 < self._current_area.x1:
                self._current_area.x1, self._current_area.x2 = (
                    self._current_area.x2,
                    self._current_area.x1,
                )

    def _update_current_y(self):
        if self._transpose_xy:
            height = self._pixel_width
        else:
            height = self._pixel_height
        if self._absolute_transform.transpose_xy:
            self._current_area.x1 = (
                self._absolute_transform.x + self._absolute_transform.dx * self._y
            )
            self._current_area.x2 = (
                self._absolute_transform.x
                + self._absolute_transform.dx * (self._y + height)
            )
            if self._current_area.x2 < self._current_area.x1:
                self._current_area.x1, self._current_area.x2 = (
                    self._current_area.x2,
                    self._current_area.x1,
                )
        else:
            self._current_area.y1 = (
                self._absolute_transform.y + self._absolute_transform.dy * self._y
            )
            self._current_area.y2 = (
                self._absolute_transform.y
                + self._absolute_transform.dy * (self._y + height)
            )
            if self._current_area.y2 < self._current_area.y1:
                self._current_area.y1, self._current_area.y2 = (
                    self._current_area.y2,
                    self._current_area.y1,
                )

    # pylint: disable=too-many-locals
    def _fill_area(self, buffer):
        """Draw onto the image"""
        if self._hidden:
            return

        image = Image.new(
            "RGBA", (self._width * self._tile_width, self._height * self._tile_height)
        )

        tile_count_x = self._bitmap.width // self._tile_width
        x = self._x
        y = self._y

        # TODO: Fix transparency

        for tile_x in range(0, self._width):
            for tile_y in range(0, self._height):
                tile_index = self._tiles[tile_y * self._width + tile_x]
                tile_index_x = tile_index % tile_count_x
                tile_index_y = tile_index // tile_count_x
                for pixel_x in range(self._tile_width):
                    for pixel_y in range(self._tile_height):
                        image_x = tile_x * self._tile_width + pixel_x
                        image_y = tile_y * self._tile_height + pixel_y
                        bitmap_x = tile_index_x * self._tile_width + pixel_x
                        bitmap_y = tile_index_y * self._tile_height + pixel_y
                        pixel_color = self._pixel_shader[
                            self._bitmap[bitmap_x, bitmap_y]
                        ]
                        image.putpixel((image_x, image_y), pixel_color["rgba"])

        if self._absolute_transform is not None:
            if self._absolute_transform.scale > 1:
                image = image.resize(
                    (
                        self._pixel_width * self._absolute_transform.scale,
                        self._pixel_height * self._absolute_transform.scale,
                    ),
                    resample=Image.NEAREST,
                )
            if self._absolute_transform.mirror_x:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
            if self._absolute_transform.mirror_y:
                image = image.transpose(Image.FLIP_TOP_BOTTOM)
            if self._absolute_transform.transpose_xy:
                image = image.transpose(Image.TRANSPOSE)
            x *= self._absolute_transform.dx
            y *= self._absolute_transform.dy
            x += self._absolute_transform.x
            y += self._absolute_transform.y
        buffer.paste(image, (x, y))

    # pylint: enable=too-many-locals

    @property
    def hidden(self):
        """True when the TileGrid is hidden. This may be False even
        when a part of a hidden Group."""
        return self._hidden

    @hidden.setter
    def hidden(self, value):
        if not isinstance(value, (bool, int)):
            raise ValueError("Expecting a boolean or integer value")
        self._hidden = bool(value)

    @property
    def x(self):
        """X position of the left edge in the parent."""
        return self._x

    @x.setter
    def x(self, value):
        if not isinstance(value, int):
            raise TypeError("X should be a integer type")
        if self._x != value:
            self._x = value
            self._update_current_x()

    @property
    def y(self):
        """Y position of the top edge in the parent."""
        return self._y

    @y.setter
    def y(self, value):
        if not isinstance(value, int):
            raise TypeError("Y should be a integer type")
        if self._y != value:
            self._y = value
            self._update_current_y()

    @property
    def flip_x(self):
        """If true, the left edge rendered will be the right edge of the right-most tile."""
        return self._flip_x

    @flip_x.setter
    def flip_x(self, value):
        if not isinstance(value, bool):
            raise TypeError("Flip X should be a boolean type")
        if self._flip_x != value:
            self._flip_x = value

    @property
    def flip_y(self):
        """If true, the top edge rendered will be the bottom edge of the bottom-most tile."""
        return self._flip_y

    @flip_y.setter
    def flip_y(self, value):
        if not isinstance(value, bool):
            raise TypeError("Flip Y should be a boolean type")
        if self._flip_y != value:
            self._flip_y = value

    @property
    def transpose_xy(self):
        """If true, the TileGrid’s axis will be swapped. When combined with mirroring, any 90
        degree rotation can be achieved along with the corresponding mirrored version.
        """
        return self._transpose_xy

    @transpose_xy.setter
    def transpose_xy(self, value):
        if not isinstance(value, bool):
            raise TypeError("Transpose XY should be a boolean type")
        if self._transpose_xy != value:
            self._transpose_xy = value
            self._update_current_x()
            self._update_current_y()

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
        elif isinstance(index, int):
            x = index % self._width
            y = index // self._width
        if x > self._width or y > self._height or index >= len(self._tiles):
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
        elif isinstance(index, int):
            x = index % self._width
            y = index // self._width
        if x > self._width or y > self._height or index >= len(self._tiles):
            raise ValueError("Tile index out of bounds")
        if not 0 <= value <= 255:
            raise ValueError("Tile value out of bounds")
        self._tiles[index] = value


# pylint: enable=too-many-instance-attributes
