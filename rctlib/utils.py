from __future__ import annotations

import logging

from colorlog import ColoredFormatter

LOG_FMT = "%(asctime)s.%(msecs)03d %(levelname)s [%(name)s] %(message)s"
LOG_FTM_COLOR = f"%(log_color)s{LOG_FMT}%(reset)s"
LOG_FMT_DATETIME = "%Y-%m-%d %H:%M:%S"


def configure_logger(verbose: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    logging.getLogger().handlers[0].setFormatter(
        ColoredFormatter(
            LOG_FTM_COLOR,
            datefmt=LOG_FMT_DATETIME,
            reset=True,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red",
            },
        )
    )
    logging.captureWarnings(True)
