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
from scryfall import Card
from utils import from_iterable
from utils.scrape import ScrapingError

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

    @classmethod
    def _parse_card_json(cls, card_json: Json) -> list[Card]:
        name = card_json["name"]
        quantity = card_json["amount"]
        tcgplayer_id = int(card_json["data"]["price_tcgplayer_id"])
        mtgo_id = int(card_json["data"]["price_cardhoarder_id"])
        card = cls.find_card(name, tcgplayer_id=tcgplayer_id, mtgo_id=mtgo_id)
        return cls.get_playset(card, quantity)

    def _scrape_deck(self) -> None:  # override
        main_data = from_iterable(self._json_data["sections"], lambda d: d["name"] == "Main")
        if not main_data:
            raise ScrapingError("No 'Main' section in the requested page code's JSON data")
        for card_json in main_data["cards"]:
            self._mainboard.extend(self._parse_card_json(card_json))
        if self._json_data["sideboard"]:
            for card_json in self._json_data["sideboard"]:
                self._sideboard.extend(self._parse_card_json(card_json))
        self._build_deck()
