"""

    mtg.deck.scrapers.streamdecker
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Streamdecker decklists.

    @author: z33k

"""
import logging
from datetime import date
from typing import override

from requests import ReadTimeout

from mtg import Json
from mtg.deck.scrapers import DeckUrlsContainerScraper, DeckScraper
from mtg.utils import get_date_from_ago_text
from mtg.utils.scrape import ScrapingError, request_json, strip_url_query

_log = logging.getLogger(__name__)


@DeckScraper.registered
class StreamdeckerDeckScraper(DeckScraper):
    """Scraper of Streamdecker deck page.
    """
    API_URL_TEMPLATE = "https://www.streamdecker.com/api/deck/{}"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "www.streamdecker.com/deck/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _get_data_from_api(self) -> Json:
        *_, decklist_id = self.url.split("/")
        try:
            json_data = request_json(self.API_URL_TEMPLATE.format(decklist_id))
        except ReadTimeout:
            raise ScrapingError("API request timed out", scraper=type(self), url=self.url)
        if not json_data or not json_data.get("data") or json_data["data"] == {"deck": {}}:
            raise ScrapingError("Data not available", scraper=type(self), url=self.url)
        return json_data["data"]

    def _parse_date(self) -> date | None:
        date_text = self._data["updatedAt"]
        return get_date_from_ago_text(date_text)

    @override
    def _parse_metadata(self) -> None:
        self._metadata.update({
            "name": self._data["name"],
            "views": self._data["views"]["counter"]
        })
        self._metadata["author"] = self._data["userProfile"]["displayName"]
        self._metadata["author_twitch_id"] = self._data["userProfile"]["twitchId"]
        if dt := self._parse_date():
            self._metadata["date"] = dt

    def _parse_json_card(self, json_card: Json) -> None:
        scryfall_id = json_card.get("scryfallId", "")
        name = json_card["name"]
        card = self.find_card(name, scryfall_id=scryfall_id)
        if json_card["main"]:
            self._maindeck.extend(self.get_playset(card, json_card["main"]))
        if json_card["sideboard"]:
            self._sideboard.extend(self.get_playset(card, json_card["sideboard"]))
        if json_card.get("commander"):
            cards = self.get_playset(card, json_card["commander"])
            for card in cards:
                self._set_commander(card)
        if json_card.get("companion"):
            self._companion = card

    @override
    def _parse_deck(self) -> None:
        for json_card in self._data["cardList"]:
            self._parse_json_card(json_card)


@DeckUrlsContainerScraper.registered
class StreamdeckerUserScraper(DeckUrlsContainerScraper):
    """Scraper of Streamdecker user page.
    """
    CONTAINER_NAME = "Streamdecker user"  # override
    API_URL_TEMPLATE = "https://www.streamdecker.com/api/userdecks/{}"  # override
    DECK_SCRAPERS = StreamdeckerDeckScraper,  # override
    DECK_URL_PREFIX = "https://www.streamdecker.com/deck/"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "streamdecker.com/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _get_data_from_api(self) -> Json:
        *_, user_name = self.url.split("/")
        return request_json(self.API_URL_TEMPLATE.format(user_name))

    @override
    def _validate_data(self) -> None:
        super()._validate_data()
        if not self._data.get("data") or not self._data["data"].get("decks"):
            raise ScrapingError("Data not available", scraper=type(self), url=self.url)

    @override
    def _collect(self) -> list[str]:
        return [d["deckLink"] for d in self._data["data"]["decks"]]
