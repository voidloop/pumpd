from log_utils import logger
from RPi import GPIO
import automationhat
import asyncio
import os

if not automationhat.is_automation_hat():
    raise RuntimeError("Automation HAT is not connected")


IDLE_TIME = os.environ.get('IDLE_TIME', 3600)
WATERING_TIME = os.environ.get('WATERING_TIME', 15)


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


class Sprinkler:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._pump = Pump()
        self._sensor = Sensor()
        self._loop = loop
        self._interval = IDLE_TIME
        self._seconds = WATERING_TIME
        self._done = asyncio.Event()

    def _start(self):
        if self._sensor.is_high():
            self._watering(self._seconds)
        else:
            logger.info('no water!')
            self._idle()

    def _watering(self, seconds):
        logger.info('watering started (%d seconds)', seconds)
        self._pump.on()
        start_time = self._loop.time()
        handle = self._loop.call_later(seconds, self._stop)

        def empty_bucket():
            logger.info('the water is over!')
            GPIO.remove_event_detect(self._sensor.gpio)
            automationhat.light.warn.on()
            self._pump.off()
            handle.cancel()
            elapsed = self._loop.time() - start_time
            self._waiting(seconds - elapsed)

        GPIO.add_event_detect(
            self._sensor.gpio, GPIO.RISING, bouncetime=500,
            callback=lambda _:
                self._loop.call_soon_threadsafe(empty_bucket))

    def _waiting(self, remaining):
        logger.info('waiting water...')

        def full_bucket():
            logger.info('watering resumed')
            GPIO.remove_event_detect(self._sensor.gpio)
            automationhat.light.warn.off()
            self._watering(remaining)

        GPIO.add_event_detect(
            self._sensor.gpio, GPIO.FALLING, bouncetime=500,
            callback=lambda _:
                self._loop.call_soon_threadsafe(full_bucket))

    def _stop(self):
        logger.info('watering finished')
        GPIO.remove_event_detect(self._sensor.gpio)
        self._pump.off()
        self._idle()

    def _idle(self):
        self._loop.call_later(self._interval, self._start)

    def run(self):
        logger.info('sprinkler started')
        self._start()


def main():
    loop = asyncio.get_event_loop()
    sprinkler = Sprinkler(loop)
    sprinkler.run()
    loop.run_forever()


if __name__ == '__main__':
    main()
