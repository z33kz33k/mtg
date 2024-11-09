"""

    mtg.deck.scrapers.mtgotraders.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGO Traders decklists.

    @author: z33k

"""
import logging
from datetime import datetime

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.utils.scrape import ScrapingError, timed_request
from mtg.scryfall import Card

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MtgoTradersScraper(DeckScraper):
    """Scraper of MTGO Traders deck page.
    """
    REQUEST_URL_TEMPLATE = "https://www.mtgotraders.com/deck/data/getdeck.php?deck={}"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        *_, self._decklist_id = self.url.split("?deck=")
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.mtgotraders.com/deck/" in url.lower() and "?deck=" in url.lower()

    def _pre_parse(self) -> None:  # override
        self._json_data = timed_request(
            self.REQUEST_URL_TEMPLATE.format(self._decklist_id), return_json=True)
        if not self._json_data:
            raise ScrapingError("Data not available")

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._json_data["Name"]
        if desc :=self._json_data.get("Description"):
            self._metadata["description"] = desc
        self._update_fmt(self._json_data["Format"])
        self._metadata["author"] = self._json_data["User"]
        self._metadata["date"] = datetime.strptime(
            self._json_data["Date"], "%Y-%m-%d %H:%M:%S").date()
        self._metadata["views"] = self._json_data["ViewCount"]
        self._metadata["downloads"] = self._json_data["DownloadCount"]
        self._metadata["ratings"] = self._json_data["TotalRatings"]
        self._metadata["avg_rating"] = self._json_data["RatingAvg"]

    def _parse_json_card(self, json_card: Json) -> list[Card]:
        name = json_card["name"]
        quantity = json_card["qty"]
        return self.get_playset(self.find_card(name), quantity)

    def _parse_deck(self) -> None:
        for json_card in self._json_data["main"]:
            self._maindeck += self._parse_json_card(json_card)
        if sideboard := self._json_data.get("sideboard"):
            for json_card in sideboard:
                self._sideboard += self._parse_json_card(json_card)

        if len(self._sideboard) == 1:
            commander = self._sideboard[0]
            if commander.commander_suitable:
                self._set_commander(commander)
                self._sideboard = []
