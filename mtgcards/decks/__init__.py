"""

    mtgcards.decks.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse decklist URL/text for decks data.

    @author: z33k

"""
from abc import ABC, abstractmethod

from bs4 import BeautifulSoup

from mtgcards.scryfall import Card, Deck, find_by_name, set_cards
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
    def deck(self) -> Deck | None:
        return self._deck

    def __init__(self, url: str, format_cards: set[Card]) -> None:
        self._url, self._format_cards = url, format_cards
        self._deck = None

    def _get_soup(self, **requests_kwargs) -> BeautifulSoup:
        self._markup = timed_request(self._url, **requests_kwargs)
        return BeautifulSoup(self._markup, "lxml")

    @abstractmethod
    def _get_deck(self) -> Deck | None:
        raise NotImplementedError

    def _get_playset(self, name: str, quantity: int, set_code="") -> list[Card]:
        if set_code:
            cards = set_cards(set_code)
            card = find_by_name(name, cards)
            if card:
                return [card] * quantity
        card = find_by_name(name, self._format_cards)
        return [card] * quantity if card else []
