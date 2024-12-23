"""

    mtg.deck.scrapers.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Deck scrapers.

    @author: z33k

"""
import logging
from abc import abstractmethod
from typing import Iterable, Optional, Type

import backoff
from bs4 import BeautifulSoup
from requests import ConnectionError, ReadTimeout, HTTPError
from selenium.common.exceptions import ElementClickInterceptedException

from mtg import Json
from mtg.deck import Deck, DeckParser, InvalidDeck, THEMES
from mtg.scryfall import all_formats
from mtg.utils import ParsingError, from_iterable, timed
from mtg.utils.scrape import ScrapingError
from mtg.utils.scrape import Throttling, extract_source, throttle

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
    "centurion": "commander",
    "commander 1v1": "commander",
    "commander / edh": "commander",
    "commander/edh": "commander",
    "commanderprecon": "commander",
    "commanderprecons": "commander",
    "duel commander": "duel",
    "duelcommander": "duel",
    "duelcommanderrussian": "duel",
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
    "old school": "oldschool",
    "oldschool 93/94": "oldschool",
    "past standard": "standard",
    "pauper edh": "paupercommander",
    "pauperedh": "paupercommander",
    "vintage old school": "oldschool",
}


class DeckScraper(DeckParser):
    THROTTLING = Throttling(0.6, 0.15)
    _REGISTRY: set[Type["DeckScraper"]] = set()

    @property
    def url(self) -> str:
        return self._url

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        url = url.removesuffix("/")
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

    def _update_custom_theme(self, prefix: str, custom_theme: str) -> None:
        self._metadata[f"{prefix}_theme"] = custom_theme
        if theme := from_iterable(THEMES, lambda t: t in custom_theme):
            self._metadata["theme"] = theme

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

    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def scrape(
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
    THROTTLING = DeckScraper.THROTTLING
    _REGISTRY: set[Type["ContainerScraper"]] = set()
    _DECK_SCRAPER: Type[DeckScraper] | None = None

    @property
    def url(self) -> str:
        return self._url

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        url = url.removesuffix("/")
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
        return url.removesuffix("/")

    @abstractmethod
    def _collect(self) -> list[str]:
        raise NotImplementedError

    def _process_decks(
            self, already_scraped_deck_urls: Iterable[str],
            already_failed_deck_urls: Iterable[str]) -> tuple[list[Deck], set[str]]:
        decks = []
        already_scraped_deck_urls = {
            url.removesuffix("/").lower() for url in already_scraped_deck_urls}
        already_failed_deck_urls = set(already_failed_deck_urls)
        failed_deck_urls = set()
        for i, deck_url in enumerate(self._deck_urls, start=1):
            scraper = self._DECK_SCRAPER(
                deck_url, dict(self._metadata)) if self._DECK_SCRAPER else DeckScraper.from_url(
                deck_url, dict(self._metadata))
            if not scraper:
                raise ScrapingError(f"Failed to find scraper suitable for deck URL: {deck_url!r}")
            sanitized_deck_url = scraper.sanitize_url(deck_url)
            if sanitized_deck_url.lower() in already_scraped_deck_urls:
                _log.info(f"Skipping already scraped deck URL: {sanitized_deck_url!r}...")
            elif sanitized_deck_url.lower() in already_failed_deck_urls:
                _log.info(f"Skipping already failed deck URL: {sanitized_deck_url!r}...")
            else:
                throttle(*self.THROTTLING)
                _log.info(f"Scraping deck {i}/{len(self._deck_urls)}...")
                deck = None
                try:
                    deck = scraper.scrape()
                except ElementClickInterceptedException:
                    _log.warning("Unable to click on a deck link with Selenium. Skipping...")
                    already_failed_deck_urls.add(sanitized_deck_url.lower())
                    failed_deck_urls.add(sanitized_deck_url.lower())
                    continue
                if deck:
                    deck_name = f"{deck.name!r} deck" if deck.name else "Deck"
                    _log.info(f"{deck_name} scraped successfully")
                    decks.append(deck)
                else:
                    already_failed_deck_urls.add(sanitized_deck_url.lower())
                    failed_deck_urls.add(sanitized_deck_url.lower())

        return decks, failed_deck_urls

    @timed("container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def scrape(
            self, already_scraped_deck_urls: Iterable[str] = (),
            already_failed_deck_urls: Iterable[str] = ()) -> tuple[list[Deck], set[str]]:
        self._deck_urls = [url.removesuffix("/") for url in self._collect()]
        _log.info(
            f"Gathered {len(self._deck_urls)} deck URL(s) from a {self.CONTAINER_NAME} at:"
            f" {self.url!r}")
        return self._process_decks(already_scraped_deck_urls, already_failed_deck_urls)

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
