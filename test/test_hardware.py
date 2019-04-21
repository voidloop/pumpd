from hardware import Sprinkler
from log_utils import logger
import asyncio

loop = asyncio.get_event_loop()
s = Sprinkler(loop)

loop.call_later(1, s.start, 30)

logger.info('starting')
loop.run_forever()
