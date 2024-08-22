"""

    mtgcards.deck.scrapers.cardsrealm.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Cardsrealm decklists.

    @author: z33k

"""
import json
import logging
from datetime import datetime

from mtgcards.const import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import getsoup
from scryfall import Card
from utils import from_iterable
from utils.scrape import ScrapingError

_log = logging.getLogger(__name__)


class CardsrealmScraper(DeckScraper):
    """Scraper of Cardsrealm decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(self.url)
        self._json_data = self._dissect_js()
        self._scrape_metadata()
        self._scrape_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtg.cardsrealm.com/" in url and "/decks/" in url

    @staticmethod
    def _sanitize_url(url: str) -> str:  # override
        if "?" in url:
            url, rest = url.split("?", maxsplit=1)
        return url

    def _dissect_js(self) -> Json:
        start_hook, end_hook = "var deck_cards = ", 'var torneio_type ='
        text = self._soup.find(
            "script", string=lambda s: s and start_hook in s and end_hook in s).text
        *_, first = text.split(start_hook)
        second, *_ = first.split(end_hook)
        obj, _ = second.rsplit("]", maxsplit=1)
        return json.loads(obj + "]")

    def _scrape_metadata(self) -> None:  # override
        pass

    def _parse_card_json(self, card_json: Json) -> list[Card]:
        pass

    def _scrape_deck(self) -> None:  # override
        pass
        self._build_deck()
