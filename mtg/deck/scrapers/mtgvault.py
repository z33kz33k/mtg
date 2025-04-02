"""

    mtg.deck.scrapers.mtgvault.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGVault decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser
from bs4 import Tag

from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError, strip_url_query
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MtgVaultDeckScraper(DeckScraper):
    """Scraper of MTGVault video decklist page.
    """
    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "mtgvault.com/" in url.lower() and "/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(
            url.removesuffix("/proxy/").removesuffix("/stats/").removesuffix("/sample-hand/"))

    @override
    def _pre_parse(self) -> None:
        self._soup = getsoup(self.url, request_timeout=45)
        if not self._soup:
            raise ScrapingError("Page not available")

    @override
    def _parse_metadata(self) -> None:
        if name_tag := self._soup.select_one("h1.deck-name"):
            self._metadata["name"] = name_tag.text.strip()
        if info_tag := self._soup.select_one("h3.deck-creation-info"):
            text = info_tag.text.strip().removeprefix("by ")
            if " on " in text:
                author, date = text.split(" on ", maxsplit=1)
            else:
                author, date = text, None
            self._metadata["author"] = author
            if date:
                self._metadata["date"] = dateutil.parser.parse(date).date()
        if fmt_tag := self._soup.select_one("span.tag-deck-format"):
            self._update_fmt(fmt_tag.text.strip())

    @classmethod
    def _parse_card(cls, card_tag: Tag) -> list[Card]:
        qty, _ = card_tag.text.strip().split("x", maxsplit=1)
        qty = int(qty)
        name_tag = card_tag.select_one("span > a")
        name = name_tag.attrs["title"]
        return cls.get_playset(cls.find_card(name), qty)

    @override
    def _parse_decklist(self) -> None:
        maindeck_tag = self._soup.select_one("div#main-deck")
        if not maindeck_tag:
            raise ScrapingError("Main deck tag not found")

        for card_tag in maindeck_tag.select("div.deck-card"):
            self._maindeck += self._parse_card(card_tag)

        if sideboard_tag := self._soup.select_one("div#sideboard"):
            for card_tag in sideboard_tag.select("div.deck-card"):
                self._sideboard += self._parse_card(card_tag)

        if commandzone_tag := self._soup.select_one("div#command-zone"):
            for card_tag in commandzone_tag.select("div.deck-card"):
                self._set_commander(self._parse_card(card_tag)[0])
