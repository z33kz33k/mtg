"""

    mtg.deck.scrapers.flexslot.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Flexslot.gg decklists.

    @author: z33k

"""
import logging

import dateutil.parser
from selenium.common.exceptions import TimeoutException

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckUrlsContainerScraper, DeckScraper
from mtg.utils.scrape import strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup
from mtg.utils.scrape import ScrapingError

_log = logging.getLogger(__name__)
CONSENT_XPATH = "//p[text()='Consent']"


@DeckScraper.registered
class FlexslotDeckScraper(DeckScraper):
    """Scraper of Flexslot.gg decklist page.
    """
    _XPATH = "//h3[@class='text-center']"
    _CLIPBOARD_XPATH = "//button[contains(text(), 'Copy to Clipboard')]"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._clipboard, self._arena_decklist = "", []

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "flexslot.gg/decks/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url).removesuffix("/view")

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, self._clipboard = get_dynamic_soup(
                self.url, self._XPATH, consent_xpath=CONSENT_XPATH,
                clipboard_xpath=self._CLIPBOARD_XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _parse_metadata(self) -> None:  # override
        if name_tag := self._soup.select_one("div.sideboardtitle.my-2.text-center"):
            self._metadata["name"] = name_tag.text.strip()
        elif name_tag := self._soup.find("title"):
            self._metadata["name"] = name_tag.text.strip().removeprefix("Flexslot - ")
        info_text = self._soup.find("h3", class_="text-center").text.strip()
        fmt_part, author_part = info_text.split("|", maxsplit=1)
        self.update_fmt(fmt_part.strip().removeprefix("Format: ").lower())
        self._metadata["author"] = author_part.strip().removeprefix("Author: ")
        if date_tag := self._soup.find("i", string=lambda s: s and "Last Updated" in s):
            self._metadata["date"] = dateutil.parser.parse(
                date_tag.text.strip().removeprefix("Last Updated ")).date()

    def _build_deck(self) -> Deck:  # override
        return ArenaParser(self._arena_decklist, metadata=self._metadata).parse(
            suppress_invalid_deck=False)

    def _parse_decklist(self) -> None:  # override
        self._arena_decklist = [line.rstrip(":") for line in self._clipboard.splitlines()]


@DeckUrlsContainerScraper.registered
class FlexslotUserScraper(DeckUrlsContainerScraper):
    """Scraper of Flexslot user page.
    """
    CONTAINER_NAME = "Flexslot user"  # override
    URL_TEMPLATE = "https://flexslot.gg{}"
    _DECK_SCRAPERS = FlexslotDeckScraper,  # override
    _XPATH = '//a[contains(@href, "/decks/")]'

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "flexslot.gg/u/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _collect(self) -> list[str]:  # override
        try:
            self._soup, _, _ = get_dynamic_soup(self.url, self._XPATH, consent_xpath=CONSENT_XPATH)
            if not self._soup:
                _log.warning(self._error_msg)
                return []
        except TimeoutException:
            _log.warning(self._error_msg)
            return []

        deck_tags = self._soup.find_all("a", href=lambda h: h and "/decks/" in h)
        return [self.URL_TEMPLATE.format(tag["href"]) for tag in deck_tags]
