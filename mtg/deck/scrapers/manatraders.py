"""

    mtg.deck.scrapers.manatraders.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Manatraders decklists.

    @author: z33k

"""
import json
import logging
from typing import override

from mtg import Json
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.utils.scrape import ScrapingError, getsoup, prepend_url, strip_url_query

_log = logging.getLogger(__name__)
URL_PREFIX = "https://www.manatraders.com"


@DeckScraper.registered
class ManatradersDeckScraper(DeckScraper):
    """Scraper of Manatraders decklist page.
    """
    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        if "manatraders.com/webshop/personal/" in url.lower():
            return True
        if "manatraders.com/webshop/deck/" in url.lower():
            return True
        return False

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _get_data_from_soup(self) -> Json:
        data_tag = self._soup.find("div", {"data-react-class": "WebshopApp"})
        if not data_tag:
            data_tag = self._soup.find("div", {"data-react-class": "DeckBuilder"})
            if not data_tag:
                raise ScrapingError("Deck data not available")
        json_data = json.loads(data_tag.attrs["data-react-props"])
        if deck_data := json_data.get("deck"):
            return deck_data
        if deck_data := json_data.get("initialDeck"):
            return deck_data
        raise ScrapingError("Deck data missing in extracted JSON")

    @override
    def _parse_metadata(self) -> None:
        self._metadata["name"] = self._data["name"]
        if author := self._data.get("playerName"):
            self._metadata["author"] = author
        self._update_fmt(self._data["format"])
        self._update_archetype_or_theme(self._data["archetype"])

    def _parse_card_json(self, card_json: Json) -> None:
        name = card_json["name"]
        card = self.find_card(name)
        if quantity := card_json.get("quantity"):
            self._maindeck += self.get_playset(card, quantity)
        if sideboard_qty := card_json.get("sideboardQuantity"):
            self._sideboard += self.get_playset(card, sideboard_qty)

    @override
    def _parse_decklist(self) -> None:
        for card_data in self._data["cards"].values():
            self._parse_card_json(card_data)
        self._derive_commander_from_sideboard()


@DeckUrlsContainerScraper.registered
class ManatradersUserScraper(DeckUrlsContainerScraper):
    """Scraper of Manatraders user search page.
    """
    CONTAINER_NAME = "Manatraders user"  # override
    DECK_SCRAPERS = ManatradersDeckScraper,  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return all(t in url.lower() for t in ("manatraders.com/decks?", "search_name"))

    @override
    def _collect(self) -> list[str]:
        deck_tags = [
            tag for tag in self._soup.find_all("a", href=lambda h: h and "/webshop/deck/" in h)]
        urls = {tag.attrs["href"] for tag in deck_tags}
        return [strip_url_query(prepend_url(url, URL_PREFIX)) for url in sorted(urls)]
