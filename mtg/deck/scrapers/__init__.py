"""

    mtg.deck.scrapers.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Deck scrapers.

    @author: z33k

"""
import logging
from abc import abstractmethod
from typing import Iterable, Optional, Type

import backoff
from bs4 import BeautifulSoup, Tag
from requests import ConnectionError, HTTPError, ReadTimeout
from selenium.common.exceptions import ElementClickInterceptedException

from mtg import Json
from mtg.deck import Deck, DeckParser, InvalidDeck
from mtg.utils import ParsingError, timed
from mtg.utils.scrape import ScrapingError
from mtg.utils.scrape import Throttling, extract_source, throttle

_log = logging.getLogger(__name__)


class DeckScraper(DeckParser):
    """Abstract deck scraper.

    Deck scrapers process a single, decklist and metadata holding, URL and return a Deck
    object (if able).
    """
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

    @abstractmethod
    def _pre_parse(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _parse_metadata(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _parse_decklist(self) -> None:
        raise NotImplementedError

    def parse(
            self, suppress_parsing_errors=True, suppress_invalid_deck=True) -> Deck | None: # override
        return self.scrape(
            suppress_scraping_errors=suppress_parsing_errors,
            suppress_invalid_deck=suppress_invalid_deck
        )

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
            self._parse_decklist()
        except ScrapingError as se:
            if not suppress_scraping_errors:
                _log.error(f"Scraping failed with: {se}")
                raise se
            _log.error(f"Scraping failed with: {se}")
            return None
        except ParsingError as pe:
            if not suppress_parsing_errors:
                _log.error(f"Scraping failed with: {pe}")
                raise pe
            _log.error(f"Scraping failed with: {pe}")
            return None
        try:
            return self._build_deck()
        except InvalidDeck as err:
            if not suppress_invalid_deck:
                _log.error(f"Scraping failed with: {err}")
                raise err
            _log.error(f"Scraping failed with: {err}")
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


class TagBasedDeckParser(DeckParser):
    """Abstract HTML tag based deck parser.

    HTML tag based parsers process a single, decklist and metadata holding, HTML tag extracted
    from a webpage and return a Deck object (if able).
    """
    def __init__(self, deck_tag: Tag,  metadata: Json | None = None) -> None:
        super().__init__(metadata)
        self._deck_tag = deck_tag

    def _pre_parse(self) -> None:  # override
        pass

    @abstractmethod
    def _parse_metadata(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _parse_decklist(self) -> None:
        raise NotImplementedError


# TODO: use this abstraction in deck scrapers that process JSON
class JsonBasedDeckParser(DeckParser):
    """Abstract JSON data based deck parser.

    JSON data based parsers process a single, decklist and metadata holding, piece of JSON data
    either dissected from a webpage's JavaScript code or obtained via a separate JSON API
    request and return a Deck object (if able).
    """
    def __init__(self,  deck_data: Json, metadata: Json | None = None) -> None:
        super().__init__(metadata)
        self._deck_data = deck_data

    def _pre_parse(self) -> None:  # override
        pass

    @abstractmethod
    def _parse_metadata(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _parse_decklist(self) -> None:
        raise NotImplementedError


class DeckUrlsContainerScraper:
    """Abstract scraper of deck-links-containing pages.
    """
    CONTAINER_NAME = None
    THROTTLING = DeckScraper.THROTTLING
    _REGISTRY: set[Type["DeckUrlsContainerScraper"]] = set()
    _DECK_SCRAPER: Type[DeckScraper] | None = None

    @property
    def url(self) -> str:
        return self._url

    @property
    def _error_msg(self) -> str:
        if not self.CONTAINER_NAME:
            return "Data not available"
        *_, name = self.CONTAINER_NAME.split()
        return f"{name.title()} data not available"

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

    def _process_deck_urls(
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
        return self._process_deck_urls(already_scraped_deck_urls, already_failed_deck_urls)

    @classmethod
    def registered(
            cls,
            scraper_type: Type["DeckUrlsContainerScraper"]) -> Type["DeckUrlsContainerScraper"]:
        """Class decorator for registering subclasses of UrlBasedContainerScraper.
        """
        if issubclass(scraper_type, DeckUrlsContainerScraper):
            cls._REGISTRY.add(scraper_type)
        else:
            raise TypeError(f"Not a subclass of DeckUrlsContainerScraper: {scraper_type!r}")
        return scraper_type

    @classmethod
    def from_url(
            cls, url: str, metadata: Json | None = None) -> Optional["DeckUrlsContainerScraper"]:
        for scraper_type in cls._REGISTRY:
            if scraper_type.is_container_url(url):
                return scraper_type(url, metadata)
        return None


class DeckTagsContainerScraper:
    """Abstract scraper of deck-HTML-tags-containing pages.
    """
    CONTAINER_NAME = None
    _REGISTRY: set[Type["DeckTagsContainerScraper"]] = set()
    _DECK_PARSER: Type[TagBasedDeckParser] | None = None

    @property
    def url(self) -> str:
        return self._url

    @property
    def _error_msg(self) -> str:
        if not self.CONTAINER_NAME:
            return "Data not available"
        *_, name = self.CONTAINER_NAME.split()
        return f"{name.title()} data not available"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        url = url.removesuffix("/")
        self._validate_url(url)
        self._url, self._metadata = self.sanitize_url(url), metadata or {}
        self._soup: BeautifulSoup | None = None
        self._deck_tags: list[Tag] = []

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
    def _collect(self) -> list[Tag]:
        raise NotImplementedError

    @timed("container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def scrape(self) -> list[Deck]:
        self._deck_tags = self._collect()
        _log.info(
            f"Gathered {len(self._deck_tags)} deck tag(s) from a {self.CONTAINER_NAME} at:"
            f" {self.url!r}")
        return [
            d for d in
            [self._DECK_PARSER(tag, dict(self._metadata)).parse() for tag in self._deck_tags]
            if d]

    @classmethod
    def registered(
            cls,
            scraper_type: Type["DeckTagsContainerScraper"]) -> Type["DeckTagsContainerScraper"]:
        """Class decorator for registering subclasses of DeckTagsContainerScraper.
        """
        if issubclass(scraper_type, DeckTagsContainerScraper):
            cls._REGISTRY.add(scraper_type)
        else:
            raise TypeError(f"Not a subclass of DeckTagsContainerScraper: {scraper_type!r}")
        return scraper_type

    @classmethod
    def from_url(
            cls, url: str, metadata: Json | None = None) -> Optional["DeckTagsContainerScraper"]:
        for scraper_type in cls._REGISTRY:
            if scraper_type.is_container_url(url):
                return scraper_type(url, metadata)
        return None


class DecksJsonContainerScraper:
    """Abstract scraper of deck-JSON-containing pages.
    """
    CONTAINER_NAME = None
    _REGISTRY: set[Type["DecksJsonContainerScraper"]] = set()
    _DECK_PARSER: Type[JsonBasedDeckParser] | None = None

    @property
    def url(self) -> str:
        return self._url

    @property
    def _error_msg(self) -> str:
        if not self.CONTAINER_NAME:
            return "Data not available"
        *_, name = self.CONTAINER_NAME.split()
        return f"{name.title()} data not available"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        url = url.removesuffix("/")
        self._validate_url(url)
        self._url, self._metadata = self.sanitize_url(url), metadata or {}
        self._decks_data: list[Json] = []

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
    def _collect(self) -> list[Json]:
        raise NotImplementedError

    @timed("container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def scrape(self) -> list[Deck]:
        self._decks_data = self._collect()
        _log.info(
            f"Gathered data for {len(self._decks_data)} deck(s) from a {self.CONTAINER_NAME} "
            f"at: {self.url!r}")
        decks = []
        for i, deck_data in enumerate(self._decks_data, start=1):
            d = self._DECK_PARSER(deck_data, dict(self._metadata)).parse()
            if d:
                decks.append(d)
                _log.info(f"Parsed deck {i}/{len(self._decks_data)}: {d.name!r}")
        return decks

    @classmethod
    def registered(
            cls,
            scraper_type: Type["DecksJsonContainerScraper"]) -> Type["DecksJsonContainerScraper"]:
        """Class decorator for registering subclasses of DecksJsonContainerScraper.
        """
        if issubclass(scraper_type, DecksJsonContainerScraper):
            cls._REGISTRY.add(scraper_type)
        else:
            raise TypeError(f"Not a subclass of DecksJsonContainerScraper: {scraper_type!r}")
        return scraper_type

    @classmethod
    def from_url(
            cls, url: str, metadata: Json | None = None) -> Optional["DecksJsonContainerScraper"]:
        for scraper_type in cls._REGISTRY:
            if scraper_type.is_container_url(url):
                return scraper_type(url, metadata)
        return None
