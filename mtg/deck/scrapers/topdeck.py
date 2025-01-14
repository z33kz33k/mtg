"""

    mtg.deck.scrapers.topdeck.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TopDeck.gg decklists.

    @author: z33k

"""
import logging

from selenium.common import TimeoutException

from mtg.deck.scrapers import DeckUrlsContainerScraper
from mtg.deck.scrapers.moxfield import MoxfieldDeckScraper
from mtg.utils.scrape import strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup

_log = logging.getLogger(__name__)


@DeckUrlsContainerScraper.registered
class TopDeckBracketScraper(DeckUrlsContainerScraper):
    """Scraper of TopDeck.gg bracket page.
    """
    CONTAINER_NAME = "TopDeck.gg bracket"  # override
    _DECK_SCRAPERS = MoxfieldDeckScraper,  # override
    _XPATH = "//a[text()='Decklist']"

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "topdeck.gg/bracket/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _collect(self) -> list[str]:  # override
        try:
            self._soup, _, _ = get_dynamic_soup(self.url, self._XPATH)
            if not self._soup:
                _log.warning(self._error_msg)
                return []
        except TimeoutException:
            _log.warning(self._error_msg)
            return []

        deck_tags = self._soup.find_all("a", string="Decklist")
        deck_urls = [t["href"] for t in deck_tags]
        if non_moxfield := [url for url in deck_urls if not MoxfieldDeckScraper.is_deck_url(url)]:
            _log.warning(f"Non-Moxfield deck(s) found: {', '.join(non_moxfield)}")
        return deck_urls


@DeckUrlsContainerScraper.registered
class TopDeckProfileScraper(DeckUrlsContainerScraper):
    """Scraper of TopDeck.gg profile page.
    """
    CONTAINER_NAME = "TopDeck.gg profile"  # override
    _DECK_SCRAPERS = MoxfieldDeckScraper,  # override
    _XPATH = ("//a[contains(@class, 'btn') and contains(@class, 'btn-sm') "
              "and not(contains(@href, 'topdeck.gg'))]")

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "topdeck.gg/profile/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _collect(self) -> list[str]:  # override
        try:
            self._soup, _, _ = get_dynamic_soup(self.url, self._XPATH)
            if not self._soup:
                _log.warning(self._error_msg)
                return []
        except TimeoutException:
            _log.warning(self._error_msg)
            return []

        deck_tags = self._soup.find_all(
            "a", class_=lambda c: c and "btn" in c and "btn-sm" in c,
            href=lambda h: h and "topdeck.gg" not in h)
        deck_urls = [t["href"] for t in deck_tags]
        if non_moxfield := [url for url in deck_urls if not MoxfieldDeckScraper.is_deck_url(url)]:
            _log.warning(f"Non-Moxfield deck(s) found: {', '.join(non_moxfield)}")
        return deck_urls
