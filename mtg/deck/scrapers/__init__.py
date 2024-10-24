"""

    mtg.deck.scrapers.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Deck scrapers.

    @author: z33k

"""
import json
import logging
from abc import abstractmethod
from typing import Callable, Optional, Type

import backoff
from bs4 import BeautifulSoup
from requests import ConnectionError, ReadTimeout

from mtg import Json
from mtg.deck import Deck, DeckParser, InvalidDeck
from mtg.utils.scrape import Throttling, extract_source, throttle
from mtg.scryfall import all_formats
from mtg.utils import ParsingError, timed
from mtg.utils.scrape import ScrapingError

_log = logging.getLogger(__name__)


SANITIZED_FORMATS = {
    "1v1 commander": "commander",
    "archon": "commander",
    "artisan historic": "historic",
    "artisanhistoric": "historic",
    "australian highlander": "commander",
    "australianhighlander": "commander",
    "canadian highlander": "commander",
    "canadianhighlander": "commander",
    "cedh": "commander",
    "commander 1v1": "commander",
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
    "oldschool 93/94": "oldschool",
    "past standard": "standard",
    "pauper edh": "paupercommander",
    "pauperedh": "paupercommander",
}


class DeckScraper(DeckParser):
    THROTTLING = Throttling(0.6, 0.15)
    _REGISTRY: set[Type["DeckScraper"]] = set()

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
                self._metadata["format"] = fmt
            else:
                _log.warning(f"Irregular format: {fmt!r}")
                if self._metadata.get("format"):
                    del self._metadata["format"]
                self._metadata["irregular_format"] = fmt

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
            self, suppress_parsing_errors=True, suppress_invalid_deck=True) -> Deck | None: # override
        return self.scrape(
            suppress_scraping_errors=suppress_parsing_errors,
            suppress_invalid_deck=suppress_invalid_deck
        )

    def _build_deck(self) -> Deck:
        return Deck(
            self._maindeck, self._sideboard, self._commander, self._partner_commander,
            self._companion, self._metadata)

    def _scrape(
            self, throttled=False, suppress_parsing_errors=True, suppress_scraping_errors=True,
            suppress_invalid_deck=True) -> Deck | None:
        if throttled:
            throttle(*self.THROTTLING)
        try:
            self._pre_parse()
            self._parse_metadata()
            self._parse_deck()
        except ScrapingError as se:
            if not suppress_scraping_errors:
                _log.error(f"Scraping failed with: {se}")
                raise se
            _log.warning(f"Scraping failed with: {se}")
            return None
        except ParsingError as pe:
            if not suppress_parsing_errors:
                _log.error(f"Scraping failed with: {pe}")
                raise pe
            _log.warning(f"Scraping failed with: {pe}")
            return None
        try:
            return self._build_deck()
        except InvalidDeck as err:
            if not suppress_invalid_deck:
                _log.error(f"Scraping failed with: {err}")
                raise err
            _log.warning(f"Scraping failed with: {err}")
            return None

    @backoff.on_exception(  # TODO: see if more errors should be such handled
        backoff.expo, (ConnectionError, ReadTimeout), max_time=60)
    def _scrape_with_backoff(
            self, throttled=False, suppress_parsing_errors=True, suppress_scraping_errors=True,
            suppress_invalid_deck=True) -> Deck | None:
        return self.scrape(
            throttled=throttled, suppress_parsing_errors=suppress_parsing_errors,
            suppress_scraping_errors=suppress_scraping_errors,
            suppress_invalid_deck=suppress_invalid_deck)

    def scrape(
            self, throttled=False, suppress_parsing_errors=True, suppress_scraping_errors=True,
            suppress_invalid_deck=True) -> Deck | None:
        try:
            return self._scrape(
                throttled=throttled,
                suppress_parsing_errors=suppress_parsing_errors,
                suppress_scraping_errors=suppress_scraping_errors,
                suppress_invalid_deck=suppress_invalid_deck
            )
        except (ConnectionError, ReadTimeout) as e:
            _log.warning(f"Scraping failed with: {e}. Re-trying with backoff...")
            return self._scrape_with_backoff(
                throttled=throttled,
                suppress_parsing_errors=suppress_parsing_errors,
                suppress_scraping_errors=suppress_scraping_errors,
                suppress_invalid_deck=suppress_invalid_deck
            )

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


class ContainerScraper:
    CONTAINER_NAME = None
    _REGISTRY: set[Type["ContainerScraper"]] = set()
    _DECK_SCRAPER: Type[DeckScraper] | None = None

    @property
    def url(self) -> str:
        return self._url

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        self._validate_url(url)
        self._url, self._metadata = self.sanitize_url(url), metadata or {}
        self._soup: BeautifulSoup | None = None
        self._deck_urls = []

    @classmethod
    def _validate_url(cls, url):
        if url and not cls.is_container_url(url):
            raise ValueError(f"Not a {cls.CONTAINER_NAME} URL: {url!r}")

    @staticmethod
    @abstractmethod
    def is_container_url(url: str) -> bool:
        raise NotImplementedError

    @staticmethod
    def sanitize_url(url: str) -> str:
        if "?" in url:
            url, rest = url.split("?", maxsplit=1)
        return url.removesuffix("/")

    @abstractmethod
    def _collect(self) -> list[str]:
        raise NotImplementedError

    def _process_decks(self, *already_scraped_deck_urls: str) -> list[Deck]:
        _log.info(
            f"Gathered {len(self._deck_urls)} deck URL(s) from a {self.CONTAINER_NAME} at:"
            f" {self.url!r}")
        decks = []
        for i, url in enumerate(self._deck_urls, start=1):
            if url in already_scraped_deck_urls:
                _log.info(f"Skipping already scraped deck URL: {url!r}")
                continue
            else:
                throttle(*DeckScraper.THROTTLING)
                _log.info(f"Scraping deck {i}/{len(self._deck_urls)}...")
                deck = None
                if self._DECK_SCRAPER:
                    deck = self._DECK_SCRAPER(url, dict(self._metadata)).scrape()
                else:
                    if scraper := DeckScraper.from_url(url, dict(self._metadata)):
                        deck = scraper.scrape()
                if deck:
                    deck_name = f"{deck.name!r} deck" if deck.name else "Deck"
                    _log.info(f"{deck_name} scraped successfully")
                    decks.append(deck)
        return decks

    def _scrape(self, *already_scraped_deck_urls: str) -> list[Deck]:
        self._deck_urls = self._collect()
        return self._process_decks(*already_scraped_deck_urls)

    @backoff.on_exception(
        backoff.expo, (ConnectionError, ReadTimeout), max_time=60)
    def _scrape_with_backoff(self, *already_scraped_deck_urls: str) -> list[Deck]:
        return self._scrape(*already_scraped_deck_urls)

    @timed("container scraping", precision=2)
    def scrape(self, *already_scraped_deck_urls: str) -> list[Deck]:
        try:
            return self._scrape(*already_scraped_deck_urls)
        except (ConnectionError, ReadTimeout) as e:
            _log.warning(
                f"Scraping {self.CONTAINER_NAME} failed with: {e}. Re-trying with backoff...")
            return self._scrape_with_backoff(*already_scraped_deck_urls)

    @classmethod
    def registered(cls, scraper_type: Type["ContainerScraper"]) -> Type["ContainerScraper"]:
        """Class decorator for registering subclasses of DeckContainerScraper.
        """
        if issubclass(scraper_type, ContainerScraper):
            cls._REGISTRY.add(scraper_type)
        else:
            raise TypeError(f"Not a subclass of DeckContainerScraper: {scraper_type!r}")
        return scraper_type

    @classmethod
    def from_url(cls, url: str, metadata: Json | None = None) -> Optional["ContainerScraper"]:
        for scraper_type in cls._REGISTRY:
            if scraper_type.is_container_url(url):
                return scraper_type(url, metadata)
        return None
