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
from mtgcards.scryfall import Card
from mtgcards.utils.scrape import extract_source


_log = logging.getLogger(__name__)


class DeckScraper(DeckParser):
    @property
    def url(self) -> str:
        return self._url

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        self._validate_url(url)
        super().__init__(metadata)
        self._throttled = False
        self._url = self._sanitize_url(url)
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
    def _sanitize_url(url: str) -> str:
        return url  # default implementation does nothing

    @abstractmethod
    def _scrape_metadata(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _scrape_deck(self) -> None:
        raise NotImplementedError

    def _build_deck(self) -> None:
        try:
            self._deck = Deck(
                self._mainboard, self._sideboard, self._commander, self._companion, self._metadata)
        except InvalidDeck as err:
            _log.warning(f"Scraping failed with: {err}")
            if self._throttled:
                raise
