"""

    mtgcards.deck.scrapers.cardsrealm.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Cardsrealm decklists.

    @author: z33k

"""
import logging

import dateutil.parser

from mtgcards import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import ScrapingError, getsoup
from mtgcards.scryfall import Card

_log = logging.getLogger(__name__)


@DeckScraper.registered
class CardsrealmScraper(DeckScraper):
    """Scraper of Cardsrealm decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtg.cardsrealm.com/" in url and "/decks/" in url

    def _get_json(self) -> Json:
        def process(text: str) -> str:
            obj, _ = text.rsplit("]", maxsplit=1)
            return obj + "]"
        return self.dissect_js("var deck_cards = ", 'var torneio_type =', end_processor=process)

    def _pre_process(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._json_data = self._get_json()

    def _process_metadata(self) -> None:  # override
        card_data = self._json_data[0]
        self._metadata["name"] = card_data["deck_title"]
        self._metadata["date"] = dateutil.parser.parse(card_data["deck_lastchange"]).date()
        self._metadata["author"] = card_data["givenNameUser"]
        self._metadata["views"] = card_data["deck_views"]
        self._update_fmt(card_data["tour_type_name"].lower())

    def _parse_card_json(self, card_json: Json) -> None:
        name = card_json["name_of_card"]
        quantity = card_json["deck_quantity"]
        card = self.find_card(name)
        if card_json["deck_sideboard"]:
            self._sideboard += self.get_playset(card, quantity)
        else:
            self._maindeck += self.get_playset(card, quantity)

    def _process_deck(self) -> None:  # override
        for card_data in self._json_data:
            self._parse_card_json(card_data)
        self._derive_commander_from_sideboard()
