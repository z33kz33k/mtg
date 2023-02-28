"""

    mtgcards.yt.parsers.moxfield.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Moxfield decklist page.

    @author: z33k

"""
from enum import Enum, auto
from typing import Optional, Set

from mtgcards.scryfall import Deck, Card
from mtgcards.yt.parsers import UrlParser


class MoxfieldParser(UrlParser):
    """Parser of Moxfield decklist page.
    """
    def _parse(self) -> None:
        pass

