import logging
import sys


def _init_logger():
    the_logger = logging.Logger('pumpd')

    handler = logging.StreamHandler(sys.stdout)
    pumpd_format = '%(asctime)-15s %(levelname)s %(message)s'
    handler.setFormatter(logging.Formatter(pumpd_format))
    the_logger.addHandler(handler)
    the_logger.setLevel(logging.INFO)
    return the_logger


logger = _init_logger()
