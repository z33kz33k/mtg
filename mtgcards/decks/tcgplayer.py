"""

    mtgcards.decks.tcgplayer.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse TCG Player decklist page.

    @author: z33k

"""

from mtgcards.decks import Deck, DeckParser


# html parsing


class TcgPlayerParser(DeckParser):
    """Parser of TCG Player decklist page.
    """

    def _get_deck(self) -> Deck | None:
        pass

    def _parse(self) -> Deck | None:
        pass
