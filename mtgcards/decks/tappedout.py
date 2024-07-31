"""

    mtgcards.decks.tappedout.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse TappedOut decklist page.

    @author: z33k

"""
from mtgcards.const import Json
from mtgcards.decks import Deck, DeckScraper


# html parsing


class TappedoutScraper(DeckScraper):
    """Scraper of TappedOut decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._update_metadata()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "tappedout.net/mtg-decks/" in url

    def _update_metadata(self) -> None:  # override
        self._metadata["source"] = "tappedout.net"

    def _get_deck(self) -> Deck | None:  # override
        pass
