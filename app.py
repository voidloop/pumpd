from apscheduler.schedulers.asyncio import AsyncIOScheduler
from hardware import Sprinkler
from log_utils import logger
import asyncio


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    sprinkler = Sprinkler(event_loop=loop)

    def tick():
        sprinkler.start(10)

    scheduler = AsyncIOScheduler(event_loop=loop)
    scheduler.add_job(tick, 'interval', seconds=20)
    scheduler.start()
    logger.info('Scheduler started')

    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info('Scheduler stopped')

