"""

    mtg.deck.scrapers.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Abstract deck scrapers.

    @author: z33k

"""
import logging
from abc import abstractmethod
from typing import Self, Type
from typing import override

import backoff
from bs4 import BeautifulSoup, Tag
from requests import ConnectionError, HTTPError, ReadTimeout
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException

from mtg import Json
from mtg.deck import CardNotFound, Deck, DeckParser, InvalidDeck
from mtg.gstate import UrlsStateManager
from mtg.utils import ParsingError, timed
from mtg.utils.scrape import InaccessiblePage, ScrapingError, Soft404Error, get_links, getsoup, \
    prepend_url
from mtg.utils.scrape import Throttling, extract_source, throttle
from mtg.utils.scrape.dynamic import get_dynamic_soup

_log = logging.getLogger(__name__)


def is_in_domain_but_not_main(url: str, domain: str) -> bool:
    """Check whether the passed URL is of the passed domain but other than exactly this domain.

    Args:
        url: URL to check
        domain: the end-part of URL's domain (including sub-folders, e.g. "pauperwave.com" or "playingmtg/tournaments)
    """
    if f"{domain}/" not in url.lower():
        return False  # not in domain
    if f"{domain}/." in url.lower():
        return False
    *_, rest = url.lower().split(f"{domain}/")
    if not rest:
        return False  # the domain exactly
    return True


class TagBasedDeckParser(DeckParser):
    """Abstract HTML tag based deck parser.

    HTML tag based parsers process a single, decklist and metadata holding, HTML tag extracted
    from a webpage and return a Deck object (if able).
    """
    def __init__(self, deck_tag: Tag,  metadata: Json | None = None) -> None:
        super().__init__(metadata)
        self._deck_tag = deck_tag

    @override
    def _pre_parse(self) -> None:
        pass  # not utilized

    @abstractmethod
    @override
    def _parse_metadata(self) -> None:
        raise NotImplementedError

    @abstractmethod
    @override
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

    @override
    def _pre_parse(self) -> None:
        pass  # not utilized

    @abstractmethod
    @override
    def _parse_metadata(self) -> None:
        raise NotImplementedError

    @abstractmethod
    @override
    def _parse_decklist(self) -> None:
        raise NotImplementedError


class DeckScraper(DeckParser):
    """Abstract deck scraper.

    Deck scrapers process a single, decklist and metadata holding, URL and return a Deck
    object (if able).
    """
    _REGISTRY: set[Type[Self]] = set()
    SELENIUM_PARAMS = {}
    THROTTLING = Throttling(0.6, 0.15)
    API_URL_TEMPLATE = ""
    HEADERS = None
    DATA_FROM_SOUP = False

    @property
    def url(self) -> str:
        return self._url

    @property
    def _error_msg(self) -> str:
        return "Page not available"

    @property
    def _selenium_timeout_msg(self) -> str:
        word = self.SELENIUM_PARAMS.get("xpath")
        word = f"'{word}'" if word else "XPath-defined"
        return f"Selenium timed out looking for {word} element(s)"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        self._validate_url(url)
        url = url.removesuffix("/")
        super().__init__(metadata)
        self._url = self.sanitize_url(url)
        self._soup: BeautifulSoup | None = None  # for HTML-based scraping
        self._clipboard: str | None  = None  # for Selenium-based scraping
        self._data: Json | None = None  # for JSON-based scraping
        self._post_init()

    def _post_init(self) -> None:
        self._metadata["url"] = self.url
        self._metadata["source"] = extract_source(self.url)

    @classmethod
    def _validate_url(cls, url: str) -> None:
        if url and not cls.is_valid_url(url):
            raise ValueError(f"Invalid URL: {url!r}")

    @staticmethod
    @abstractmethod
    def is_valid_url(url: str) -> bool:
        raise NotImplementedError

    # FIXME: this should be a classmethod to enable a re-use of the default logic in subclasses
    @staticmethod
    def sanitize_url(url: str) -> str:
        return url.removesuffix("/")

    def _fetch_soup(self) -> None:
        if self.SELENIUM_PARAMS:
            try:
                self._soup, _, self._clipboard = get_dynamic_soup(
                    self.url, **self.SELENIUM_PARAMS)
            except TimeoutException:
                raise ScrapingError(self._selenium_timeout_msg, scraper=type(self), url=self.url)
        else:
            self._soup = getsoup(self.url, self.HEADERS)

    def _get_data_from_api(self) -> Json:
        raise NotImplementedError

    def _get_data_from_soup(self) -> Json:
        raise NotImplementedError

    def _get_sub_parser(self) -> TagBasedDeckParser | JsonBasedDeckParser | None:
        return None

    def _is_page_inaccessible(self) -> bool:
        return False

    def _is_soft_404_error(self) -> bool:
        return False

    def _validate_soup(self) -> None:
        if not self._soup:
            raise ScrapingError(self._error_msg, scraper=type(self), url=self.url)
        if self._is_page_inaccessible():
            raise InaccessiblePage(scraper=type(self), url=self.url)
        if self._is_soft_404_error():
            raise Soft404Error(scraper=type(self), url=self.url)

    def _validate_data(self) -> None:
        if not self._data:
            raise ScrapingError("Data not available", scraper=type(self), url=self.url)

    @override
    def _pre_parse(self) -> None:
        if self.API_URL_TEMPLATE:  # JSON-based, soup not needed
            self._data = self._get_data_from_api()
            self._validate_data()
        else:
            self._fetch_soup()
            self._validate_soup()
            if self.DATA_FROM_SOUP:
                self._data = self._get_data_from_soup()
                self._validate_data()
        self._sub_parser = self._get_sub_parser()

    @abstractmethod
    @override
    def _parse_metadata(self) -> None:
        raise NotImplementedError

    @abstractmethod
    @override
    def _parse_decklist(self) -> None:
        raise NotImplementedError

    @override
    def parse(
            self, suppress_invalid_deck=True, suppress_card_not_found=True,
            suppress_parsing_errors=False) -> Deck | None:
        raise NotImplementedError  # not utilized

    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def scrape(
            self, throttled=False, suppressed_errors=(ParsingError, ScrapingError)) -> Deck | None:
        if throttled:
            throttle(*self.THROTTLING)
        try:
            self._pre_parse()
            self._parse_metadata()
            self._parse_decklist()
            return self._build_deck()
        except (InvalidDeck, CardNotFound) as err:
            _log.warning(f"Scraping failed with: {err!r}")
            return None
        except suppressed_errors as err:
            if isinstance(err, ParsingError) and not isinstance(err, (InvalidDeck, CardNotFound)):
                err = ScrapingError(str(err), type(self), self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            return None


    @classmethod
    def registered(cls, scraper_type: Type[Self]) -> Type[Self]:
        """Class decorator for registering subclasses of this class.
        """
        if issubclass(scraper_type, cls):
            cls._REGISTRY.add(scraper_type)
        else:
            raise TypeError(f"Not a subclass of {cls.__name__}: {scraper_type!r}")
        return scraper_type

    @classmethod
    def from_url(cls, url: str, metadata: Json | None = None) -> Self | None:
        for scraper_type in cls._REGISTRY:
            if scraper_type.is_valid_url(url):
                return scraper_type(url, metadata)
        return None

    @classmethod
    def get_registered_scrapers(cls) -> set[Type[Self]]:
        return set(cls._REGISTRY)


type Collected = list[str | Tag | Json] | tuple[list[str], list[Tag], list[Json], list[str]]


class ContainerScraper(DeckScraper):
    """Abstract base container scraper.

    Note: container scrapers don't scrape their page by themselves. Instead, they only collect
    relevant deck-containing links/tags/JSON and delegate this work to their sub-scrapers or
    sub-parsers. Still, occasionally, a container scraper may need to actually parse some part of
    their page (e.g. to gather some data common (and therefore out of scope) for all its
    sub-parsers).
    """
    _REGISTRY: set[Type[Self]] = set()  # override
    CONTAINER_NAME = None

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
    @override
    def _error_msg(self) -> str:
        if not self.CONTAINER_NAME:
            return "Data not available"
        return f"{self.short_name().title()} data not available"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._urls_manager = UrlsStateManager()

    @override
    def _post_init(self) -> None:
        self._metadata["container_url"] = self.url

    # DeckParser API
    @override
    def _parse_metadata(self) -> None:
        pass

    @override
    def _parse_decklist(self) -> None:
        raise NotImplementedError  # not utilized

    @override
    def _build_deck(self) -> Deck | None:
        raise NotImplementedError  # not utilized

    # partly redefined DeckScraper API
    @staticmethod
    @abstractmethod
    @override
    def is_valid_url(url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    @override
    def scrape(self) -> list[Deck]:
        raise NotImplementedError

    # ContainerScraper API
    def _gather(self) -> Collected:
        try:
            self._pre_parse()
            self._parse_metadata()
            return self._collect()
        except ParsingError as pe:
            err = ScrapingError(str(pe), type(self), self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            return []
        except ScrapingError as e:
            _log.warning(f"Scraping failed with: {e!r}")
            return []

    @abstractmethod
    def _collect(self) -> Collected:
        raise NotImplementedError


# only for registration
class FolderContainerScraper(ContainerScraper):
    _REGISTRY: set[Type[Self]] = set()  # override

    @staticmethod
    @abstractmethod
    @override
    def is_valid_url(url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    @override
    def scrape(self) -> list[Deck]:
        raise NotImplementedError

    @abstractmethod
    def _collect(self) -> Collected:
        raise NotImplementedError

    @classmethod
    @override
    def registered(cls, scraper_type: Type[Self]) -> Type[Self]:
        """Class decorator for registering folder container scrapers.
        """
        if issubclass(scraper_type, ContainerScraper):
            cls._REGISTRY.add(scraper_type)
        else:
            raise TypeError(f"Not a subclass of {ContainerScraper.__name__}: {scraper_type!r}")
        return scraper_type


class DeckUrlsContainerScraper(ContainerScraper):
    """Abstract scraper of deck-links-containing pages.

    Subclasses that don't define DECK_SCRAPERS use all deck scrapers registered in DeckScraper
    class by default. Defining DECK_URL_PREFIX causes prepending of that prefix to each collected
    deck URL before processing (useful for relative links).
    """
    _REGISTRY: set[Type[Self]] = set()  # override
    DECK_SCRAPERS: tuple[Type[DeckScraper], ...] = ()
    DECK_URL_PREFIX = ""

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_urls = []

    @staticmethod
    @abstractmethod
    @override
    def is_valid_url(url: str) -> bool:
        raise NotImplementedError

    @classmethod
    def _get_deck_scrapers(cls) -> set[Type[DeckScraper]]:
        return set(cls.DECK_SCRAPERS) or DeckScraper.get_registered_scrapers()

    @override
    def _collect(self) -> list[str]:
        links = sorted(set(get_links(self._soup)))
        return [l for l in links if any(ds.is_valid_url(l) for ds in self._get_deck_scrapers())]

    @override
    def _gather(self) -> Collected:
        try:
            self._pre_parse()
            self._parse_metadata()
            deck_urls = self._collect()
            if self.DECK_URL_PREFIX:
                return [prepend_url(l, self.DECK_URL_PREFIX) for l in self._collect()]
            return deck_urls
        except ParsingError as pe:
            err = ScrapingError(str(pe), type(self), self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            return []
        except ScrapingError as e:
            _log.warning(f"Scraping failed with: {e!r}")
            return []

    @classmethod
    def _dispatch_deck_scraper(
            cls, url: str, metadata: Json | None = None) -> DeckScraper | None:
        for scraper_type in cls._get_deck_scrapers():
            if scraper_type.is_valid_url(url):
                return scraper_type(url, metadata)
        return None

    def _process_deck_urls(self) -> list[Deck]:
        decks = []
        for i, deck_url in enumerate(self._deck_urls, start=1):
            if deck_url in (self.url, self.url + "/"):
                _log.warning("Scraping container URL as deck URL detected. Skipping...")
                continue  # avoid scraping self in infinite loop
            scraper = self._dispatch_deck_scraper(deck_url, self._metadata)
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

    @timed("container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    @override
    def scrape(self) -> list[Deck]:
        self._deck_urls = [url.removesuffix("/") for url in self._gather()]
        _log.info(
            f"Gathered {len(self._deck_urls)} deck URL(s) from a {self.CONTAINER_NAME} at:"
            f" {self.url!r}")
        return self._process_deck_urls()


class DeckTagsContainerScraper(ContainerScraper):
    """Abstract scraper of deck-HTML-tags-containing pages.
    """
    _REGISTRY: set[Type[Self]] = set()  # override
    TAG_BASED_DECK_PARSER: Type[TagBasedDeckParser] | None = None

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        if self.TAG_BASED_DECK_PARSER:
            self._metadata["url"] = self.url
            self._metadata["source"] = extract_source(self.url)
        self._deck_tags: list[Tag] = []

    @staticmethod
    @abstractmethod
    @override
    def is_valid_url(url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    @override
    def _collect(self) -> list[Tag]:
        raise NotImplementedError

    def _process_deck_tags(self) -> list[Deck]:
        decks = []
        for i, deck_tag in enumerate(self._deck_tags, start=1):
            try:
                deck = self.TAG_BASED_DECK_PARSER(deck_tag, self._metadata).parse()
            except (AttributeError, ParsingError) as e:
                err = ScrapingError(str(e), type(self), self.url)
                _log.warning(f"Tag-based deck parsing failed with: {err!r}")
                deck = None
            if deck:
                decks.append(deck)
                _log.info(f"Parsed deck {i}/{len(self._deck_tags)}: {deck.name!r}")
            else:
                _log.warning(f"Failed to parse deck {i}/{len(self._deck_tags)}. Skipping...")
                continue

        if decks:
            self._urls_manager.add_scraped(self.url)
        else:
            self._urls_manager.add_failed(self.url)

        return decks

    @timed("container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    @override
    def scrape(self) -> list[Deck]:
        self._deck_tags = self._gather()
        _log.info(
            f"Gathered {len(self._deck_tags)} deck tag(s) from a {self.CONTAINER_NAME} at:"
            f" {self.url!r}")
        return self._process_deck_tags()


class DecksJsonContainerScraper(ContainerScraper):
    """Abstract scraper of deck-JSON-containing pages.
    """
    _REGISTRY: set[Type[Self]] = set()  # override
    JSON_BASED_DECK_PARSER: Type[JsonBasedDeckParser] | None = None

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        if self.JSON_BASED_DECK_PARSER:
            self._metadata["url"] = self.url
            self._metadata["source"] = extract_source(self.url)
        self._decks_data: Json = []

    @staticmethod
    @abstractmethod
    @override
    def is_valid_url(url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    @override
    def _collect(self) -> Json:
        raise NotImplementedError

    def _process_decks_data(self) -> list[Deck]:
        decks = []
        for i, deck_data in enumerate(self._decks_data, start=1):
            try:
                deck = self.JSON_BASED_DECK_PARSER(deck_data, self._metadata).parse()
            except (AttributeError, ParsingError) as e:
                err = ScrapingError(str(e), type(self), self.url)
                _log.warning(f"JSON-based deck parsing failed with: {err!r}")
                deck = None
            if deck:
                decks.append(deck)
                _log.info(f"Parsed deck {i}/{len(self._decks_data)}: {deck.name!r}")
            else:
                _log.warning(f"Failed to parse deck {i}/{len(self._decks_data)}. Skipping...")
                continue

        if decks:
            self._urls_manager.add_scraped(self.url)
        else:
            self._urls_manager.add_failed(self.url)

        return decks

    @timed("container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    @override
    def scrape(self) -> list[Deck]:
        self._decks_data = self._gather()
        _log.info(
            f"Gathered data for {len(self._decks_data)} deck(s) from a {self.CONTAINER_NAME} "
            f"at: {self.url!r}")
        return self._process_decks_data()


class HybridContainerScraper(
    DeckUrlsContainerScraper, DecksJsonContainerScraper, DeckTagsContainerScraper):
    """Abstract scraper of all deck container scenarios:

    * container of deck URLs (links pointing to pages that scrape for a singular deck)
    * container of deck HTML tags
    * container of deck JSON data
    * nested container of container URLs (links pointing to pages that scrape for multiple decks).
    """
    _REGISTRY: set[Type[Self]] = set()  # override
    CONTAINER_SCRAPERS: tuple[Type[ContainerScraper], ...] = ()
    CONTAINER_URL_PREFIX = ""

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._container_urls = []

    @staticmethod
    @abstractmethod
    @override
    def is_valid_url(url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    @override
    def _collect(self) -> Collected:
        raise NotImplementedError

    @override
    def _gather(self) -> Collected:
        try:
            self._pre_parse()
            self._parse_metadata()
            deck_urls, deck_tags, decks_data, container_urls = self._collect()
            if self.DECK_URL_PREFIX:
                deck_urls = [prepend_url(l, self.DECK_URL_PREFIX) for l in deck_urls]
            if self.CONTAINER_URL_PREFIX:
                container_urls = [prepend_url(l, self.CONTAINER_URL_PREFIX) for l in container_urls]
            return deck_urls, deck_tags, decks_data, container_urls
        except ParsingError as pe:
            err = ScrapingError(str(pe), type(self), self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            return [], [], [], []
        except ScrapingError as e:
            _log.warning(f"Scraping failed with: {e!r}")
            return [], [], [], []

    @classmethod
    def _get_container_scrapers(cls) -> set[Type[ContainerScraper]]:
        return set(cls.CONTAINER_SCRAPERS)

    @classmethod
    def _dispatch_container_scraper(
            cls, url: str, metadata: Json | None = None) -> ContainerScraper | None:
        for scraper_type in cls._get_container_scrapers():
            if scraper_type.is_valid_url(url):
                return scraper_type(url, metadata)
        return None

    @classmethod
    def _sift_links(cls, *links: str) -> tuple[list[str], list[str]]:
        deck_urls = [l for l in links if any(ds.is_valid_url(l) for ds in cls._get_deck_scrapers())]
        container_urls = [
            l for l in links if any(
                cs.is_valid_url(l) for cs in cls._get_container_scrapers())]
        return deck_urls, container_urls

    def _get_links_from_tags(
            self, *tags: Tag, css_selector="", url_prefix="",
            query_stripped=True) -> tuple[list[str], list[str]]:
        """Get all links from the provided tags. If no tags are provided, the soup is assumed.

        Note: this assumes the same URL prefix both for deck URLs and container URLs (which ought
        to be most of the time as multi-domain relative URLs on the same page don't make much
        sense).

        Args:
            *tags: BeautifulSoup tags containing links (or the whole soup if not provided)
            css_selector: CSS selector to obtain links from the tag
            url_prefix: prefix to add to relative URLs
            query_stripped: whether to strip the query part of the URL

        Returns:
            links sifted into deck URLs and container URLs
        """
        tags = tags or [self._soup]
        links = get_links(
            *tags, css_selector=css_selector, url_prefix=url_prefix, query_stripped=query_stripped)
        return self._sift_links(*links)

    def _process_container_urls(self) -> list[Deck]:
        decks = []
        for i, url in enumerate(self._container_urls, start=1):
            if self.url in url:
                continue  # avoid scraping self in infinite loop
            if scraper := self._dispatch_container_scraper(url, self._metadata):
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

        for deck in decks:
            deck.update_metadata(outer_container_url=self.url)

        return decks

    @timed("hybrid container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    @override
    def scrape(self) -> list[Deck]:
        self._deck_urls, self._deck_tags, self._decks_data, self._container_urls = self._gather()
        decks = []
        if self._deck_urls:
            _log.info(
                f"Gathered {len(self._deck_urls)} deck URL(s) from a {self.CONTAINER_NAME} at:"
                f" {self.url!r}")
            decks += self._process_deck_urls()
        if self._deck_tags:
            _log.info(
                f"Gathered {len(self._deck_tags)} deck tag(s) from a {self.CONTAINER_NAME} at:"
                f" {self.url!r}")
            decks += self._process_deck_tags()
        if self._decks_data:
            _log.info(
            f"Gathered data for {len(self._decks_data)} deck(s) from a {self.CONTAINER_NAME} "
            f"at: {self.url!r}")
            decks += self._process_decks_data()
        if self._container_urls:
            _log.info(
                f"Gathered {len(self._container_urls)} container URL(s) from a "
                f"{self.CONTAINER_NAME} at: {self.url!r}")
            decks += self._process_container_urls()
        if not decks:
            # outer container URLs are not ever skipped
            # to allow for potential scraping of their content changes
            # mind that this doesn't stop JSON/tag parsing parts of this scraper to potentially
            # flag the same URL (but then treated as regular container URL) as scraped/failed
            _log.info(f"Nothing gathered from a {self.CONTAINER_NAME} at: {self.url!r}")

        return decks
