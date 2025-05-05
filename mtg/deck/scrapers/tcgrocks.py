"""

    mtg.deck.scrapers.tcgrocks.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TCGRocks decklists.

    TCGRocks is a sister site of MTGRocks and its decklists are sometimes featured in MTGRocks
    articles.

    @author: z33k

"""
import json
import logging
from typing import override

import dateutil.parser

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser, normalize_decklist
from mtg.deck.scrapers import DeckScraper
from mtg.utils.json import Node
from mtg.utils.scrape import ScrapingError, strip_url_query

_log = logging.getLogger(__name__)


@DeckScraper.registered
class TcgRocksDeckScraper(DeckScraper):
    """Scraper of TCGRocks decklist page.
    """
    DATA_FROM_SOUP = True

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "tcgrocks.com/mtg/deck-builder/embed/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    def _validate_soup(self) -> None:
        super()._validate_soup()
        script_tag = self._soup.select_one("script#__NUXT_DATA__")
        if not script_tag:
            raise ScrapingError(
                "Script tag with JSON data not found", scraper=type(self), url=self.url)

    def _get_data_from_soup(self) -> Json:
        script_tag = self._soup.select_one("script#__NUXT_DATA__")
        return json.loads(script_tag.text.strip())

    def _validate_data(self) -> None:
        super()._validate_data()
        if not isinstance(self._data, list) or "mtg" not in self._data:
            raise ScrapingError("Deck data not available", scraper=type(self), url=self.url)

    @override
    def _parse_metadata(self) -> None:
        if title_tag := self._soup.select_one("h2.text-center"):
            self._metadata["name"] = title_tag.text.strip()

        root = Node(self._data)
        for text in [n.data for n in root.find_all(lambda n: isinstance(n.data, str))]:
            try:
                self._metadata["date"] = dateutil.parser.parse(text).date()
                break
            except dateutil.parser.ParserError:
                pass

        if keywords := self._metadata.get("article", {}).get("tags"):
            if fmt := self.derive_format_from_words(*keywords):
                self._update_fmt(fmt)

    @override
    def _parse_decklist(self) -> None:
        root = Node(self._data)
        mtg_node = root.find(lambda n: n.data == "mtg")
        decklist_node = mtg_node.next_sibling
        if decklist_node is None or not decklist_node.data:
            raise ScrapingError("Decklist not found", scraper=type(self), url=self.url)
        self._decklist = normalize_decklist(decklist_node.data, self.fmt or None)

    @override
    def _build_deck(self) -> Deck | None:
        return ArenaParser(self._decklist, self._metadata).parse()
