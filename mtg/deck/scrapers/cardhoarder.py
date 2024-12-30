"""

    mtg.deck.scrapers.cardhoarder.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Cardhoarder decklists.

    @author: z33k

"""
import json
import logging

from selenium.common.exceptions import TimeoutException

from mtg import Json
from mtg.deck.scrapers import UrlDeckScraper
from mtg.utils.scrape import ScrapingError, get_dynamic_soup, strip_url_params

_log = logging.getLogger(__name__)


# Cardhoarder has anti-scraping protection (I doubt they care much about user-posted decks
# though), but it seems it's bypassed by Selenium
@UrlDeckScraper.registered
class CardhoarderScraper(UrlDeckScraper):
    """Scraper of Cardhoarder decklist page.
    """
    _XPATH = "//div[@id='deck-viewer']"
    _CONSENT_XPATH = "//div[@id='checkbox']"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.cardhoarder.com/d/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url)

    def _get_deck_data(self) -> Json:
        deck_tag = self._soup.find("div", id="deck-viewer")
        if not deck_tag:
            raise ScrapingError(
                "No deck tag in the requested page code. You're probably being blocked by "
                "Cardhoarder anti-bot measures")
        return json.loads(deck_tag.attrs["data-deck"])

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, _ = get_dynamic_soup(
                self.url, self._XPATH, consent_xpath=self._CONSENT_XPATH)
            self._deck_data = self._get_deck_data()
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._deck_data["name"]

    # TODO: commander handling is only derived, no such input has been seen so far
    def _parse_decklist(self) -> None:  # override
        card_jsons = []
        for _, item in self._deck_data["items"].items():
            card_jsons += item["items"]

        for data in card_jsons:
            name = data["SavedDeckItem"]["name"]
            card = self.find_card(name)
            if quantity_commander := int(data["SavedDeckItem"].get("quantity_commander", 0)):
                for _ in range(quantity_commander):
                    self._set_commander(card)
            else:
                quantity_main = int(data["SavedDeckItem"]["quantity_main"])
                quantity_sideboard = int(data["SavedDeckItem"]["quantity_sideboard"])
                self._maindeck += self.get_playset(card, quantity_main)
                if quantity_sideboard:
                    self._sideboard += self.get_playset(card, quantity_sideboard)
