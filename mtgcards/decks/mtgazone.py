"""

    mtgcards.decks.mtgazone.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MTG Arena Zone decklist page.

    @author: z33k

"""
from mtgcards.decks import Deck, DeckParser


class MtgaZoneParser(DeckParser):
    """Parser of MTG Arena Zone decklist page.
    """

    def _get_deck(self) -> Deck | None:
        pass

    def _parse(self) -> Deck | None:
        pass
