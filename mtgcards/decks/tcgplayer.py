"""

    mtgcards.decks.tcgplayer.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse TCG Player decklist page.

    @author: z33k

"""
from mtgcards.const import Json
from mtgcards.decks import Deck, DeckScraper


# html parsing

class TcgplayerScraper(DeckScraper):
    """Scraper of TCG Player decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._scrape_metadata()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "decks.tcgplayer.com/" in url

    def _scrape_metadata(self) -> None:  # override
        self._metadata["source"] = "www.tcgplayer.com"

    def _get_deck(self) -> Deck | None:  # override
        pass
