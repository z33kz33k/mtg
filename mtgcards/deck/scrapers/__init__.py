"""

    mtgcards.deck.scrapers.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Deck scrapers.

    @author: z33k

"""
from abc import abstractmethod

from mtgcards.const import Json
from mtgcards.deck import DeckParser
from mtgcards.utils.scrape import extract_source


class DeckScraper(DeckParser):
    @property
    def url(self) -> str:
        return self._url

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        self._validate_url(url)
        super().__init__(metadata)
        self._url = self._sanitize_url(url)
        self._metadata["url"] = self.url
        self._metadata["source"] = extract_source(self.url)

    @classmethod
    def _validate_url(cls, url):
        if url and not cls.is_deck_url(url):
            raise ValueError(f"Not a deck URL: {url!r}")

    @abstractmethod
    def _scrape_metadata(self) -> None:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def is_deck_url(url: str) -> bool:
        raise NotImplementedError

    @staticmethod
    def _sanitize_url(url: str) -> str:
        return url  # default implementation does nothing
