"""

    mtg.deck.scrapers.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Abstract deck scrapers.

    @author: z33k

"""
import logging
from abc import abstractmethod
from typing import Optional, Type

import backoff
from bs4 import BeautifulSoup, Tag
from requests import ConnectionError, HTTPError, ReadTimeout
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException

from mtg import Json
from mtg.deck import Deck, DeckParser, InvalidDeck
from mtg.gstate import UrlsStateManager
from mtg.utils import ParsingError, timed
from mtg.utils.scrape import ScrapingError, getsoup
from mtg.utils.scrape import Throttling, extract_source, throttle
from mtg.utils.scrape.dynamic import get_dynamic_soup

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


_Collected = str | Tag | Json


class ContainerScraper(DeckParser):
    """Abstract base container scraper.

    Note: container scrapers don't scrape their page by themselves. Instead, they only collect
    relevant deck-containing links/tags/JSON and delegate this work to their sub-scrapers or
    sub-parsers. Still, occasionally, a container scraper may need to actually parse some part of
    their page (e.g. to gather some data common (and therefore out of scope) for all its
    sub-parsers). Hence, it derives from DeckParser and not from DeckScraper.
    """
    CONTAINER_NAME = None
    _REGISTRY: set[Type["ContainerScraper"]] | None = None
    XPATH, CONSENT_XPATH = "", ""
    API_URL_TEMPLATE = ""
    HEADERS = None

    @property
    def url(self) -> str:
        return self._url

    @classmethod
    def short_name(cls) -> str:
        if not cls.CONTAINER_NAME:
            return ""
        try:
            *_, name = cls.CONTAINER_NAME.split()
            return name
        except ValueError:
            return cls.CONTAINER_NAME

    @property
    def _error_msg(self) -> str:
        if not self.CONTAINER_NAME:
            return "Data not available"
        return f"{self.short_name().title()} data not available"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(metadata)
        url = url.removesuffix("/")
        self._validate_url(url)
        self._url, self._metadata = self.sanitize_url(url), metadata or {}
        if "container_url" in self._metadata:
            self._metadata["outer_container_url"] = self._metadata["container_url"]
        self._metadata["container_url"] = self.url
        self._soup: BeautifulSoup | None = None

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

    def _pre_parse(self) -> None:  # override
        if self.API_URL_TEMPLATE:  # JSON-based, soup not needed
            return
        if self.XPATH:
            try:
                self._soup, _, _ = get_dynamic_soup(
                    self.url, self.XPATH, consent_xpath=self.CONSENT_XPATH)
            except TimeoutException:
                raise ScrapingError(self._error_msg)
        else:
            self._soup = getsoup(self.url, self.HEADERS)
        if not self._soup:
            raise ScrapingError(self._error_msg)

    def _parse_metadata(self) -> None:  # override
        pass

    def _parse_decklist(self) -> None:  # override
        pass

    def _gather(self) -> list[_Collected] | tuple[list[str], list[str]]:
        try:
            self._pre_parse()
        except ScrapingError:
            _log.warning(self._error_msg)
            return []
        return self._collect()

    @abstractmethod
    def _collect(self) -> list[_Collected] | tuple[list[str], list[str]]:
        raise NotImplementedError

    @abstractmethod
    def scrape(self) -> list[Deck]:
        raise NotImplementedError


class DeckUrlsContainerScraper(ContainerScraper):
    """Abstract scraper of deck-links-containing pages.
    """
    THROTTLING = DeckScraper.THROTTLING
    _REGISTRY: set[Type["DeckUrlsContainerScraper"]] = set()
    DECK_SCRAPERS: tuple[Type[DeckScraper], ...] = ()

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._urls_manager = UrlsStateManager()
        self._deck_urls = []

    @staticmethod
    @abstractmethod
    def is_container_url(url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def _collect(self) -> list[str]:
        raise NotImplementedError

    @classmethod
    def _dispatch_deck_scraper(
            cls, url: str, metadata: Json | None = None) -> Optional[DeckScraper]:
        for scraper_type in cls.DECK_SCRAPERS:
            if scraper_type.is_deck_url(url):
                return scraper_type(url, metadata)
        return None

    def _process_deck_urls(self) -> list[Deck]:
        decks = []
        for i, deck_url in enumerate(self._deck_urls, start=1):
            scraper = self._dispatch_deck_scraper(deck_url, dict(self._metadata))
            if not scraper:
                continue
            sanitized_deck_url = scraper.sanitize_url(deck_url)
            if self._urls_manager.is_scraped(sanitized_deck_url):
                _log.info(f"Skipping already scraped deck URL: {sanitized_deck_url!r}...")
            elif self._urls_manager.is_failed(sanitized_deck_url):
                _log.info(f"Skipping already failed deck URL: {sanitized_deck_url!r}...")
            else:
                throttle(*self.THROTTLING)
                _log.info(f"Scraping deck {i}/{len(self._deck_urls)}...")
                deck = None
                try:
                    deck = scraper.scrape()
                except ElementClickInterceptedException:
                    _log.warning("Unable to click on a deck link with Selenium. Skipping...")
                    self._urls_manager.add_failed(sanitized_deck_url)
                    continue
                if deck:
                    deck_name = f"{deck.name!r} deck" if deck.name else "Deck"
                    _log.info(f"{deck_name} scraped successfully")
                    decks.append(deck)
                    self._urls_manager.add_scraped(sanitized_deck_url)
                else:
                    self._urls_manager.add_failed(sanitized_deck_url)

        return decks

    # override
    @timed("container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def scrape(self) -> list[Deck]:
        self._deck_urls = [url.removesuffix("/") for url in self._gather()]
        _log.info(
            f"Gathered {len(self._deck_urls)} deck URL(s) from a {self.CONTAINER_NAME} at:"
            f" {self.url!r}")
        return self._process_deck_urls()

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


class DeckTagsContainerScraper(ContainerScraper):
    """Abstract scraper of deck-HTML-tags-containing pages.
    """
    _REGISTRY: set[Type["DeckTagsContainerScraper"]] = set()
    DECK_PARSER: Type[TagBasedDeckParser] | None = None

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._metadata["url"] = self.url
        self._metadata["source"] = extract_source(self.url)
        self._deck_tags: list[Tag] = []

    @staticmethod
    @abstractmethod
    def is_container_url(url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def _collect(self) -> list[Tag]:
        raise NotImplementedError

    # override
    @timed("container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def scrape(self) -> list[Deck]:
        self._deck_tags = self._gather()
        _log.info(
            f"Gathered {len(self._deck_tags)} deck tag(s) from a {self.CONTAINER_NAME} at:"
            f" {self.url!r}")
        decks = []
        for i, deck_tag in enumerate(self._deck_tags, start=1):
            try:
                d = self.DECK_PARSER(deck_tag, dict(self._metadata)).parse(
                    suppress_invalid_deck=False, suppress_parsing_errors=False)
                if d:
                    decks.append(d)
                    _log.info(f"Parsed deck {i}/{len(self._deck_tags)}: {d.name!r}")
            except (AttributeError, ParsingError, InvalidDeck) as err:
                _log.warning(f"Failed to parse deck {i}/{len(self._deck_tags)}: {err}. Skipping...")
                continue

        return decks

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


class DecksJsonContainerScraper(ContainerScraper):
    """Abstract scraper of deck-JSON-containing pages.
    """
    _REGISTRY: set[Type["DecksJsonContainerScraper"]] = set()
    DECK_PARSER: Type[JsonBasedDeckParser] | None = None

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._metadata["url"] = self.url
        self._metadata["source"] = extract_source(self.url)
        self._decks_data: list[Json] = []

    @staticmethod
    @abstractmethod
    def is_container_url(url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def _collect(self) -> list[Json]:
        raise NotImplementedError

    # override
    @timed("container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def scrape(self) -> list[Deck]:
        self._decks_data = self._gather()
        _log.info(
            f"Gathered data for {len(self._decks_data)} deck(s) from a {self.CONTAINER_NAME} "
            f"at: {self.url!r}")
        decks = []
        for i, deck_data in enumerate(self._decks_data, start=1):
            d = self.DECK_PARSER(deck_data, dict(self._metadata)).parse()
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


class HybridContainerScraper(DeckUrlsContainerScraper):
    """Abstract scraper of both deck and deck container URLs.

    This scraper acts as regular scraper of deck URLs containing pages, insofar as it encounters
    only deck URLs within the scraped page. However, on encountering a link leading to another
    decks containing page, it dispatches work to another ContainerScraper. Therefore, it's both
    hybrid and nested.
    """
    _REGISTRY: set[Type["HybridContainerScraper"]] = set()  # override
    CONTAINER_SCRAPERS: tuple[Type[ContainerScraper], ...] = ()

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._container_urls = []

    @staticmethod
    @abstractmethod
    def is_container_url(url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def _collect(self) -> tuple[list[str], list[str]]:  # override
        raise NotImplementedError

    def _gather(self) -> tuple[list[str], list[str]]:  # override
        try:
            self._pre_parse()
        except ScrapingError:
            _log.warning(self._error_msg)
            return [], []
        return self._collect()

    @classmethod
    def _dispatch_container_scraper(
            cls, url: str, metadata: Json | None = None) -> Optional[ContainerScraper]:
        for scraper_type in cls.CONTAINER_SCRAPERS:
            if scraper_type.is_container_url(url):
                return scraper_type(url, metadata)
        return None

    def _get_links_from_tag(
            self, links_tag: Tag | None, url_template="") -> tuple[list[str], list[str]]:
        """Get all links from the container tag or the soup, and clean them up.

        Args:
            links_tag: a BeautifulSoup tag containing links (or the whole soup if not provided)
            url_template: template to obtain absolute URLs from relative ones (e.g. 'https://aetherhub.com{}')
        """
        tag = links_tag if links_tag is not None else self._soup
        links = {t.attrs["href"].removesuffix("/") for t in tag.find_all("a", href=lambda h: h)}
        if url_template:
            prefix = url_template[:-2]
            links = {url_template.format(l) if not l.startswith(prefix) else l for l in links}
        deck_urls = sorted(l for l in links if any(ds.is_deck_url(l) for ds in self.DECK_SCRAPERS))
        container_urls = sorted(
            l for l in links if any(cs.is_container_url(l) for cs in self.CONTAINER_SCRAPERS))
        return deck_urls, container_urls

    def process_container_urls(self) -> list[Deck]:
        decks = []
        _log.info(
            f"Gathered {len(self._container_urls)} container "
            f"URL(s) from a {self.CONTAINER_NAME} at: {self.url!r}")
        for i, url in enumerate(self._container_urls, start=1):
            if scraper := self._dispatch_container_scraper(url, dict(self._metadata)):
                sanitized_url = scraper.sanitize_url(url)
                if self._urls_manager.is_scraped(sanitized_url):
                    _log.info(
                        f"Skipping already scraped {scraper.short_name()} URL: "
                        f"{sanitized_url!r}...")
                elif self._urls_manager.is_failed(sanitized_url):
                    _log.info(
                        f"Skipping already failed {scraper.short_name()} URL: "
                        f"{sanitized_url!r}...")
                else:
                    _log.info(
                        f"Scraping container URL {i}/{len(self._container_urls)} "
                        f"({scraper.short_name()})...")
                    container_decks = scraper.scrape()
                    if not container_decks:
                        self._urls_manager.add_failed(sanitized_url)
                    else:
                        decks += [d for d in container_decks if d not in decks]
                        self._urls_manager.add_scraped(sanitized_url)
        return decks

    # override
    @timed("nested container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def scrape(self) -> list[Deck]:
        decks = []
        self._deck_urls, self._container_urls = self._gather()
        if self._deck_urls:
            _log.info(
                f"Gathered {len(self._deck_urls)} deck URL(s) from a {self.CONTAINER_NAME} at:"
                f" {self.url!r}")
            decks.extend(self._process_deck_urls())
        if self._container_urls:
            decks += self.process_container_urls()
        if not decks:
            _log.info(f"Nothing gathered from a {self.CONTAINER_NAME} at: {self.url!r}")
            self._urls_manager.add_failed(self.url)
        return decks

    # override
    @classmethod
    def registered(
            cls,
            scraper_type: Type["HybridContainerScraper"]) -> Type["HybridContainerScraper"]:
        """Class decorator for registering subclasses of HybridContainerScraper.
        """
        if issubclass(scraper_type, HybridContainerScraper):
            cls._REGISTRY.add(scraper_type)
        else:
            raise TypeError(f"Not a subclass of HybridContainerScraper: {scraper_type!r}")
        return scraper_type

    # override
    @classmethod
    def from_url(
            cls, url: str, metadata: Json | None = None) -> Optional["HybridContainerScraper"]:
        for scraper_type in cls._REGISTRY:
            if scraper_type.is_container_url(url):
                return scraper_type(url, metadata)
        return None
