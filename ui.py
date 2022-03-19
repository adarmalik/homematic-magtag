# SPDX-FileCopyrightText: 2022 adarmalik adarmalik@gmail.com
# SPDX-License-Identifier: GPLv2

import math

import board
import displayio
import terminalio
from displayio import Bitmap

from adafruit_display_text import label, wrap_text_to_lines, wrap_text_to_pixels
from adafruit_bitmap_font import bitmap_font
import adafruit_logging as logging

import config
from state import RunMode
from hmip import HMIP, HMIPInfo
from controls import *

LOGGER = logging.getLogger('UI')


class UI:
    class Screen:
        def __init__(self, info_provider_list, state_to_pixel):
            self.provider = info_provider_list
            self.lut = state_to_pixel

    class LocalInfoProvider(HMIPInfo):
        def __init__(self, name, did, state_getter):
            self._topic_part = ''
            super().__init__(name, did)
            self._state_getter = state_getter

        def value(self):
            return self._state_getter()

    class NEOPIXEL_COLOR:
        RED = (16, 0, 0)
        YELLOW = (128, 32, 0)
        GREEN = (0, 16, 0)
        OFF = (0, 0, 0)

    class LabelStyle:
        def __init__(self, color_value, bg_color_value, font, scale):
            self.__color = color_value
            self.__bg_color = bg_color_value
            self.__font = font
            self.__scale = scale

        @property
        def color(self):
            return self.__color

        def set_color(self, value):
            self.__color = value

        @property
        def background_color(self):
            return self.__bg_color

        def set_background_color(self, value):
            self.__bg_color = value

        @property
        def font(self):
            return self.__font

        def set_font(self, value):
            self.__font = value

        @property
        def scale(self):
            return self.__scale

        def set_font(self, value):
            self.__scale = value

    DEFAULT_LABEL_STYLE = LabelStyle(0x000000,
                                     0xFFFFFF,
                                     bitmap_font.load_font(config.UI_DEFAULT_FONT, Bitmap),
                                     1)

    def __init__(self, magtag, hmip):
        self._mt = magtag
        self._hmip = hmip

        self._homescreen = UI.Screen(
            [UI.LocalInfoProvider('Heizung', '', hmip.get_current_heating_state), UI.LocalInfoProvider('Fenster', '', hmip.get_current_windows_state)],
            lambda state: UI.NEOPIXEL_COLOR.GREEN if state else UI.NEOPIXEL_COLOR.RED
            )
        self._heatingscreen = UI.Screen(
            hmip._wths,
            lambda state: UI.NEOPIXEL_COLOR.RED if state else UI.NEOPIXEL_COLOR.GREEN
            )
        self._windowscreen = UI.Screen(
            hmip._swdms,
            lambda state: UI.NEOPIXEL_COLOR.RED if state else UI.NEOPIXEL_COLOR.GREEN
            )
        self._currentscreen = self._homescreen
        self._events = []
        self._needs_redraw = True
        self._display = board.DISPLAY
        self._display.rotation = 0
        self._splash = displayio.Group()

        bitmap = displayio.OnDiskBitmap('/bg.bmp')
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=bitmap.pixel_shader)
        self._splash.append(tile_grid)
        self._display.show(self._splash)

        self._labels = displayio.Group()
        for i in range(4):
            lbl = label.Label(font=UI.DEFAULT_LABEL_STYLE.font,
                              text='',
                              color=UI.DEFAULT_LABEL_STYLE.color,
                              background_color=UI.DEFAULT_LABEL_STYLE.background_color,
                              scale=UI.DEFAULT_LABEL_STYLE.scale)
            lbl.x = 5
            lbl.y = 72 * i + 52
            self._labels.append(lbl)

        self._splash.append(self._labels)
        self._page = 0
        self.show_main_screen()

    def _set_heating_state(self, on):
        self._set_pixel_color(0, UI.NEOPIXEL_COLOR.GREEN if on else UI.NEOPIXEL_COLOR.RED)

    def _set_window_state(self, on):
        self._set_pixel_color(1, UI.NEOPIXEL_COLOR.GREEN if on else UI.NEOPIXEL_COLOR.RED)

    def _set_pixel_color(self, pixel_idx, color):
        self._mt.peripherals.neopixels[pixel_idx] = color

    def _update_labels(self):
        for i, l in enumerate(self._labels):
            try:
                provider = self._currentscreen.provider[i + (self._page * len(self._labels) )]
                l.text = provider.text()
            except IndexError:
                l.text = ''
        self._needs_redraw = True

    def update_pixel(self):
        for i in range(4):
            try:
                provider = self._currentscreen.provider[i + self._page*4]
                val = self._currentscreen.provider[i + self._page*4].value()
                color = self._currentscreen.lut(val)
                self._set_pixel_color(i, color)
            except IndexError:
                self._set_pixel_color(i, UI.NEOPIXEL_COLOR.OFF)

    def draw_ui(self):
        drawn = True
        if self._needs_redraw:
            try:
                self._display.refresh()
                self._needs_redraw = False
            except RuntimeError:
                drawn = False
                LOGGER.debug('Refresh display failed')
        return drawn

    def show_window_screen(self):
        LOGGER.debug('Switching to window screen')
        self._switch_to_screen(self._windowscreen)

    def show_heating_screen(self):
        LOGGER.debug('Switching to heating screen')
        self._switch_to_screen(self._heatingscreen)

    def show_main_screen(self):
        LOGGER.debug('Switching to home screen')
        self._switch_to_screen(self._homescreen)

    def _switch_to_screen(self, screen):
        self._page = 0
        self._currentscreen = screen
        self._update_labels()
        self.update_pixel()

    def _change_page(self, change):
        self._page = ((self._page + change)%(math.ceil(len(self._currentscreen.provider) / 4)))
        self._update_labels()
        self.update_pixel()

    def consume_button_event(self, event):
        LOGGER.debug('UI processes event %s'%type(event))
        if self._currentscreen == self._homescreen:
            if type(event) == ButtonDEvent:
                self.show_heating_screen()
            elif type(event) == ButtonCEvent:
                self.show_window_screen()
            elif type(event) == ButtonAEvent:
                RunMode.RUNNING = False
                self.draw_shutdown_screen()
        else:
            if type(event) == ButtonDEvent:
                self.show_main_screen()
            elif type(event) == ButtonBEvent:
                self._change_page(-1)
            elif type(event) == ButtonAEvent:
                self._change_page(1)

    def draw_shutdown_screen(self):
        self._labels[0].text = 'To'
        self._labels[1].text = 'Start'
        self._labels[2].text = 'Press'
        self._labels[3].text = 'HERE ->'
        self._mt.peripherals.neopixels[0] = UI.NEOPIXEL_COLOR.OFF
        self._mt.peripherals.neopixels[1] = UI.NEOPIXEL_COLOR.OFF
        self._mt.peripherals.neopixels[2] = UI.NEOPIXEL_COLOR.OFF
        self._mt.peripherals.neopixels[3] = config.SHUTDOWN_COLOR
        self._needs_redraw = True
        while(not self.draw_ui()):
            pass
