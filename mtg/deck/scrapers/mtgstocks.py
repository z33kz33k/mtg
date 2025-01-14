"""

    mtg.deck.scrapers.mtgstocks.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGStocks decklists.

    @author: z33k

"""
import json
import logging

import dateutil.parser

from mtg import Json
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.scryfall import Card
from mtg.utils import from_iterable
from mtg.utils.scrape import ScrapingError, getsoup, strip_url_query

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MtgStocksDeckScraper(DeckScraper):
    """Scraper of MTGStocks decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_data: Json | None = None
        self._deck_id = self._parse_deck_id()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgstocks.com/decks/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_query(url)
        return url.replace("/visual/", "/")

    def _parse_deck_id(self) -> int:
        try:
            _, id_part = self.url.split("mtgstocks.com/decks/", maxsplit=1)
            if "/" in id_part:
                id_, _ = id_part.split("/", maxsplit=1)
                return int(id_)
            return int(id_part)
        except ValueError:
            raise ScrapingError(f"Deck ID not available: {self.url!r}")

    def _get_deck_data(self) -> Json:
        script_tag = self._soup.find("script", id="ng-state")
        if not script_tag:
            raise ScrapingError("Data not available")
        data = json.loads(script_tag.text)
        deck_data = from_iterable(
            [v for v in data.values() if isinstance(v, dict)],
            lambda v: v.get("b") and v["b"].get("id") and v["b"]["id"] == self._deck_id)
        if not deck_data:
            raise ScrapingError("Deck data not found")
        return deck_data["b"]

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._deck_data = self._get_deck_data()

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._deck_data["name"]
        if date := self._deck_data.get("lastUpdated"):
            self._metadata["date"] = dateutil.parser.parse(date).date()
        if player := self._deck_data.get("player"):
            self._metadata["author"] = player
        self._update_fmt(self._deck_data["format"]["name"])

    def _parse_playset(self, card: Json) -> list[Card]:
        qty = int(card["quantity"])
        name = card["card"]["name"]
        return self.get_playset(self.find_card(name), qty)

    def _parse_decklist(self) -> None:  # override
        for card in self._deck_data["boards"]["mainboard"]["cards"]:
            self._maindeck.extend(self._parse_playset(card))
        if sideboard := self._deck_data["boards"].get("sideboard"):
            for card in sideboard["cards"]:
                self._sideboard.extend(self._parse_playset(card))


@DeckUrlsContainerScraper.registered
class MtgStocksArticleScraper(DeckUrlsContainerScraper):
    """Scraper of MTGStocks article page.
    """
    CONTAINER_NAME = "MTGStocks article"  # override
    _DECK_SCRAPERS = MtgStocksDeckScraper,  # override
    URL_TEMPLATE = "https://mtgstocks.com{}"

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "mtgstocks.com/news/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning(self._error_msg)
            return []

        deck_tags = self._soup.find_all("news-deck")
        a_tags = [tag.find("a", href=lambda h: h and "/decks/" in h) for tag in deck_tags]
        return [self.URL_TEMPLATE.format(t.attrs["href"]) for t in a_tags if t is not None]
