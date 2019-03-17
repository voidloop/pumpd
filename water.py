from abc import ABC, abstractmethod
import asyncio
import RPi.GPIO as GPIO


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


class AbstractPumpContext(ABC):
    def __init__(self):
        self.state = PumpStopped(self)

    @abstractmethod
    async def activate(self):
        pass

    @abstractmethod
    async def deactivate(self):
        pass


class Pump:
    def __init__(self, context: AbstractPumpContext):
        self._context = context

    async def start(self, seconds=None):
        await self._context.state.start(seconds)

    async def stop(self):
        await self._context.state.stop()

    @property
    def is_running(self):
        return not isinstance(self._context.state, PumpStopped)


class PumpState:
    def __init__(self, context: AbstractPumpContext):
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
        self._timer = self._create_timer(seconds)

    async def start(self, seconds=None):
        self._timer.cancel()
        self._timer = self._create_timer(seconds)

    async def stop(self):
        self._timer.cancel()
        await super().stop()

    def _create_timer(self, seconds):
        return AsyncTimer(seconds, self._kill)


class AsyncTimer:
    def __init__(self, seconds, callback):
        self._seconds = seconds
        self._callback = callback
        self._task = asyncio.ensure_future(self._run())

    async def _run(self):
        await asyncio.sleep(self._seconds)
        await self._callback()

    def cancel(self):
        self._task.cancel()


class PumpStopped(PumpState):
    def __init__(self, context):
        super().__init__(context)

    def _change_state(self, seconds):
        if seconds is None:
            self._context.state = PumpStarted(self._context)
        else:
            self._context.state = PumpStartedTimer(self._context, seconds)

    async def start(self, seconds=None):
        await self._context.activate()
        self._change_state(seconds)
