from apscheduler.schedulers.asyncio import AsyncIOScheduler
from hardware import Sprinkler
from log_utils import logger
import asyncio

sprinkler = Sprinkler()


def tick():
    sprinkler.start(10)


if __name__ == '__main__':
    scheduler = AsyncIOScheduler()
    scheduler.add_job(tick, 'interval', hours=1)
    scheduler.start()
    logger.info('scheduler started')

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info('scheduler stopped')

