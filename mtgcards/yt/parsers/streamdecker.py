"""

    mtgcards.yt.parsers.streamdecker.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Streamdecker decklist page.

    @author: z33k

"""
from enum import Enum, auto
from typing import Optional, Set

from mtgcards.scryfall import Deck, Card
from mtgcards.yt.parsers import UrlParser


class StreamdeckerParser(UrlParser):
    """Parser of Streamdecker deck page.
    """
    def _parse(self) -> Optional[Deck]:
        pass
