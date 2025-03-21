"""

    mtg.deck.scrapers.streamdecker.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
    API_URL_TEMPLATE = "https://www.streamdecker.com/api/deck/{}"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        *_, self._decklist_id = self.url.split("/")

    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "www.streamdecker.com/deck/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        try:
            json_data = request_json(self.API_URL_TEMPLATE.format(self._decklist_id))
        except ReadTimeout:
            raise ScrapingError("Request timed out")
        if not json_data or not json_data.get("data") or json_data["data"] == {"deck": {}}:
            raise ScrapingError("Data not available")
        self._deck_data = json_data["data"]

    def _parse_date(self) -> date | None:
        date_text = self._deck_data["updatedAt"]
        return get_date_from_ago_text(date_text)

    @override
    def _parse_metadata(self) -> None:
        self._metadata.update({
            "name": self._deck_data["name"],
            "views": self._deck_data["views"]["counter"]
        })
        self._metadata["author"] = self._deck_data["userProfile"]["displayName"]
        self._metadata["author_twitch_id"] = self._deck_data["userProfile"]["twitchId"]
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
    def _parse_decklist(self) -> None:
        for json_card in self._deck_data["cardList"]:
            self._parse_json_card(json_card)


@DeckUrlsContainerScraper.registered
class StreamdeckerUserScraper(DeckUrlsContainerScraper):
    """Scraper of Streamdecker user page.
    """
    CONTAINER_NAME = "Streamdecker user"  # override
    API_URL_TEMPLATE = "https://www.streamdecker.com/api/userdecks/{}"
    DECK_SCRAPERS = StreamdeckerDeckScraper,  # override
    DECK_URL_PREFIX = "https://www.streamdecker.com/deck/"  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "streamdecker.com/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    def _get_user_name(self) -> str:
        *_, last = self.url.split("/")
        return last

    @override
    def _collect(self) -> list[str]:
        json_data = request_json(self.API_URL_TEMPLATE.format(self._get_user_name()))
        if not json_data or not json_data.get("data") or not json_data["data"].get("decks"):
            _log.warning(self._error_msg)
            return []
        return [d["deckLink"] for d in json_data["data"]["decks"]]
