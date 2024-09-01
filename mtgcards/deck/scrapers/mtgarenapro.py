"""

    mtgcards.deck.scrapers.mtgarenapro.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGArena.Pro decklists.

    @author: z33k

"""
import logging

from mtgcards import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import getsoup

_log = logging.getLogger(__name__)


class MtgArenaProScraper(DeckScraper):
    """Scraper of MTGArena.Pro decklist page.
    """

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(self.url)
        self._json_data = self._get_json()
        self._scrape_metadata()
        self._scrape_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgarena.pro/decks/" in url

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = DeckScraper.sanitize_url(url)
        return url

    def _get_json(self) -> Json:
        return self.dissect_js("var precachedDeck=", '"card_ids":', lambda s: s + '"card_ids":[]}')

    def _scrape_metadata(self) -> None:  # override
        pass

    def _scrape_deck(self) -> None:  # override
        pass

        self._build_deck()
