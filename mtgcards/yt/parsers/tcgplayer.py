"""

    mtgcards.yt.parsers.tcgplayer.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse TCG Player decklist page.

    @author: z33k

"""
from enum import Enum, auto
from typing import Optional, Set

from mtgcards import Card
from mtgcards.scryfall import Deck
from mtgcards.yt.parsers import UrlParser


class TcgPlayerParser(UrlParser):
    """Parser of TCG Player decklist page.
    """
    def _parse(self) -> Optional[Deck]:
        pass
