"""

    mtg.deck.scrapers.streamdecker.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Streamdecker decklists.

    @author: z33k

"""
import logging
from datetime import date

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.utils import get_date_from_ago_text
from mtg.utils.scrape import ScrapingError, timed_request

_log = logging.getLogger(__name__)


@DeckScraper.registered
class StreamdeckerScraper(DeckScraper):
    """Scraper of Streamdecker deck page.
    """
    API_URL_TEMPLATE = "https://www.streamdecker.com/api/deck/{}"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        *_, self._decklist_id = self.url.split("/")
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.streamdecker.com/deck/" in url

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = DeckScraper.sanitize_url(url)
        if url.endswith("/"):
            return url.removesuffix("/")
        return url

    def _pre_parse(self) -> None:  # override
        self._json_data = timed_request(
            self.API_URL_TEMPLATE.format(self._decklist_id), return_json=True)["data"]
        if not self._json_data:
            raise ScrapingError("Data not available")

    def _parse_date(self) -> date | None:
        date_text = self._json_data["updatedAt"]
        return get_date_from_ago_text(date_text)

    def _parse_metadata(self) -> None:  # override
        self._metadata.update({
            "name": self._json_data["name"],
            "views": self._json_data["views"]["counter"]
        })
        self._metadata["author"] = self._json_data["userProfile"]["displayName"]
        self._metadata["author_twitch_id"] = self._json_data["userProfile"]["twitchId"]
        if dt := self._parse_date():
            self._metadata["date"] = dt

    def _parse_json_card(self, json_card: Json) -> None:
        scryfall_id = json_card.get("scryfallId", "")
        name = json_card["name"]
        card = self.find_card(self.sanitize_card_name(name), scryfall_id=scryfall_id)
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

    def _parse_deck(self) -> None:
        for json_card in self._json_data["cardList"]:
            self._parse_json_card(json_card)