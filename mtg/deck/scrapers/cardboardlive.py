"""

    mtg.deck.scrapers.cardboardlive.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape CardBoard Live decklists.

    @author: z33k

"""
import logging
from typing import override

from selenium.common.exceptions import TimeoutException

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper
from mtg.utils.scrape import strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup
from mtg.utils.scrape import ScrapingError

_log = logging.getLogger(__name__)
CLIPBOARD_XPATH = "//span[text()='Export to Arena']"


@DeckScraper.registered
class CardBoardLiveDeckScraper(DeckScraper):
    """Scraper of a CardBoard Live decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._clipboard = ""

    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "app.cardboard.live/shared-deck/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        try:
            self._soup, _, self._clipboard = get_dynamic_soup(
                self.url, CLIPBOARD_XPATH, clipboard_xpath=CLIPBOARD_XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    @override
    def _parse_metadata(self) -> None:
        self._metadata["name"] = self._soup.find("h3", class_="shared-deck__title").text.strip()
        for tag in self._soup.find_all("p", class_="shared-deck__describe"):
            if "Played by: " in tag.text:
                self._metadata["author"] = tag.text.strip().removeprefix("Played by: ")
            elif "Format: " in tag.text:
                self._update_fmt(tag.text.strip().removeprefix("Format: "))
            elif "Tournament: " in tag.text:
                self._metadata["event"] = tag.text.strip().removeprefix("Tournament: ")

    @override
    def _parse_decklist(self) -> None:
        pass

    @override
    def _build_deck(self) -> Deck:
        return ArenaParser(self._clipboard, metadata=self._metadata).parse(
            suppress_parsing_errors=False, suppress_invalid_deck=False)

