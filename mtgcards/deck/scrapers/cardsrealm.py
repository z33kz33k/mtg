"""

    mtgcards.deck.scrapers.cardsrealm.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Cardsrealm decklists.

    @author: z33k

"""
import json
import logging

import dateutil.parser

from mtgcards.const import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import getsoup
from scryfall import Card

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
        card_data = self._json_data[0]
        self._metadata["name"] = card_data["deck_title"]
        self._metadata["date"] = dateutil.parser.parse(card_data["deck_lastchange"]).date()
        self._metadata["author"] = card_data["givenNameUser"]
        self._metadata["views"] = card_data["deck_views"]
        self._update_fmt(card_data["tour_type_name"].lower())

    def _parse_card_json(self, card_json: Json) -> list[Card]:
        name = card_json["name_of_card"]
        quantity = card_json["deck_quantity"]
        card = self.find_card(name)
        if card_json["deck_sideboard"]:
            self._sideboard += self.get_playset(card, quantity)
        else:
            self._mainboard += self.get_playset(card, quantity)

    def _scrape_deck(self) -> None:  # override
        for card_data in self._json_data:
            self._parse_card_json(card_data)
        self._derive_commander_from_sideboard()
        self._build_deck()
