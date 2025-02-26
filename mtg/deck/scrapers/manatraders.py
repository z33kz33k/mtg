"""

    mtg.deck.scrapers.manatraders.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Manatraders decklists.

    @author: z33k

"""
import json
import logging

from mtg import Json
from mtg.deck.scrapers import DeckUrlsContainerScraper, DeckScraper
from mtg.utils.scrape import ScrapingError, getsoup, strip_url_query

_log = logging.getLogger(__name__)


@DeckScraper.registered
class ManatradersDeckScraper(DeckScraper):
    """Scraper of Manatraders decklist page.
    """
    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        if "manatraders.com/webshop/personal/" in url.lower():
            return True
        if "manatraders.com/webshop/deck/" in url.lower():
            return True
        return False

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _get_deck_data(self) -> Json:
        json_data = self._soup.find(
            "div", {"data-react-class": "WebshopApp"}).attrs["data-react-props"]
        return json.loads(json_data)["deck"]

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._deck_data = self._get_deck_data()

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._deck_data["name"]
        if author := self._deck_data.get("playerName"):
            self._metadata["author"] = author
        self._update_fmt(self._deck_data["format"])
        self._metadata["archetype"] = self._deck_data["archetype"]

    def _parse_card_json(self, card_json: Json) -> None:
        name = card_json["name"]
        card = self.find_card(name)
        if quantity := card_json.get("quantity"):
            self._maindeck += self.get_playset(card, quantity)
        if sideboard_qty := card_json.get("sideboardQuantity"):
            self._sideboard += self.get_playset(card, sideboard_qty)

    def _parse_decklist(self) -> None:  # override
        for card_data in self._deck_data["cards"].values():
            self._parse_card_json(card_data)
        self._derive_commander_from_sideboard()


@DeckUrlsContainerScraper.registered
class ManatradersUserScraper(DeckUrlsContainerScraper):
    """Scraper of Manatraders user search page.
    """
    CONTAINER_NAME = "Manatraders user"  # override
    DECK_URL_TEMPLATE = "https://www.manatraders.com{}"
    DECK_SCRAPERS = ManatradersDeckScraper,  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return all(t in url.lower() for t in ("manatraders.com/decks?", "search_name"))

    def _collect(self) -> list[str]:  # override
        deck_tags = [
            tag for tag in self._soup.find_all("a", href=lambda h: h and "/webshop/deck/" in h)]
        urls = {tag.attrs["href"] for tag in deck_tags}
        return [strip_url_query(self.DECK_URL_TEMPLATE.format(url)) for url in sorted(urls)]
