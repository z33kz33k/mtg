"""

    mtgcards.deck.scrapers.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Deck scrapers.

    @author: z33k

"""
import logging
from abc import abstractmethod

from mtgcards.const import Json
from mtgcards.deck import Deck, DeckParser, InvalidDeck
from mtgcards.utils.scrape import Throttling, extract_source
from scryfall import all_formats
from utils.scrape import throttle

_log = logging.getLogger(__name__)


SANITIZED_FORMATS = {
    "duelcommander": "duel",
    "duel commander": "duel",
    "historicbrawl": "brawl",
    "artisan historic": "historic",
}


class DeckScraper(DeckParser):
    THROTTLING = Throttling(0.6, 0.15)

    @property
    def url(self) -> str:
        return self._url

    @property
    def throttled(self) -> bool:
        return self._throttled

    def __init__(
            self, url: str, metadata: Json | None = None, throttled=False,
            supress_invalid_deck=True) -> None:
        self._validate_url(url)
        super().__init__(metadata)
        self._throttled = throttled
        self._supress_invalid_deck = supress_invalid_deck
        self._url = self.sanitize_url(url)
        self._metadata["url"] = self.url
        self._metadata["source"] = extract_source(self.url)
        if self.throttled:
            throttle(*self.THROTTLING)

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
        return url

    @abstractmethod
    def _scrape_metadata(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _scrape_deck(self) -> None:
        raise NotImplementedError

    def _update_fmt(self, fmt: str) -> None:
        if fmt != self.fmt:
            fmt = SANITIZED_FORMATS.get(fmt, fmt)
            if fmt in all_formats():
                if self.fmt:
                    _log.warning(
                        f"Earlier specified format: {self.fmt!r} overwritten with a scraped "
                        f"one: {fmt!r}")
                self._metadata["format"] = fmt
            else:
                _log.warning(f"Not a valid format: {fmt!r}")

    def _build_deck(self) -> None:
        try:
            self._deck = Deck(
                self._mainboard, self._sideboard, self._commander, self._partner_commander,
                self._companion, self._metadata)
        except InvalidDeck as err:
            _log.warning(f"Scraping failed with: {err}")
            if not self._supress_invalid_deck:
                raise

