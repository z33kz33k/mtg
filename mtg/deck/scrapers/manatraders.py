"""

    mtg.deck.scrapers.manatraders.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Manatraders decklists.

    @author: z33k

"""
import json
import logging

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.deck.scrapers.streamdecker import StreamdeckerScraper
from mtg.utils.scrape import ScrapingError, getsoup, strip_url_params

_log = logging.getLogger(__name__)


@DeckScraper.registered
class ManatradersScraper(DeckScraper):
    """Scraper of Manatraders decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        if "manatraders.com/webshop/personal/" in url.lower():
            return True
        if "manatraders.com/webshop/deck/" in url.lower():
            return True
        return False

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url)

    def _get_json_data(self) -> Json:
        json_data = self._soup.find(
            "div", {"data-react-class": "WebshopApp"}).attrs["data-react-props"]
        return json.loads(json_data)["deck"]

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._json_data = self._get_json_data()

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._json_data["name"]
        if author := self._json_data.get("playerName"):
            self._metadata["author"] = author
        self._update_fmt(self._json_data["format"])
        self._metadata["archetype"] = self._json_data["archetype"]

    def _parse_card_json(self, card_json: Json) -> None:
        name = card_json["name"]
        card = self.find_card(StreamdeckerScraper.sanitize_card_name(name))
        if quantity := card_json.get("quantity"):
            self._maindeck += self.get_playset(card, quantity)
        if sideboard_qty := card_json.get("sideboardQuantity"):
            self._sideboard += self.get_playset(card, sideboard_qty)

    def _parse_deck(self) -> None:  # override
        for card_data in self._json_data["cards"].values():
            self._parse_card_json(card_data)
        self._derive_commander_from_sideboard()
