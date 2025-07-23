"""

    mtg.deck.scrapers.mtgstocks
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGStocks decklists.

    @author: z33k

"""
import json
import logging
from typing import override

import dateutil.parser

from mtg import Json
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.scryfall import Card
from mtg.utils import from_iterable
from mtg.utils.scrape import ScrapingError, get_links, prepend_url, strip_url_query

_log = logging.getLogger(__name__)
URL_PREFIX = "https://mtgstocks.com"


@DeckScraper.registered
class MtgStocksDeckScraper(DeckScraper):
    """Scraper of MTGStocks decklist page.
    """
    DATA_FROM_SOUP = True  # override

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_id = self._parse_deck_id()

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "mtgstocks.com/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
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
            raise ScrapingError(f"Deck ID not available", scraper=type(self), url=self.url)

    def _get_data_from_soup(self) -> Json:
        script_tag = self._soup.find("script", id="ng-state")
        if not script_tag:
            raise ScrapingError("<script> not found", scraper=type(self), url=self.url)
        data = json.loads(script_tag.text)
        deck_data = from_iterable(
            [v for v in data.values() if isinstance(v, dict)],
            lambda v: v.get("b") and v["b"].get("id") and v["b"]["id"] == self._deck_id)
        if not deck_data:
            raise ScrapingError("Deck data not found", scraper=type(self), url=self.url)
        return deck_data["b"]

    @override
    def _parse_metadata(self) -> None:
        self._metadata["name"] = self._data["name"]
        if date := self._data.get("lastUpdated"):
            self._metadata["date"] = dateutil.parser.parse(date).date()
        if player := self._data.get("player"):
            self._metadata["author"] = player
        self._update_fmt(self._data["format"]["name"])

    def _parse_playset(self, card: Json) -> list[Card]:
        qty = int(card["quantity"])
        name = card["card"]["name"]
        return self.get_playset(self.find_card(name), qty)

    @override
    def _parse_deck(self) -> None:
        for card in self._data["boards"]["mainboard"]["cards"]:
            self._maindeck.extend(self._parse_playset(card))
        if sideboard := self._data["boards"].get("sideboard"):
            for card in sideboard["cards"]:
                self._sideboard.extend(self._parse_playset(card))


@DeckUrlsContainerScraper.registered
class MtgStocksArticleScraper(DeckUrlsContainerScraper):
    """Scraper of MTGStocks article page.
    """
    CONTAINER_NAME = "MTGStocks article"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "mtgstocks.com/news/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    def _collect_other_urls(self) -> list[str]:
        article_tag = self._soup.find("article")
        if not article_tag:
            err = ScrapingError("Article tag not found", scraper=type(self), url=self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            return []
        links = get_links(article_tag)
        return [l for l in links if any(ds.is_valid_url(l) for ds in self._get_deck_scrapers())]

    def _collect_own_urls(self) -> list[str]:
        deck_tags = self._soup.find_all("news-deck")
        a_tags = [tag.find("a", href=lambda h: h and "/decks/" in h) for tag in deck_tags]
        return [prepend_url(t.attrs["href"], URL_PREFIX) for t in a_tags if t is not None]

    def _collect(self) -> list[str]:
        return sorted({*self._collect_other_urls(), *self._collect_own_urls()})

