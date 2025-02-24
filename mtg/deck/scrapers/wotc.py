"""

    mtg.deck.scrapers.wotc.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape the official WotC site's decklists.

    @author: z33k

"""
import logging
import re

import dateutil.parser
from bs4 import Tag

from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckTagsContainerScraper, TagBasedDeckParser
from mtg.scryfall import COMMANDER_FORMATS
from mtg.utils.scrape import ScrapingError, strip_url_query

_log = logging.getLogger(__name__)


class WotCDeckTagParser(TagBasedDeckParser):
    """Parser of WotC decklist HTML tag.
    """
    def _parse_metadata(self) -> None:  # override
        if name := self._deck_tag.attrs.get("deck-title"):
            self._metadata["name"] = name
        if fmt := self._deck_tag.attrs.get("format"):
            if ", " in fmt:
                fmt, *_ = fmt.split(", ")
            self._update_fmt(fmt)

    def _parse_decklist(self) -> None:  # override
        pass

    @staticmethod
    def _sanitize_line(line: str) -> str:
        line = line.strip()
        if line and not line[0].isdigit():
            line = "1 " + line
        # cleans gibberish in square brackets in lines like '1 Arcane Signet[45dhxuab676gfah]'
        return re.sub(r'\[[a-zA-Z0-9]+?\]', '', line).strip()

    def _build_deck(self) -> Deck:  # override
        maindeck_tag = self._deck_tag.find("main-deck")
        if not maindeck_tag:
            raise ScrapingError("No main deck data available")

        lines = [self._sanitize_line(l) for l in maindeck_tag.text.strip().splitlines()]
        if self.fmt and self.fmt in COMMANDER_FORMATS:
            lines.insert(0, "Commander")
            lines.insert(2, "")
            lines.insert(3, "Deck")

        # haven't seen any, so let's assume one
        if sideboard_tag := self._deck_tag.find("sideboard") or self._deck_tag.find(
                "side-board") or self._deck_tag.find("side") or self._deck_tag.find("side-deck"):
            lines += ["", "Sideboard"]
            lines += [self._sanitize_line(l) for l in sideboard_tag.text.splitlines()]

        return ArenaParser(lines, dict(self._metadata)).parse(suppress_invalid_deck=False)


@DeckTagsContainerScraper.registered
class WotCArticleScraper(DeckTagsContainerScraper):
    """Scraper of WotC article page.
    """
    CONTAINER_NAME = "WotC article"
    DECK_PARSER = WotCDeckTagParser

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "magic.wizards.com/" in url.lower() and "/news/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _parse_metadata(self) -> None:  # override
        if time_tag := self._soup.select_one("div > time"):
            self._metadata["date"] = dateutil.parser.parse(time_tag.text.strip()).date()

    def _collect(self) -> list[Tag]:  # override
        deck_tags = [*self._soup.find_all("deck-list")]
        if not deck_tags:
            _log.warning(self._error_msg)
            return []

        self._parse_metadata()

        return deck_tags
