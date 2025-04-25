"""

    mtg.deck.scrapers.mtgotraders.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGO Traders decklists.

    @author: z33k

"""
import logging
from datetime import datetime
from typing import override

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import request_json

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MtgoTradersDeckScraper(DeckScraper):
    """Scraper of MTGO Traders deck page.
    """
    API_URL_TEMPLATE = "https://www.mtgotraders.com/deck/data/getdeck.php?deck={}"  # override

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "www.mtgotraders.com/deck/" in url.lower() and "?deck=" in url.lower()

    @override
    def _get_data_from_api(self) -> Json:
        *_, decklist_id = self.url.split("?deck=")
        return request_json(self.API_URL_TEMPLATE.format(decklist_id))

    @override
    def _parse_metadata(self) -> None:
        self._metadata["name"] = self._data["Name"]
        if desc :=self._data.get("Description"):
            self._metadata["description"] = desc
        self._update_fmt(self._data["Format"])
        self._metadata["author"] = self._data["User"]
        self._metadata["date"] = datetime.strptime(
            self._data["Date"], "%Y-%m-%d %H:%M:%S").date()
        self._metadata["views"] = self._data["ViewCount"]
        self._metadata["downloads"] = self._data["DownloadCount"]
        self._metadata["ratings"] = self._data["TotalRatings"]
        self._metadata["avg_rating"] = self._data["RatingAvg"]

    def _parse_json_card(self, json_card: Json) -> list[Card]:
        name = json_card["name"]
        quantity = json_card["qty"]
        return self.get_playset(self.find_card(name), quantity)

    @override
    def _parse_decklist(self) -> None:
        for json_card in self._data["main"]:
            self._maindeck += self._parse_json_card(json_card)
        if sideboard := self._data.get("sideboard"):
            for json_card in sideboard:
                self._sideboard += self._parse_json_card(json_card)
        self._derive_commander_from_sideboard()
