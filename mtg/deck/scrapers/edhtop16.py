"""

    mtg.deck.scrapers.edhtop16
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape EDHTop16 decklist containers.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckUrlsContainerScraper, UrlHook
from mtg.deck.scrapers.topdeck import check_unexpected_urls
from mtg.utils.scrape import ScrapingError, dissect_js

_log = logging.getLogger(__name__)
URL_HOOKS = (
    # tournament
    UrlHook(
        ('"edhtop16.com/tournament/"', ),
    ),
    # commander
    UrlHook(
        ('"edhtop16.com/commander/"', ),
    ),
)


@DeckUrlsContainerScraper.registered
class EdhTop16TournamentScraper(DeckUrlsContainerScraper):
    """Scraper of EDHTop16 tournament page.
    """
    CONTAINER_NAME = "EDHTop16 tournament"  # override
    DATA_FROM_SOUP = True  # override

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._arena_decklists = []

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "edhtop16.com/tournament/" in url.lower()

    def _process_json(self, json_data: Json) -> Json:
        match json_data:
            case [[_, {"tournament": data}]]:
                return data
            case _:
                raise ScrapingError("No tournament data", scraper=type(self), url=self.url)

    @override
    def _get_data_from_soup(self) -> Json:
        script_tag = self._soup.find("script", type="text/javascript")
        if not script_tag:
            raise ScrapingError(
                "Data <script> tag not found", scraper=type(self), url=self.url)
        json_data = dissect_js(
            script_tag, "window.__river_ops = ", ";\n      ",
            end_processor=lambda s: s.replace('":undefined', '":null').replace(
                '": undefined', '": null'))
        return self._process_json(json_data)

    @override
    def _validate_data(self) -> None:
        super()._validate_data()
        if "entries" not in self._data:
            raise ScrapingError("No tournament entries data", scraper=type(self), url=self.url)

    @override
    def _parse_metadata(self) -> None:
        self._update_fmt("commander")
        self._metadata["event"] = {}
        self._metadata["event"]["name"] = self._data.get("name")
        if size := self._data.get("size"):
            self._metadata["event"]["size"] = size
        if date := self._data.get("tournamentDate"):
            self._metadata["event"]["date"] = dateutil.parser.parse(date).date()

    @staticmethod
    def _normalize_decklist(decklist: str) -> str:
        tokens = decklist.split("1 ")[1:]
        commander, *playsets = [f"1 {t}" for t in tokens if t]
        return "\n".join(["Commander", commander, "", "Deck"] + [*playsets])

    def _process_decklist(self, decklist: str | None, urls: list[str]) -> None:
        if decklist:
            decklist = decklist.strip()
            if decklist.lower().startswith("http"):
                urls.append(decklist)
            else:
                try:
                    self._arena_decklists.append(self._normalize_decklist(decklist))
                except ValueError:
                    pass

    @override
    def _collect(self) -> list[str]:
        deck_urls = []
        for entry in self._data["entries"]:
            self._process_decklist(entry.get("decklist", ""), deck_urls)
        check_unexpected_urls(deck_urls, *self._get_deck_scrapers())
        return deck_urls

    @override
    def scrape(self) -> list[Deck]:
        decks = super().scrape()
        if self._arena_decklists:
            _log.info(
                f"Gathered {len(self._arena_decklists)} text decklists from a {self.CONTAINER_NAME}"
                f" at: {self.url!r}")
            for arena_decklist in self._arena_decklists:
                if deck := ArenaParser(arena_decklist, metadata=self._metadata).parse():
                    decks.append(deck)
        return decks


@DeckUrlsContainerScraper.registered
class EdhTop16CommanderScraper(EdhTop16TournamentScraper):
    """Scraper of EDHTop16 commander page.
    """
    CONTAINER_NAME = "EDHTop16 commander"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "edhtop16.com/commander/" in url.lower()

    @override
    def _process_json(self, json_data: Json) -> Json:
        match json_data:
            case [[_, {"commander": data}]]:
                return data
            case _:
                raise ScrapingError("No commander data", scraper=type(self), url=self.url)

    @override
    def _validate_data(self) -> None:
        if not self._data or "entries" not in self._data or not self._data["entries"].get("edges"):
            raise ScrapingError("No commander entries data", scraper=type(self), url=self.url)

    @override
    def _parse_metadata(self) -> None:
        self._update_fmt("commander")
        self._metadata["commander"] = {}
        self._metadata["commander"]["name"] = self._data["name"]
        self._metadata["commander"]["entries"] = self._data["stats"]["count"]
        self._metadata["commander"]["meta_share"] = self._data["stats"]["metaShare"]
        self._metadata["commander"]["conversion_rate"] = self._data["stats"]["conversionRate"]

    @override
    def _collect(self) -> list[str]:
        deck_urls = []
        for edge in self._data["entries"]["edges"]:
            decklist = edge["node"].get("decklist", "")
            self._process_decklist(decklist, deck_urls)
        check_unexpected_urls(deck_urls, *self._get_deck_scrapers())
        return deck_urls
