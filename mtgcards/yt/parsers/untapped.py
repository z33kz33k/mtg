"""

    mtgcards.yt.parsers.untapped.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Untapped.gg decklist page.

    @author: z33k

"""
from enum import Enum, auto
from typing import Optional, Set

from mtgcards.scryfall import Deck, Card
from mtgcards.yt.parsers import UrlParser


class UntappedParser(UrlParser):
    """Parser of Untapped.gg decklist page.
    """
    def _parse(self) -> Optional[Deck]:
        pass
