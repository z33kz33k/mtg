"""

    mtgcards.decks.untapped.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Untapped.gg decklist page.

    @author: z33k

"""
from mtgcards.decks import Deck, UrlDeckParser


class UntappedParser(UrlDeckParser):
    """Parser of Untapped.gg decklist page.
    """
    def __init__(self, url: str, fmt="standard", author="", throttled=False) -> None:
        super().__init__(url, fmt, author)

    @staticmethod
    def is_deck_url(url: str) -> bool:
        return "mtga.untapped.gg/profile/" in url and "/deck/" in url

    def _get_deck(self) -> Deck | None:
        pass

    def _parse(self) -> Deck | None:
        pass
