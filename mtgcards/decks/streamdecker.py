"""

    mtgcards.decks.streamdecker.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Streamdecker decklist page.

    @author: z33k

"""
import logging
from datetime import date

from mtgcards.const import Json
from mtgcards.decks import Deck, InvalidDeck, DeckScraper, find_card_by_name
from mtgcards.scryfall import find_by_id
from mtgcards.utils import get_ago_date
from mtgcards.utils.scrape import timed_request


_log = logging.getLogger(__name__)


# no apparent ways to scrape an Arena list
class StreamdeckerScraper(DeckScraper):
    """Scraper of Streamdecker deck page.
    """
    API_URL_TEMPLATE = "https://www.streamdecker.com/api/deck/{}"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        *_, self._decklist_id = url.split("/")
        self._json_data = timed_request(
            self.API_URL_TEMPLATE.format(self._decklist_id), return_json=True)["data"]
        self._scrape_metadata()
        self._mainboard, self._sideboard, self._commander, self._companion = [], [], None, None
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.streamdecker.com/deck/" in url

    def _parse_date(self) -> date | None:
        date_text = self._json_data["updatedAt"]
        return get_ago_date(date_text)

    def _scrape_metadata(self) -> None:  # override
        self._metadata.update({
            "name": self._json_data["name"],
            "views": self._json_data["views"]["counter"]
        })
        if not self.author:
            self._metadata["author"] = self._json_data["userProfile"]["displayName"]
        self._metadata["author_twitch_id"] = self._json_data["userProfile"]["twitchId"]
        if dt := self._parse_date():
            self._metadata["date"] = dt

    def _parse_card(self, json_card: Json) -> None:
        scryfall_id = json_card["scryfallId"]
        name = json_card["name"]
        card = find_by_id(scryfall_id)
        if not card:
            card = find_card_by_name(name, fmt=self.fmt)
        if json_card["main"]:
            self._mainboard.extend([card] * json_card["main"])
        if json_card["sideboard"]:
            self._sideboard.extend([card] * json_card["sideboard"])
        if json_card["commander"]:
            self._commander.extend([card] * json_card["commander"])
        if json_card["companion"]:
            self._companion.extend([card] * json_card["companion"])

    def _get_deck(self) -> Deck | None:
        for card in self._json_data["cardList"]:
            self._parse_card(card)
        try:
            return Deck(self._mainboard, self._sideboard, self._commander, metadata=self._metadata)
        except InvalidDeck as err:
            _log.warning(f"Scraping failed with: {err}")
            return None

