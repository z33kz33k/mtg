"""

    mtgcards.decks.mtgazone.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MTG Arena Zone decklist page.

    @author: z33k

"""
from typing import Optional

from mtgcards.scryfall import Deck
from mtgcards.decks import UrlParser


class MtgaZoneParser(UrlParser):
    """Parser of MTG Arena Zone decklist page.
    """

    def _get_deck(self) -> Deck | None:
        pass

    def _parse(self) -> Deck | None:
        pass
