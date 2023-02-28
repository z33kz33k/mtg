"""

    mtgcards.yt.parsers.goldfish.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MtGGoldfish decklist page.

    @author: z33k

"""
from enum import Enum, auto
from typing import Optional, Set

from mtgcards import Card
from mtgcards.scryfall import Deck
from mtgcards.yt.parsers import UrlParser


class _ParsingState(Enum):
    """State machine for parsing.
    """
    IDLE = auto()
    COMMANDER = auto()
    MAINLIST = auto()
    SIDEBOARD = auto()

    @classmethod
    def shift_to_commander(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state is not _ParsingState.IDLE:
            raise RuntimeError(f"Invalid transition to COMMANDER from: {current_state.name}")
        return _ParsingState.COMMANDER

    @classmethod
    def shift_to_mainlist(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state not in (_ParsingState.IDLE, _ParsingState.COMMANDER):
            raise RuntimeError(f"Invalid transition to MAIN_LIST from: {current_state.name}")
        return _ParsingState.MAINLIST

    @classmethod
    def shift_to_sideboard(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state is not _ParsingState.MAINLIST:
            raise RuntimeError(f"Invalid transition to SIDEBOARD from: {current_state.name}")
        return _ParsingState.SIDEBOARD


class GoldfishParser(UrlParser):
    """Parser of MtGGoldfish decklist page.
    """
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/96.0.4664.113 Safari/537.36}",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
                  "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
    }

    def __init__(self, url: str, format_cards: Set[Card]) -> None:
        super().__init__(url, format_cards)
        self._state = _ParsingState.IDLE

    def _parse(self) -> Optional[Deck]:
        table = self._soup.find("table", class_="deck-view-deck-table")
        rows = table.find_all("tr")
        for row in rows:
            pass
