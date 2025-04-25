"""

    mtg.deck.scrapers.searchit.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGSearch.it decklists.

    @author: z33k

"""
import logging
from typing import override

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper
from mtg.utils.scrape import ScrapingError, strip_url_query

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MtgSearchItDeckScraper(DeckScraper):
    """Scraper of a MTGSearch.it decklist page.
    """
    SELENIUM_PARAMS = {  # override
        "xpath": "//div[contains(@class, 'tags') and contains(@class, 'mt10')]"
    }
    # TODO: detect presence of this trolling and attempt to click with Selenium
    # XPATH_UNBLOCK = "//a[@href='/access/unblock']"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._arena_decklist = ""

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "mtgsearch.it/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _parse_metadata(self) -> None:
        tags = self._soup.select_one("div.tags.mt10").text.strip()
        try:
            fmt, arch = tags.splitlines()
            self._update_archetype_or_theme(arch)
            self._update_fmt(fmt)
        except ValueError:
            pass
        a_tag = self._soup.select_one("a.icon")
        img_tag = a_tag.find("img")
        self._metadata["author"] = img_tag.attrs["alt"].removesuffix(" | Icon")

    @override
    def _parse_decklist(self) -> None:
        tokens = "container text hide".split()
        decklist_tag = self._soup.find(
            "section", class_=lambda c: c and all(t in c for t in tokens))
        if not decklist_tag:
            raise ScrapingError("Decklist tag not found", scraper=type(self), url=self.url)
        self._arena_decklist = decklist_tag.text.strip()

    @override
    def _build_deck(self) -> Deck:
        return ArenaParser(self._arena_decklist, metadata=self._metadata).parse(
            suppress_parsing_errors=False, suppress_invalid_deck=False)
