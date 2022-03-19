import asyncio
import keypad
import board
import alarm

import adafruit_logging as logging

from state import RunMode


LOGGER = logging.getLogger('CONTROLS')


class ButtonAEvent:
    pass


class ButtonBEvent:
    pass


class ButtonCEvent:
    pass


class ButtonDEvent:
    pass


class ButtonNavigation():
    def __init__(self, magtag):
        self._ev_queue = []
        self._magtag = magtag
        self._running = True

    async def button_navigation_coro(self):
        pins = (board.BUTTON_A, board.BUTTON_B, board.BUTTON_C, board.BUTTON_D)
        keys = keypad.Keys(pins, value_when_pressed=False, pull=True)
        while RunMode.RUNNING:
            event = keys.events.get()
            if event and event.pressed:
                if pins[event.key_number] == board.BUTTON_A:
                    self._ev_queue.append(ButtonAEvent())
                    self._magtag.peripherals.play_tone(80, 0.07)
                elif pins[event.key_number] == board.BUTTON_B:
                    self._ev_queue.append(ButtonBEvent())
                    self._magtag.peripherals.play_tone(90, 0.07)
                elif pins[event.key_number] == board.BUTTON_C:
                    self._ev_queue.append(ButtonCEvent())
                    self._magtag.peripherals.play_tone(100, 0.07)
                elif pins[event.key_number] == board.BUTTON_D:
                    self._ev_queue.append(ButtonDEvent())
                    self._magtag.peripherals.play_tone(110, 0.07)
            await asyncio.sleep(0)
        keys.deinit()
        LOGGER.info('Exit button navi')

    def event_queue(self):
        return self._ev_queue
