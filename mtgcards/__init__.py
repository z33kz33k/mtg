"""

    mtgcards
    ~~~~~~~~
    Root package.

    @author: z33k

"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, TypeVar


__appname__ = __name__
__version__ = "0.4.0"
__description__ = "Scrape data on MtG cards and do other stuff."
__author__ = "z33k"
__license__ = "MIT License"

# type hints
T = TypeVar("T")
Json = dict[str, Any]
PathLike = str | Path
Method = Callable[[Any, tuple[Any, ...]], Any]  # method with signature def methodname(self, *args)
Function = Callable[[tuple[Any, ...]], Any]  # function with signature def funcname(*args)

FILENAME_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
READABLE_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
SECONDS_IN_YEAR = 365.25 * 24 * 60 * 60  # with leap years
_VAR_DIR = Path(os.getcwd()) / "var"
DATA_DIR = _VAR_DIR / "data"
OUTPUT_DIR = _VAR_DIR / "output"
LOG_DIR = _VAR_DIR / "logs" if _VAR_DIR.exists() else Path(os.getcwd())


_logging_initialized = False


def read_logs() -> list[str]:
    return [l for p in LOG_DIR.iterdir() if p.name.endswith(".log") or ".log." in p.name
            for l in p.read_text(encoding="utf-8").splitlines()]


def init_log() -> None:
    """Initialize logging.
    """
    global _logging_initialized

    if not _logging_initialized:
        logfile = LOG_DIR / "mtgcards.log"
        log_format = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        log_level = logging.INFO

        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        formatter = logging.Formatter(log_format)
        handler = RotatingFileHandler(logfile, maxBytes=1024*1024*10, backupCount=10)
        handler.setFormatter(formatter)
        handler.setLevel(log_level)
        root_logger.addHandler(handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(log_level)
        root_logger.addHandler(stream_handler)

        _logging_initialized = True


init_log()


# import scraper modules so they get registered for the factory method
from mtgcards.deck.scrapers.aetherhub import DeckScraper
from mtgcards.deck.scrapers.archidekt import DeckScraper
from mtgcards.deck.scrapers.cardhoarder import DeckScraper
from mtgcards.deck.scrapers.cardsrealm import DeckScraper
from mtgcards.deck.scrapers.deckstats import DeckScraper
from mtgcards.deck.scrapers.flexslot import DeckScraper
from mtgcards.deck.scrapers.goldfish import DeckScraper
from mtgcards.deck.scrapers.hareruya import DeckScraper
from mtgcards.deck.scrapers.manastack import DeckScraper
from mtgcards.deck.scrapers.manatraders import DeckScraper
from mtgcards.deck.scrapers.melee import DeckScraper
from mtgcards.deck.scrapers.moxfield import DeckScraper
from mtgcards.deck.scrapers.mtgarenapro import DeckScraper
from mtgcards.deck.scrapers.mtgazone import DeckScraper
from mtgcards.deck.scrapers.mtgdecksnet import DeckScraper
from mtgcards.deck.scrapers.mtgotraders import DeckScraper
from mtgcards.deck.scrapers.mtgtop8 import DeckScraper
from mtgcards.deck.scrapers.penny import DeckScraper
from mtgcards.deck.scrapers.scryfall import DeckScraper
from mtgcards.deck.scrapers.starcitygames import DeckScraper
from mtgcards.deck.scrapers.streamdecker import DeckScraper
from mtgcards.deck.scrapers.tappedout import DeckScraper
from mtgcards.deck.scrapers.tcgplayer import DeckScraper
from mtgcards.deck.scrapers.topdecked import DeckScraper
from mtgcards.deck.scrapers.untapped import DeckScraper
