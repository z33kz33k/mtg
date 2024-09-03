"""

    mtgcards.deck.scrapers.melee.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Melee.gg decklists.

    @author: z33k

"""
import logging

import dateutil.parser

from mtgcards import Json
from mtgcards.deck.arena import ArenaParser
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.deck.scrapers.goldfish import GoldfishScraper
from mtgcards.utils.scrape import getsoup

_log = logging.getLogger(__name__)


class MeleeGgScraper(DeckScraper):
    """Scraper of Melee.gg decklist page.
    """
    ALT_DOMAIN = "mtgmelee.com"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(self.url, headers=GoldfishScraper.HEADERS)
        self._scrape_metadata()
        self._scrape_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "melee.gg/Decklist/" in url or "mtgmelee.com/Decklist/" in url

    def _scrape_metadata(self) -> None:  # override
        self._metadata["name"] = self._soup.select_one("a.decklist-card-title").text.strip()
        self._metadata["author"] = self._soup.select_one(
            "span.decklist-card-title-author").text.strip().removeprefix("by ")
        if event_tag := self._soup.select_one("div.decklist-card-info-tournament"):
            self._metadata["event"] = event_tag.text.strip()
        info_tags = [tag for tag in self._soup.select("div.decklist-card-info")
                     if not "Deck" in tag.text]
        for tag in info_tags:
            if "/" in tag.text and any(ch.isdigit() for ch in tag.text):
                self._metadata["date"] = dateutil.parser.parse(tag.text.strip())
            else:
                self._update_fmt(tag.text.strip())

    def _scrape_deck(self) -> None:  # override
        lines = self._soup.select_one(
            "textarea.decklist-builder-paste-field").text.strip().splitlines()
        self._deck = ArenaParser(lines, self._metadata).deck
