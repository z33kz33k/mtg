"""

    mtgcards.yt.parsers.mtgazone.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MTG Arena Zone decklist page.

    @author: z33k

"""
from enum import Enum, auto
from typing import Optional, Set

from mtgcards import Card
from mtgcards.scryfall import Deck
from mtgcards.yt.parsers import UrlParser


class MtgaZoneParser(UrlParser):
    """Parser of MTG Arena Zone decklist page.
    """
    def _parse(self) -> Optional[Deck]:
        pass
