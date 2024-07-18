"""

    mtgcards.decks.tcgplayer.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse TCG Player decklist page.

    @author: z33k

"""

from mtgcards.decks import UrlParser
from mtgcards.scryfall import Deck


# html parsing


class TcgPlayerParser(UrlParser):
    """Parser of TCG Player decklist page.
    """

    def _get_deck(self) -> Deck | None:
        pass

    def _parse(self) -> Deck | None:
        pass
