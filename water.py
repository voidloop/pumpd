import asyncio
import RPi.GPIO as GPIO
import socketio
import logging


class FloatSwitch:
    def __init__(self, gpio):
        self.gpio = gpio

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(gpio, GPIO.IN)

    def read(self):
        return GPIO.input(self.gpio)

    def is_high(self):
        return not self.read()

    def is_low(self):
        return not self.is_high()


class PumpContext:
    def __init__(self, sio: socketio.AsyncServer, relay):
        self.sio = sio
        self.relay = relay
        self.state = PumpStopped(self)

    async def activate(self):
        self.relay.on()
        await self.sio.emit('pump started')
        logging.info('pump started')

    async def deactivate(self):
        self.relay.off()
        await self.sio.emit('pump stopped')
        logging.info('pump stopped')


class Pump:
    def __init__(self, sio, relay):
        self._context = PumpContext(sio, relay)

    async def start(self, seconds=None):
        await self._context.state.start(seconds)

    async def stop(self):
        await self._context.state.stop()

    def attach(self, switch):
        self._context.switch = switch


class PumpState:
    def __init__(self, context: PumpContext):
        self._context = context

    async def start(self, seconds=None):
        pass

    async def stop(self):
        pass


class PumpStarted(PumpState):
    def __init__(self, context):
        super().__init__(context)

    async def _kill(self):
        await self._context.deactivate()
        self._context.state = PumpStopped(self._context)

    async def stop(self):
        await self._kill()


class PumpStartedTimer(PumpStarted):
    def __init__(self, context, seconds):
        super().__init__(context)
        self._timer = self._start_timer(seconds)

    async def start(self, seconds=None):
        self._timer.cancel()
        self._timer = self._start_timer(seconds)
        await self._context.sio.emit('pump restarted')
        logging.info('pump restarted')

    async def stop(self):
        self._timer.cancel()
        await super().stop()

    def _start_timer(self, seconds):
        return AsyncTimer(seconds, self._kill)


class AsyncTimer:
    def __init__(self, seconds, callback):
        self._seconds = seconds
        self._callback = callback
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        await asyncio.sleep(self._seconds)
        await self._callback()

    def cancel(self):
        self._task.cancel()


class PumpStopped(PumpState):
    def __init__(self, context):
        super().__init__(context)

    def _change_state(self, seconds):
        if seconds:
            self._context.state = PumpStartedTimer(self._context, seconds)
        else:
            self._context.state = PumpStarted(self._context)

    async def start(self, seconds=None):
        await self._context.activate()
        self._change_state(seconds)
