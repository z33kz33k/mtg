"""

    mtg.deck.scrapers.cardhoarder.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Cardhoarder decklists.

    @author: z33k

"""
import json
import logging

import dateutil.parser
from selenium.common.exceptions import TimeoutException

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.utils.scrape import ScrapingError, dissect_js, strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup

_log = logging.getLogger(__name__)


# Cardhoarder has anti-scraping protection (I doubt they care much about user-posted decks
# though), but it seems it's bypassed by Selenium
@DeckScraper.registered
class CardhoarderDeckScraper(DeckScraper):
    """Scraper of Cardhoarder decklist page.
    """
    XPATH = "//div[contains(@id, 'deck-viewer')]"

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "cardhoarder.com/d/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _get_deck_data(self) -> Json:
        start = 'const props = JSON.parse('
        end = ');\n\t\t\twindow.Cardhoarder.helpers.addDeckViewer('
        # in this case, it returns raw JSON string instead of dict...
        deck_data = dissect_js(self._soup, start, end)
        if not deck_data:
            raise ScrapingError("Deck data not available")
        # ...that needs to be reparsed
        return json.loads(deck_data)

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, _ = get_dynamic_soup(self.url, self.XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")
        self._deck_data = self._get_deck_data()

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._deck_data["deck"]["name"]
        self._metadata["date"] = dateutil.parser.parse(self._deck_data["deck"]["updated_at"]).date()

    def _parse_decklist(self) -> None:  # override
        maindeck, sideboard = [], []
        for item in self._deck_data["items"]:
            card_data = item["card"]["card_data"]
            name = card_data["name"]
            set_code = card_data["scryfall_set_code"]
            collector_number = card_data["collector_number"]
            scryfall_id = card_data["scryfall_id"]
            card = self.find_card(name, (set_code, collector_number), scryfall_id)

            quantity_main = int(item["quantity_main"])
            quantity_sideboard = int(item.get("quantity_sideboard", 0))
            maindeck += self.get_playset(card, quantity_main)
            if quantity_sideboard:
                sideboard += self.get_playset(card, quantity_sideboard)

        if len(maindeck) in (1, 2):
            for card in maindeck:
                self._set_commander(card)
            self._maindeck = sideboard
        else:
            self._maindeck = maindeck
            self._sideboard = sideboard
