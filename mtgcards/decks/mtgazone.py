"""

    mtgcards.decks.mtgazone.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse MTG Arena Zone decklist page.

    @author: z33k

"""
from mtgcards.const import Json
from mtgcards.decks import Deck, UrlDeckParser


class MtgazoneParser(UrlDeckParser):
    """Parser of MTG Arena Zone decklist page.
    """

    def __init__(self, url: str, metadata: Json | None = None, throttled=False) -> None:
        super().__init__(url, metadata)
        self._update_metadata()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgazone.com/user-decks/" in url

    def _update_metadata(self) -> None:  # override
        self._metadata["source"] = "mtgazone.com"

    def _get_deck(self) -> Deck | None:  # override
        pass
