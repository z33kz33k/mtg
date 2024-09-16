"""

    mtgcards.deck.scrapers.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Deck scrapers.

    @author: z33k

"""
import json
import logging
from abc import abstractmethod
from typing import Callable, Optional, Type

from bs4 import BeautifulSoup

from mtgcards import Json
from mtgcards.deck import Deck, DeckParser, InvalidDeck
from mtgcards.utils.scrape import Throttling, extract_source, throttle
from mtgcards.scryfall import all_formats
from mtgcards.utils import ParsingError

_log = logging.getLogger(__name__)


SANITIZED_FORMATS = {
    "archon": "commander",
    "artisan historic": "historic",
    "artisanhistoric": "historic",
    "australian highlander": "commander",
    "australianhighlander": "commander",
    "canadian highlander": "commander",
    "canadianhighlander": "commander",
    "cedh": "commander",
    "commander / edh": "commander",
    "commander/edh": "commander",
    "commanderprecon": "commander",
    "commanderprecons": "commander",
    "duel commander": "duel",
    "duelcommander": "duel",
    "edh": "commander",
    "european highlander": "commander",
    "europeanhighlander": "commander",
    "future standard": "future",
    "highlander australian": "commander",
    "highlander canadian": "commander",
    "highlander european": "commander",
    "highlander": "commander",
    "highlanderaustralian": "commander",
    "highlandercanadian": "commander",
    "highlandereuropean": "commander",
    "historic brawl": "brawl",
    "historic pauper": "historic",
    "historic-pauper": "historic",
    "historicbrawl": "brawl",
    "historicpauper": "historic",
    "no banned list modern": "modern",
    "pauper edh": "paupercommander",
    "pauperedh": "paupercommander",
}


class DeckScraper(DeckParser):
    THROTTLING = Throttling(0.6, 0.15)
    _REGISTRY = set()

    @property
    def url(self) -> str:
        return self._url

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        self._validate_url(url)
        super().__init__(metadata)
        self._url = self.sanitize_url(url)
        self._soup: BeautifulSoup | None = None
        self._metadata["url"] = self.url
        self._metadata["source"] = extract_source(self.url)

    @classmethod
    def _validate_url(cls, url):
        if url and not cls.is_deck_url(url):
            raise ValueError(f"Not a deck URL: {url!r}")

    @staticmethod
    @abstractmethod
    def is_deck_url(url: str) -> bool:
        raise NotImplementedError

    @staticmethod
    def sanitize_url(url: str) -> str:
        if "?" in url:
            url, rest = url.split("?", maxsplit=1)
        return url.removesuffix("/")

    def _update_fmt(self, fmt: str) -> None:
        fmt = fmt.strip().lower()
        fmt = SANITIZED_FORMATS.get(fmt, fmt)
        if fmt != self.fmt:
            if fmt in all_formats():
                if self.fmt:
                    _log.warning(
                        f"Earlier specified format: {self.fmt!r} overwritten with a scraped "
                        f"one: {fmt!r}")
                self._metadata["format"] = fmt
            else:
                _log.warning(f"Not a valid format: {fmt!r}")

    def dissect_js(
            self, start_hook: str, end_hook: str,
            end_processor: Callable[[str], str] | None = None) -> Json:
        text = self._soup.find(
            "script", string=lambda s: s and start_hook in s and end_hook in s).text
        *_, first = text.split(start_hook)
        second, *_ = first.split(end_hook)
        if end_processor:
            second = end_processor(second)
        return json.loads(second)

    @abstractmethod
    def _pre_parse(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _parse_metadata(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _parse_deck(self) -> None:
        raise NotImplementedError

    def parse(
            self, supress_parsing_errors=True, supress_invalid_deck=True) -> Deck | None: # override
        return self.scrape(
            supress_scraping_errors=supress_parsing_errors,
            supress_invalid_deck=supress_invalid_deck
        )

    def _build_deck(self) -> Deck:
        return Deck(
            self._maindeck, self._sideboard, self._commander, self._partner_commander,
            self._companion, self._metadata)

    def scrape(
            self, throttled=False, supress_scraping_errors=True,
            supress_invalid_deck=True) -> Deck | None:
        if throttled:
            throttle(*self.THROTTLING)
        try:
            self._pre_parse()
            self._parse_metadata()
            self._parse_deck()
        except ParsingError as pe:
            if not supress_scraping_errors:
                _log.error(f"Scraping failed with: {pe}")
                raise pe
            _log.warning(f"Scraping failed with: {pe}")
            return None
        try:
            return self._build_deck()
        except InvalidDeck as err:
            if not supress_invalid_deck:
                _log.error(f"Scraping failed with: {err}")
                raise err
            _log.warning(f"Scraping failed with: {err}")
            return None

    @classmethod
    def registered(cls, scraper_type: Type["DeckScraper"]) -> Type["DeckScraper"]:
        """Class decorator for registering subclasses of DeckScraper.
        """
        if issubclass(scraper_type, DeckScraper):
            cls._REGISTRY.add(scraper_type)
        else:
            raise TypeError(f"Not a subclass of DeckScraper: {scraper_type!r}")
        return scraper_type

    @classmethod
    def from_url(cls, url: str, metadata: Json | None = None) -> Optional["DeckScraper"]:
        for scraper_type in cls._REGISTRY:
            if scraper_type.is_deck_url(url):
                return scraper_type(url, metadata)
        return None
