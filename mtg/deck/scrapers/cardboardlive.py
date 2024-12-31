"""

    mtg.deck.scrapers.cardboardlive.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape CardBoard Live decklists.

    @author: z33k

"""
import logging

from selenium.common.exceptions import TimeoutException

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import UrlBasedDeckScraper
from mtg.utils.scrape import get_dynamic_soup, strip_url_params
from mtg.utils.scrape import ScrapingError

_log = logging.getLogger(__name__)
CLIPBOARD_XPATH = "//span[text()='Export to Arena']"


@UrlBasedDeckScraper.registered
class CardBoardLiveDeckScraper(UrlBasedDeckScraper):
    """Scraper of a CardBoard Live decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._clipboard = ""

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "app.cardboard.live/shared-deck/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url, with_endpoint=False)

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, self._clipboard = get_dynamic_soup(
                self.url, CLIPBOARD_XPATH, clipboard_xpath=CLIPBOARD_XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._soup.find("h3", class_="shared-deck__title").text.strip()
        for tag in self._soup.find_all("p", class_="shared-deck__describe"):
            if "Played by: " in tag.text:
                self._metadata["author"] = tag.text.strip().removeprefix("Played by: ")
            elif "Format: " in tag.text:
                self._update_fmt(tag.text.strip().removeprefix("Format: "))
            elif "Tournament: " in tag.text:
                self._metadata["event"] = tag.text.strip().removeprefix("Tournament: ")

    def _build_deck(self) -> Deck:  # override
        return ArenaParser(self._clipboard.splitlines(), metadata=self._metadata).parse(
            suppress_invalid_deck=False)

    def _parse_decklist(self) -> None:  # override
        pass

