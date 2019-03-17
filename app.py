from aiohttp import web
from log_utils import logger
from RPi import GPIO
from water import Pump, FloatSwitch, AbstractPumpContext
import asyncio
import automationhat
import socketio

if not automationhat.is_automation_hat():
    raise RuntimeError("Automation HAT is not connected")

sio = socketio.AsyncServer(async_mode='aiohttp')


class PumpContext(AbstractPumpContext):
    def __init__(self):
        super().__init__()
        self.relay = automationhat.relay.one

    async def activate(self):
        self.relay.on()
        logger.info('emit (broadcast): pump_started')
        await sio.emit('pump_started')

    async def deactivate(self):
        self.relay.off()
        logger.info('emit (broadcast): pump_stopped')
        await sio.emit('pump_stopped')


switch = FloatSwitch(gpio=20)
pump = Pump(PumpContext())


@sio.on('pump_start')
async def on_pump_start(sid, data):

    async def error(msg):
        logger.warn(msg)
        await sio.emit('error', data=msg, room=sid)

    try:
        seconds = int(data['seconds'])
        logger.info('event (sid=%s): pump_start (%d %s)', sid, seconds, 'second' if seconds == 1 else 'seconds')
        if seconds < 0:
            await error('a negative value for "seconds" parameter is not allowed (seconds={})'.format(seconds))
            return
    except (TypeError, ValueError):
        if data['seconds'] is None:
            logger.info('event (sid=%s): pump_start (client has not specified how many seconds)', sid)
            seconds = None
        else:
            await error('"seconds" parameter must be an integer (seconds={})'.format(data['seconds']))
            return
    except KeyError:
        seconds = None

    if switch.is_high():
        await pump.start(seconds=seconds)
    else:
        logger.info('emit (sid=%s): no_water', sid)
        await sio.emit('no_water', room=sid)


@sio.on('pump_stop')
async def on_pump_stop(sid):
    logger.info('event (sid=%s): pump_stop', sid)
    await pump.stop()


@sio.on('connect')
async def on_connect(sid, environ):
    logger.info('event (sid=%s): connect (%s)', sid, environ['REMOTE_ADDR'])


@sio.on('client_ready')
async def on_client_ready(sid):
    logger.info('event (sid=%s): client_ready', sid)
    data = {
        'water': 'high' if switch.is_high() else 'low',
        'pump': 'running' if pump.is_running else 'stop'
    }

    await sio.emit('server_ready', data, room=sid)
    logger.info('emit (sid={}): server_ready, data={}'.format(sid, data))


def install_interrupts():
    loop = asyncio.get_event_loop()

    async def low():
        logger.info('emit (broadcast): no_water')
        await sio.emit('no_water')
        await pump.stop()

    async def high():
        logger.info('emit (broadcast): water_ok')
        await sio.emit('water_ok')

    def switch_cb(_):
        if switch.is_low():
            asyncio.run_coroutine_threadsafe(low(), loop)
            automationhat.light.warn.on()
        else:
            asyncio.run_coroutine_threadsafe(high(), loop)
            automationhat.light.warn.off()

    GPIO.add_event_detect(switch.gpio, GPIO.BOTH, callback=switch_cb)


def main():
    install_interrupts()
    app = web.Application()
    sio.attach(app)
    web.run_app(app, port=5000)


if __name__ == '__main__':
    main()
