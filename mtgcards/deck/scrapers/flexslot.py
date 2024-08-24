"""

    mtgcards.deck.scrapers.flexslot.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Flexslot.gg decklists.

    @author: z33k

"""
import logging

import dateutil.parser

from mtgcards.const import Json
from mtgcards.deck.arena import ArenaParser
from mtgcards.deck.scrapers import DeckScraper
from utils.scrape import get_dynamic_soup_by_xpath

_log = logging.getLogger(__name__)


class FlexslotScraper(DeckScraper):
    """Scraper of Flexslot.gg decklist page.
    """
    _XPATH = "//h3[@class='text-center']"
    _CONSENT_XPATH = "//p[text()='Consent']"
    _CLIPBOARD_XPATH = "//button[text()='Copy to Clipboard']"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup, _, self._clipboard = get_dynamic_soup_by_xpath(
            self.url, self._XPATH, consent_xpath=self._CONSENT_XPATH,
            clipboard_xpath=self._CLIPBOARD_XPATH)
        self._scrape_metadata()
        self._scrape_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "flexslot.gg/decks/" in url

    def _scrape_metadata(self) -> None:  # override
        if name_tag := self._soup.select_one("div.sideboardtitle.my-2.text-center"):
            self._metadata["name"] = name_tag.text.strip()
        info_text = self._soup.find("h3", class_="text-center").text.strip()
        fmt_part, author_part = info_text.split("|", maxsplit=1)
        self._update_fmt(fmt_part.strip().removeprefix("Format: ").lower())
        self._metadata["author"] = author_part.strip().removeprefix("Author: ")
        if date_tag := self._soup.find("i", string=lambda s: s and "Last Updated" in s):
            self._metadata["date"] = dateutil.parser.parse(
                date_tag.text.strip().removeprefix("Last Updated ")).date()

    def _scrape_deck(self) -> None:  # override
        decklist = [line.rstrip(":") for line in self._clipboard.splitlines()]
        self._deck = ArenaParser(decklist, metadata=self._metadata).deck
