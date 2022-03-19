# SPDX-FileCopyrightText: 2022 adarmalik adarmalik@gmail.com
# SPDX-License-Identifier: GPLv2

from adafruit_magtag.magtag import MagTag
import adafruit_logging as logging

import alarm
import asyncio
import board
import time

import ui
import hmip
import controls
from ui import UI
from hmip import HMIP
from controls import *

from state import RunMode
import config


ui.LOGGER.setLevel(config.LOGGING['ui'])
hmip.LOGGER.setLevel(config.LOGGING['hmip'])
controls.LOGGER.setLevel(config.LOGGING['controls'])

LOGGER = logging.getLogger('MAIN')
LOGGER.setLevel(config.LOGGING['main'])

BYE_MELODY = [(440,0.25), (350,0.25), (147, 0.5)]
LAST_ACTIVITY = 0


def go_to_sleep(magtag):
    LOGGER.info('Go to sleep')
    #play_melody(magtag, BYE_MELODY)
    magtag.peripherals.neopixel_disable = True
    pin_alarm = alarm.pin.PinAlarm(pin=board.D15, value=False, pull=True)
    alarm.exit_and_deep_sleep_until_alarms(pin_alarm)


def play_melody(magtag, meldoy):
    for i in range(len(meldoy)):
        magtag.peripherals.play_tone(meldoy[i][0], meldoy[i][1])


async def pixel_loop(ui, hmip):
    while RunMode.RUNNING:
        ui.update_pixel()
        await asyncio.sleep(1)
    LOGGER.info('Exit pixel loop')


async def display_loop(ui):
    while RunMode.RUNNING:
        await asyncio.sleep(5 if ui.draw_ui() else 1)
    LOGGER.info('Exit display loop')


async def mqtt_loop(hmip):
    while RunMode.RUNNING:
        hmip.mqtt_client_loop()
        await asyncio.sleep(1)
    LOGGER.info('Exit mqtt loop')


async def button_event_loop(bn, ui):
    events = bn.event_queue()
    global LAST_ACTIVITY
    # global MAX_INACTIVITY
    LAST_ACTIVITY = time.monotonic()
    while RunMode.RUNNING:
        if len(events):
            e = events.pop(0)
            LOGGER.debug(str(e))
            ui.consume_button_event(e)
            LAST_ACTIVITY = time.monotonic()
        else:
            if time.monotonic() - LAST_ACTIVITY > config.MAX_INACTIVITY:
                LOGGER.debug('Inactive {} {}'.format(time.monotonic(), LAST_ACTIVITY))
                RunMode.RUNNING = False
                ui.draw_shutdown_screen()
        await asyncio.sleep(0)
    LOGGER.info('Exit button loop')


async def main(mt, ui, hmip, controls):

    loop = asyncio.get_event_loop()

    ui_task = loop.create_task(display_loop(ui))
    pixel_task = loop.create_task(pixel_loop(ui, hmip))
    mqtt_task = loop.create_task(mqtt_loop(hmip))
    button_task = loop.create_task(controls.button_navigation_coro())
    event_task = loop.create_task(button_event_loop(controls, ui))

    await asyncio.gather(mqtt_task, ui_task, pixel_task, button_task, event_task)


LOGGER.info('Starting up')
mt = MagTag()
for i in range(4):
    mt.peripherals.buttons[i].deinit()

mt.peripherals.neopixels[3] = config.STARTUP_COLOR

event_loop = asyncio.get_event_loop()

try:
    hmip = HMIP()
    event_loop.run_until_complete(main(mt,
                                    UI(mt, hmip),
                                    hmip,
                                    ButtonNavigation(mt)))
    LOGGER.info('Loop ended')
except Exception as ex:
    LOGGER.error(str(ex))
    import traceback
    traceback.print_exception(None, ex, ex.__traceback__)
    event_loop.stop()
finally:
    event_loop.close()

go_to_sleep(mt)
