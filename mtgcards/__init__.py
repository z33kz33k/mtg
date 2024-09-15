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
from mtgcards.deck.scrapers.aetherhub import AetherhubScraper
from mtgcards.deck.scrapers.archidekt import ArchidektScraper
from mtgcards.deck.scrapers.cardhoarder import CardhoarderScraper
from mtgcards.deck.scrapers.cardsrealm import CardsrealmScraper
from mtgcards.deck.scrapers.deckstats import DeckstatsScraper
from mtgcards.deck.scrapers.flexslot import FlexslotScraper
from mtgcards.deck.scrapers.goldfish import GoldfishScraper
from mtgcards.deck.scrapers.hareruya import HareruyaScraper
from mtgcards.deck.scrapers.manastack import ManaStackScraper
from mtgcards.deck.scrapers.manatraders import ManatradersScraper
from mtgcards.deck.scrapers.melee import MeleeGgScraper
from mtgcards.deck.scrapers.moxfield import MoxfieldScraper
from mtgcards.deck.scrapers.mtgarenapro import MtgArenaProScraper
from mtgcards.deck.scrapers.mtgazone import MtgaZoneScraper
from mtgcards.deck.scrapers.mtgdecksnet import MtgDecksNetScraper
from mtgcards.deck.scrapers.mtgotraders import MtgoTradersScraper
from mtgcards.deck.scrapers.mtgtop8 import MtgTop8Scraper
from mtgcards.deck.scrapers.penny import PennyDreadfulMagicScraper
from mtgcards.deck.scrapers.scryfall import ScryfallScraper
from mtgcards.deck.scrapers.starcitygames import StarCityGamesScraper
from mtgcards.deck.scrapers.streamdecker import StreamdeckerScraper
from mtgcards.deck.scrapers.tappedout import TappedoutScraper
from mtgcards.deck.scrapers.tcgplayer import NewPageTcgPlayerScraper, OldPageTcgPlayerScraper
from mtgcards.deck.scrapers.topdecked import TopDeckedScraper, TopDeckedMetadeckScraper
from mtgcards.deck.scrapers.untapped import UntappedProfileDeckScraper, UntappedRegularDeckScraper
