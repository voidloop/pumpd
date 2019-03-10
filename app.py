from aiohttp import web
from aiohttp.log import access_logger
from RPi import GPIO
from water import Pump, FloatSwitch
import asyncio
import automationhat
import socketio
import sys
import logging


if not automationhat.is_automation_hat():
    raise RuntimeError("Automation HAT is not connected")

sio = socketio.AsyncServer(async_mode='aiohttp')
switch = FloatSwitch(gpio=20)
pump = Pump(sio, relay=automationhat.relay.one)
logger = logging.getLogger('pumpd')


@sio.on('pump start')
async def start_pump(sid):
    if switch.is_high():
        await pump.start()
    else:
        await sio.emit('no water')


@sio.on('connect')
async def connect(sid, environ):
    logger.info('connect {}'.format(sid))


def init_gpio_cb():
    loop = asyncio.get_event_loop()

    def switch_cb(_):
        if switch.is_low():
            asyncio.run_coroutine_threadsafe(pump.stop(), loop)
            asyncio.run_coroutine_threadsafe(sio.emit('no water'), loop)
            automationhat.light.warn.on()
        else:
            asyncio.run_coroutine_threadsafe(sio.emit('water ok'), loop)
            automationhat.light.warn.off()

    GPIO.add_event_detect(switch.gpio, GPIO.BOTH, callback=switch_cb)


def init_logging():
    handler = logging.StreamHandler(sys.stdout)
    logger.setLevel(logging.INFO)
    access_logger.setLevel(logging.INFO)

    logger.addHandler(handler)
    access_logger.addHandler(handler)


def main():
    init_gpio_cb()
    init_logging()

    app = web.Application()
    sio.attach(app)
    web.run_app(app, port=5000)


if __name__ == '__main__':
    main()
