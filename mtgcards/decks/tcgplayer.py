"""

    mtgcards.decks.tcgplayer.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse TCG Player decklist page.

    @author: z33k

"""

from mtgcards.decks import Deck, UrlDeckParser


# html parsing


class TcgplayerParser(UrlDeckParser):
    """Parser of TCG Player decklist page.
    """
    def __init__(self, url: str, fmt="standard", author="") -> None:
        super().__init__(url, fmt, author)

    @staticmethod
    def is_deck_url(url: str) -> bool:
        return "decks.tcgplayer.com/" in url

    def _get_deck(self) -> Deck | None:
        pass

    def _parse(self) -> Deck | None:
        pass
