"""

    mtg.deck.scrapers.seventeen.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape 17Lands decklists.

    @author: z33k

"""
import logging

from requests import ReadTimeout

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError, request_json, strip_url_query

_log = logging.getLogger(__name__)


@DeckScraper.registered
class SeventeenLandsDeckScraper(DeckScraper):
    """Scraper of 17Lands decklist page.
    """
    API_URL_TEMPLATE = ("https://www.17lands.com/data/user_deck?sharing_token={}"
                        "&deck={}&timestamp={}")

    def __init__(
            self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        _, rest = self.url.split("/user/deck/", maxsplit=1)
        self._sharing_token, self._deck_id, self._timestamp = rest.split("/")
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "17lands.com/user/deck/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_query(url).removesuffix("/primer").removesuffix("/history")
        return url.rstrip(".,")

    def _pre_parse(self) -> None:  # override
        try:
            self._json_data = request_json(
                self.API_URL_TEMPLATE.format(self._sharing_token, self._deck_id, self._timestamp))
        except ReadTimeout:
            raise ScrapingError("Request timed out")
        if not self._json_data or not self._json_data.get("groups") or not self._json_data.get(
                "cards"):
            raise ScrapingError("Data not available")

    def _parse_metadata(self) -> None:  # override
        pass

    def _parse_card(self, card_data: Json) -> Card:
        name = card_data["name"]
        scryfall_id, _ = card_data["image_url"].split(".jpg?", maxsplit=1)
        scryfall_id = scryfall_id.removeprefix("https://cards.scryfall.io/large/front/")
        *_, scryfall_id = scryfall_id.split("/")
        return self.find_card(name, scryfall_id=scryfall_id)

    def _parse_decklist(self) -> None:  # override
        maindeck_card_ids = self._json_data["groups"][0]["cards"]
        try:
            sideboard_card_ids = self._json_data["groups"][1]["cards"]
        except IndexError:
            sideboard_card_ids = []

        for card_data in self._json_data["cards"].values():
            card = self._parse_card(card_data)
            self._maindeck += [card] * maindeck_card_ids.count(card_data["id"])
            if sideboard_card_ids:
                self._sideboard += [card] * sideboard_card_ids.count(card_data["id"])

