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


class Sensor:
    def __init__(self, gpio=20):
        self.gpio = gpio

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(gpio, GPIO.IN)

    def is_low(self):
        return not self.is_high()

    def is_high(self):
        return not self._read()

    def _read(self):
        return GPIO.input(self.gpio)


class Context:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.state = IdleState(self)
        self.pump = Pump()
        self.sensor = Sensor()


class State:
    def __init__(self, context: Context):
        self._context = context

    def start(self, seconds):
        pass

    def stop(self):
        pass


class IdleState(State):
    def start(self, seconds):
        if self._context.sensor.is_high():
            logger.info('changing state: idle -> running (%ds)', seconds)
            self._context.state = RunningState(self._context, seconds)
        else:
            logger.info('error: the water tank is empty')


class RunningState(State):
    def __init__(self, context, seconds):
        super().__init__(context)
        self._context.pump.on()
        self._start_time = self._context.loop.time()
        self._seconds = seconds
        self._handler = self._context.loop.call_later(seconds, self._normal_stop)

        GPIO.add_event_detect(
            self._context.sensor.gpio, GPIO.RISING, bouncetime=500,
            callback=lambda _:
                self._context.loop.call_soon_threadsafe(self._empty))

    def stop(self):
        self._handler.cancel()
        self._normal_stop()

    def _normal_stop(self):
        logger.info('changing state: running -> idle')
        self._pump_off()
        self._context.state = IdleState(self._context)

    def _pump_off(self):
        self._context.pump.off()
        GPIO.remove_event_detect(self._context.sensor.gpio)

    def _empty(self):
        logger.info('changing state: running -> waiting')
        self._handler.cancel()
        self._pump_off()
        automationhat.light.warn.on()
        elapsed = self._context.loop.time() - self._start_time
        self._context.state = WaitingState(self._context, self._seconds - elapsed)


class WaitingState(State):
    def __init__(self, context, remaining):
        super().__init__(context)
        self._remaining = remaining

        GPIO.add_event_detect(
            self._context.sensor.gpio, GPIO.FALLING, bouncetime=500,
            callback=lambda _:
                self._context.loop.call_soon_threadsafe(self._refilled))

    def _refilled(self):
        logger.info('changing state: waiting -> running (%ds)', self._remaining)
        GPIO.remove_event_detect(self._context.sensor.gpio)
        automationhat.light.warn.off()
        self._context.state = RunningState(self._context, self._remaining)

    def stop(self):
        logger.info('changing state: waiting -> idle')
        GPIO.remove_event_detect(self._context.sensor.gpio)
        automationhat.light.warn.off()
        self._context.state = IdleState(self._context)

    def start(self, seconds):
        logger.info('no water')


class Sprinkler:
    def __init__(self, loop=None):
        if not loop:
            loop = asyncio.get_event_loop()
        self._context = Context(loop)

    def start(self, seconds):
        self._context.state.start(seconds)

    def stop(self):
        self._context.state.stop()
