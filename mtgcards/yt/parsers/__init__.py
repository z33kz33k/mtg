"""

    mtgcards.yt.parsers.py
    ~~~~~~~~~~~~~~~~~~~~~~
    Parse YouTube video's descriptions for decks data.

    @author: z33k

"""
from abc import ABC, abstractmethod
from typing import Optional, Set

from bs4 import BeautifulSoup

from mtgcards.scryfall import Card, Deck
from mtgcards.utils import timed_request


class ParsingError(ValueError):
    """Raised on unexpected states of parsed data.
    """


class UrlParser(ABC):
    """Abstract base parser of URLs pointing to decklists.
    """
    @property
    def url(self) -> str:
        return self._url

    @property
    def deck(self) -> Optional[Deck]:
        return self._deck

    def __init__(self, url: str, format_cards: Set[Card]) -> None:
        self._url, self._format_cards = url, format_cards
        self._deck = None

    def _get_soup(self, **requests_kwargs) -> BeautifulSoup:
        self._markup = timed_request(self._url, **requests_kwargs)
        return BeautifulSoup(self._markup, "lxml")

    @abstractmethod
    def _get_deck(self) -> Optional[Deck]:
        raise NotImplementedError

