"""

    mtgcards.decks.mtgazone.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MTG Arena Zone decklist page.

    @author: z33k

"""
from mtgcards.decks import Deck, UrlDeckParser


class MtgazoneParser(UrlDeckParser):
    """Parser of MTG Arena Zone decklist page.
    """
    def __init__(self, url: str, fmt="standard", author="", throttled=False) -> None:
        super().__init__(url, fmt, author)

    @staticmethod
    def is_deck_url(url: str) -> bool:
        return "mtgazone.com/user-decks/" in url

    def _get_deck(self) -> Deck | None:
        pass

    def _parse(self) -> Deck | None:
        pass
