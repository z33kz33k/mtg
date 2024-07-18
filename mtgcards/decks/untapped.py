"""

    mtgcards.decks.untapped.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Untapped.gg decklist page.

    @author: z33k

"""
from typing import Optional

from mtgcards.scryfall import Deck
from mtgcards.decks import UrlParser


class UntappedParser(UrlParser):
    """Parser of Untapped.gg decklist page.
    """

    def _get_deck(self) -> Deck | None:
        pass

    def _parse(self) -> Deck | None:
        pass
