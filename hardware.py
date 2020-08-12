from abc import ABC, abstractmethod
from enum import Enum
from log_utils import logger
from RPi import GPIO
import automationhat
import asyncio

if not automationhat.is_automation_hat():
    raise RuntimeError("Automation HAT is not connected")


class Pump:
    def __init__(self, relay=None):
        if not relay:
            relay = automationhat.relay.one
        self._relay = relay

    def on(self):
        automationhat.light.power.on()
        self._relay.on()

    def off(self):
        automationhat.light.power.off()
        self._relay.off()


class SensorEvent(Enum):
    RISING = 1
    FALLING = 2


class Sensor:
    _events = {
        SensorEvent.RISING: GPIO.RISING,
        SensorEvent.FALLING: GPIO.FALLING
    }

    def __init__(self, gpio=20):
        self.gpio = gpio
        GPIO.setup(gpio, GPIO.IN)

    def is_low(self):
        return not self.is_high()

    def is_high(self):
        return not self._read()

    def _read(self):
        return GPIO.input(self.gpio)

    def add_event_detect(self, event: SensorEvent, callback):
        GPIO.add_event_detect(
            self.gpio,
            self._events[event],
            bouncetime=500,
            callback=callback)

    def remove_event_detect(self):
        GPIO.remove_event_detect(self.gpio)


class Context:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.state = IdleState(self)
        self.pump = Pump()
        self.sensor = Sensor()

    def transition_to(self, state):
        logger.info('State transition: {} -> {}'.format(self.state, state))
        self.state = state


class State(ABC):
    def __init__(self, context: Context):
        self._context = context

    def start(self, seconds):
        pass

    def stop(self):
        pass

    @abstractmethod
    def __str__(self):
        pass


class IdleState(State):
    def __init__(self, context):
        super().__init__(context)
        self._blink_handler = context.loop.call_later(1, self._blink_on)

    def start(self, seconds):
        if self._context.sensor.is_high():
            self._blink_handler.cancel()
            automationhat.light.power.off()
            self._context.transition_to(RunningState(self._context, seconds))
        else:
            logger.info('The water tank is empty!')

    def _blink_on(self):
        automationhat.light.power.write(0.5)
        self._blink_handler = self._context.loop.call_later(0.2, self._blink_off)

    def _blink_off(self):
        automationhat.light.power.off()
        self._blink_handler = self._context.loop.call_later(4.8, self._blink_on)

    def __str__(self):
        return 'IDLE'


class RunningState(State):
    def __init__(self, context, seconds):
        super().__init__(context)
        loop = self._context.loop
        self._context.pump.on()
        self._start_time = loop.time()
        self._seconds = seconds
        self._handler = loop.call_later(seconds, self._normal_stop)
        self._context.sensor.add_event_detect(
            event=SensorEvent.RISING,
            callback=lambda _: loop.call_soon_threadsafe(self._empty))

    def stop(self):
        self._handler.cancel()
        self._normal_stop()

    def _normal_stop(self):
        self._pump_off()
        self._context.transition_to(IdleState(self._context))

    def _empty(self):
        self._handler.cancel()
        self._pump_off()
        automationhat.light.warn.on()
        elapsed = self._context.loop.time() - self._start_time
        self._context.transition_to(WaitingState(self._context, self._seconds - elapsed))

    def _pump_off(self):
        self._context.pump.off()
        self._context.sensor.remove_event_detect()

    def __str__(self):
        return 'RUNNING ({}s)'.format(self._seconds)


class WaitingState(State):
    def __init__(self, context, remaining):
        super().__init__(context)
        loop = self._context.loop
        self._remaining = remaining
        self._context.sensor.add_event_detect(
            event=SensorEvent.FALLING,
            callback=lambda _: loop.call_soon_threadsafe(self._refilled))

    def _refilled(self):
        self._context.sensor.remove_event_detect()
        automationhat.light.warn.off()
        self._context.transition_to(RunningState(self._context, self._remaining))

    def stop(self):
        self._context.sensor.remove_event_detect()
        automationhat.light.warn.off()
        self._context.transition_to(IdleState(self._context))

    def start(self, seconds):
        logger.info('No water!')

    def __str__(self):
        return 'WAITING (remaining={}s)'.format(self._remaining)


class Sprinkler:
    def __init__(self, event_loop=None):
        if not event_loop:
            event_loop = asyncio.get_event_loop()
        self._context = Context(event_loop)
        logger.info('Initial state: {}'.format(self._context.state))

    def start(self, seconds):
        self._context.state.start(seconds)

    def stop(self):
        self._context.state.stop()
