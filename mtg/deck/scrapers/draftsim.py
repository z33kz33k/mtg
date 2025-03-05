"""

    mtg.deck.scrapers.draftsim.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Draftsim decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser

from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper
from mtg.utils.scrape import ScrapingError, strip_url_query
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)


@DeckScraper.registered
class DraftsimDeckScraper(DeckScraper):
    """Scraper of Draftsim decklist page.
    """
    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "draftsim.com/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")

    @override
    def _parse_metadata(self) -> None:
        if info_tag := self._soup.find("div", class_="deckstats__overview__left"):
            for info_text in info_tag.text.strip().split("\n"):
                info_text = info_text.strip()
                if info_text.startswith("Deck format: "):
                    self._update_fmt(info_text.removeprefix("Deck format: "))
                elif info_text.startswith("Added: "):
                    self._metadata["date"] = dateutil.parser.parse(
                        info_text.removeprefix("Added: ")).date()

    @override
    def _parse_decklist(self) -> None:
        pass

    @override
    def _build_deck(self) -> Deck:
        decklist_tag = self._soup.find("textarea", id="decktext")
        if not decklist_tag:
            raise ScrapingError("Decklist tag not found")
        decklist = decklist_tag.text.strip()
        return ArenaParser(decklist, self._metadata).parse(
            suppress_parsing_errors=False, suppress_invalid_deck=False)
