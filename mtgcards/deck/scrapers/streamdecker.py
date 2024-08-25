"""

    mtgcards.deck.scrapers.streamdecker.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Streamdecker decklists.

    @author: z33k

"""
import logging
import re
from datetime import date

from mtgcards.const import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils import get_ago_date
from mtgcards.utils.scrape import timed_request

_log = logging.getLogger(__name__)


class StreamdeckerScraper(DeckScraper):
    """Scraper of Streamdecker deck page.
    """
    API_URL_TEMPLATE = "https://www.streamdecker.com/api/deck/{}"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        *_, self._decklist_id = self.url.split("/")
        self._json_data = timed_request(
            self.API_URL_TEMPLATE.format(self._decklist_id), return_json=True)["data"]
        self._scrape_metadata()
        self._scrape_deck()

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
        self._metadata["author"] = self._json_data["userProfile"]["displayName"]
        self._metadata["author_twitch_id"] = self._json_data["userProfile"]["twitchId"]
        if dt := self._parse_date():
            self._metadata["date"] = dt

    def _parse_json_card(self, json_card: Json) -> None:
        scryfall_id = json_card.get("scryfallId", "")
        name = json_card["name"]
        if "/" in name:
            # sanitize multiface names, e.g. "Wear/Tear" ==> "Wear // Tear"
            name = re.sub(r'(?<=[a-zA-Z])/(?=[a-zA-Z])', r' // ', name)
        card = self.find_card(name, scryfall_id=scryfall_id)
        if json_card["main"]:
            self._mainboard.extend(self.get_playset(card, json_card["main"]))
        if json_card["sideboard"]:
            self._sideboard.extend(self.get_playset(card, json_card["sideboard"]))
        if json_card["commander"]:
            self._set_commander(card)
        if json_card["companion"]:
            self._companion = card

    def _scrape_deck(self) -> None:
        for json_card in self._json_data["cardList"]:
            self._parse_json_card(json_card)
        self._build_deck()
