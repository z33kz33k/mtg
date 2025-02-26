"""

    mtg.deck.scrapers.searchit.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGSearch.it decklists.

    @author: z33k

"""
import logging

from selenium.common import TimeoutException

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper
from mtg.utils.scrape import ScrapingError, strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup

_log = logging.getLogger(__name__)



@DeckScraper.registered
class MtgSearchItDeckScraper(DeckScraper):
    """Scraper of a MTGSearch.it decklist page.
    """
    XPATH = "//div[contains(@class, 'tags') and contains(@class, 'mt10')]"
    # TODO: detect presence of this trolling and attempt to click with Selenium
    XPATH_UNBLOCK = "//a[@href='/access/unblock']"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._arena_decklist = ""

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgsearch.it/decks/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, _ = get_dynamic_soup(self.url, self.XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _parse_metadata(self) -> None:  # override
        tags = self._soup.select_one("div.tags.mt10").text.strip()
        try:
            fmt, arch = tags.splitlines()
            self._update_archetype(arch)
            self._update_custom_theme("searchit", arch.lower())
            self._update_fmt(fmt)
        except ValueError:
            pass
        a_tag = self._soup.select_one("a.icon")
        img_tag = a_tag.find("img")
        self._metadata["author"] = img_tag.attrs["alt"].removesuffix(" | Icon")

    def _parse_decklist(self) -> None:  # override
        tokens = "container text hide".split()
        decklist_tag = self._soup.find(
            "section", class_=lambda c: c and all(t in c for t in tokens))
        self._arena_decklist = decklist_tag.text.strip()

    def _build_deck(self) -> Deck:  # override
        return ArenaParser(self._arena_decklist.splitlines(), metadata=self._metadata).parse(
            suppress_invalid_deck=False)
