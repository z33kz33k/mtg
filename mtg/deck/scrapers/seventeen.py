"""

    mtg.deck.scrapers.seventeen
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape 17Lands decklists.

    @author: z33k

"""
import logging
from typing import override

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
                        "&deck={}&timestamp={}")  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "17lands.com/user/deck/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(url).removesuffix("/primer").removesuffix("/history")
        return url.rstrip(".,")

    @override
    def _get_data_from_api(self) -> Json:
        _, rest = self.url.split("/user/deck/", maxsplit=1)
        sharing_token, deck_id, timestamp = rest.split("/")
        try:
            return request_json(self.API_URL_TEMPLATE.format(sharing_token, deck_id, timestamp))
        except ReadTimeout:
            raise ScrapingError("API request timed out", scraper=type(self), url=self.url)

    @override
    def _validate_data(self) -> None:
        super()._validate_data()
        if not self._data.get("groups") or not self._data.get("cards"):
            raise ScrapingError("Data not available", scraper=type(self), url=self.url)

    @override
    def _parse_metadata(self) -> None:
        pass

    def _parse_card(self, card_data: Json) -> Card:
        name = card_data["name"]
        scryfall_id, _ = card_data["image_url"].split(".jpg?", maxsplit=1)
        scryfall_id = scryfall_id.removeprefix("https://cards.scryfall.io/large/front/")
        *_, scryfall_id = scryfall_id.split("/")
        return self.find_card(name, scryfall_id=scryfall_id)

    @override
    def _parse_deck(self) -> None:
        maindeck_card_ids = self._data["groups"][0]["cards"]
        try:
            sideboard_card_ids = self._data["groups"][1]["cards"]
        except IndexError:
            sideboard_card_ids = []

        for card_data in self._data["cards"].values():
            card = self._parse_card(card_data)
            self._maindeck += [card] * maindeck_card_ids.count(card_data["id"])
            if sideboard_card_ids:
                self._sideboard += [card] * sideboard_card_ids.count(card_data["id"])
