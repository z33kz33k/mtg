"""

    mtgcards.deck.scrapers.deckstats.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Deckstats.net decklists.

    @author: z33k

"""
import json
import logging
from datetime import datetime

from mtgcards.const import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import getsoup

_log = logging.getLogger(__name__)


class DeckstatsScraper(DeckScraper):
    """Scraper of Deckstats.net decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(self.url)
        self._json_data = self._dissect_js()
        self._scrape_metadata()
        self._scrape_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "deckstats.net/decks/" in url

    def _dissect_js(self) -> Json:
        start_hook, end_hook = "init_deck_data(", "deck_display();"
        text = self._soup.find(
            "script", string=lambda s: s and start_hook in s and end_hook in s).text
        *_, first = text.split(start_hook)
        second, *_ = first.split(end_hook)
        obj = second.removesuffix(", false);")
        return json.loads(obj)

    def _scrape_metadata(self) -> None:  # override
        pass

    def _parse_card_json(self, card_json: Json) -> None:
        name = card_json["name"]
        quantity = card_json["amount"]
        # card = self.find_card(name, set_and_collector_number=(set_code, collector_number))
        # playset = self.get_playset(card, quantity)
        # self._mainboard.extend(playset)

    def _scrape_deck(self) -> None:  # override
        pass
        self._build_deck()
