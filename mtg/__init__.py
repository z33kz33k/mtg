"""

    mtg.__init__.py
    ~~~~~~~~~~~~~~~
    Root package.

    @author: z33k

"""
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable


__appname__ = __name__
__version__ = "0.7"
__description__ = "Scrape data on MtG decks."
__author__ = "z33k"
__license__ = "MIT License"

# type aliases
type Json = dict[str, Any] | list[dict[str, Any]]
type PathLike = str | Path


FILENAME_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
READABLE_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
SECONDS_IN_YEAR = 365.25 * 24 * 60 * 60  # with leap years
VAR_DIR = Path(os.getcwd()) / "var"
DATA_DIR = VAR_DIR / "data"
OUTPUT_DIR = VAR_DIR / "output"
DECKS_DIR = OUTPUT_DIR / "decks"
AVOIDED_DIR = OUTPUT_DIR / "avoided"
LOG_DIR = VAR_DIR / "logs" if VAR_DIR.exists() else Path(os.getcwd())
README = Path(os.getcwd()) / "README.md"
SECRETS = json.loads(Path("secrets.json").read_text(encoding="utf-8"))


_logging_initialized = False


def read_logs() -> list[str]:
    return [l for p in LOG_DIR.iterdir() if p.name.endswith(".log") or ".log." in p.name
            for l in p.read_text(encoding="utf-8").splitlines()]


def init_log() -> None:
    """Initialize logging.
    """
    global _logging_initialized

    if not _logging_initialized:
        logfile = LOG_DIR / "mtg.log"
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


# import scraper modules
# so all their scraper classes get registered in the superclasses' they derive from on time
from mtg.deck.scrapers.aetherhub import DeckScraper
from mtg.deck.scrapers.archidekt import DeckScraper
from mtg.deck.scrapers.cardboardlive import DeckScraper
from mtg.deck.scrapers.cardhoarder import DeckScraper
from mtg.deck.scrapers.cardsrealm import DeckScraper
from mtg.deck.scrapers.cycles import HybridContainerScraper
from mtg.deck.scrapers.deckbox import DeckScraper
from mtg.deck.scrapers.deckstats import DeckScraper
from mtg.deck.scrapers.draftsim import DeckScraper
from mtg.deck.scrapers.edhrec import DeckScraper
from mtg.deck.scrapers.edhtop16 import DeckUrlsContainerScraper
from mtg.deck.scrapers.fireball import DeckScraper
from mtg.deck.scrapers.flexslot import DeckScraper
from mtg.deck.scrapers.goldfish import DeckScraper
from mtg.deck.scrapers.hareruya import DeckScraper
from mtg.deck.scrapers.magic import DeckScraper
from mtg.deck.scrapers.magicblogs import HybridContainerScraper
from mtg.deck.scrapers.magicville import DeckScraper
from mtg.deck.scrapers.manabox import DeckScraper
from mtg.deck.scrapers.manastack import DeckScraper
from mtg.deck.scrapers.manatraders import DeckScraper
from mtg.deck.scrapers.melee import DeckScraper
from mtg.deck.scrapers.moxfield import DeckScraper
from mtg.deck.scrapers.mtgarenapro import DeckScraper
from mtg.deck.scrapers.mtgazone import DeckScraper
from mtg.deck.scrapers.mtgcircle import DeckScraper
from mtg.deck.scrapers.mtgdecksnet import DeckScraper
from mtg.deck.scrapers.mtgjson import DeckScraper
from mtg.deck.scrapers.mtgo import DeckScraper
from mtg.deck.scrapers.mtgstocks import DeckScraper
from mtg.deck.scrapers.mtgotraders import DeckScraper
from mtg.deck.scrapers.mtgtop8 import DeckScraper
from mtg.deck.scrapers.paupermtg import DeckScraper
from mtg.deck.scrapers.pauperwave import HybridContainerScraper
from mtg.deck.scrapers.penny import DeckScraper
from mtg.deck.scrapers.searchit import DeckScraper
from mtg.deck.scrapers.seventeen import DeckScraper
from mtg.deck.scrapers.scryfall import DeckScraper
from mtg.deck.scrapers.scg import DeckScraper
from mtg.deck.scrapers.streamdecker import DeckScraper
from mtg.deck.scrapers.tappedout import DeckScraper
from mtg.deck.scrapers.tcdecks import DeckScraper
from mtg.deck.scrapers.tcgplayer import DeckScraper
from mtg.deck.scrapers.topdeck import DeckUrlsContainerScraper
from mtg.deck.scrapers.topdecked import DeckScraper
from mtg.deck.scrapers.untapped import DeckScraper
from mtg.deck.scrapers.wotc import HybridContainerScraper
