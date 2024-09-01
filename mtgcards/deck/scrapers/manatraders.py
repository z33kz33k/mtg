"""

    mtgcards.deck.scrapers.manatraders.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Manatraders decklists.

    @author: z33k

"""
import json
import logging

from mtgcards import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.deck.scrapers.streamdecker import StreamdeckerScraper
from mtgcards.utils.scrape import getsoup

_log = logging.getLogger(__name__)


class ManatradersScraper(DeckScraper):
    """Scraper of Manatraders decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(self.url)
        self._json_data = self._get_json_data()
        self._scrape_metadata()
        self._scrape_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        if "www.manatraders.com/webshop/personal/" in url:
            return True
        if "www.manatraders.com/webshop/deck/" in url:
            return True
        return False

    def _get_json_data(self) -> Json:
        json_data = self._soup.find(
            "div", {"data-react-class": "WebshopApp"}).attrs["data-react-props"]
        return json.loads(json_data)["deck"]

    def _scrape_metadata(self) -> None:  # override
        self._metadata["name"] = self._json_data["name"]
        if author := self._json_data.get("playerName"):
            self._metadata["author"] = author
        self._update_fmt(self._json_data["format"])
        self._metadata["archetype"] = self._json_data["archetype"]

    def _parse_card_json(self, card_json: Json) -> None:
        name = card_json["name"]
        card = self.find_card(StreamdeckerScraper.sanitize_card_name(name))
        if quantity := card_json.get("quantity"):
            self._mainboard += self.get_playset(card, quantity)
        if sideboard_qty := card_json.get("sideboardQuantity"):
            self._sideboard += self.get_playset(card, sideboard_qty)

    def _scrape_deck(self) -> None:  # override
        for card_data in self._json_data["cards"].values():
            self._parse_card_json(card_data)
        self._derive_commander_from_sideboard()
        self._build_deck()
