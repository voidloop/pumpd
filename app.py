from aiohttp import web
from RPi import GPIO
from water import Pump, FloatSwitch
import asyncio
import automationhat
import socketio

if not automationhat.is_automation_hat():
    raise RuntimeError("Automation HAT is not connected")

sio = socketio.AsyncServer(async_mode='aiohttp')
switch = FloatSwitch(gpio=20)
pump = Pump(sio, relay=automationhat.relay.one)


@sio.on('pump start')
async def start_pump(sid):
    if switch.is_high():
        await pump.start()
    else:
        await sio.emit('no water')


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


def main():
    app = web.Application()
    init_gpio_cb()
    sio.attach(app)
    web.run_app(app, port=5000)


if __name__ == '__main__':
    main()
