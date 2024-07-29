"""

    mtgcards.decks.untapped.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Untapped.gg decklist page.

    @author: z33k

"""
import logging

import selenium.common.exceptions

from mtgcards.const import Json
from mtgcards.decks import Deck, DeckScraper
from mtgcards.decks.arena import ArenaParser
from mtgcards.utils.scrape import get_dynamic_soup_by_xpath

_log = logging.getLogger(__name__)
CONSENT_XPATH = '//button[contains(@class, "fc-button fc-cta-consent") and @aria-label="Consent"]'
CLIPBOARD_XPATH = "//span[text()='Copy to MTGA']"


class UntappedProfileDeckScraper(DeckScraper):
    """Scraper of decklist page of Untapped.gg user's profile.
    """
    _XPATH = "//div[@role='tab' and text()='SIDEBOARD']"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        try:
            self._soup, _, self._clipboard = get_dynamic_soup_by_xpath(
                self._url, self._XPATH, consent_xpath=CONSENT_XPATH,
                clipboard_xpath=CLIPBOARD_XPATH)
            self._update_metadata()
            self._deck = self._get_deck()
            pass
        except selenium.common.exceptions.TimeoutException:
            _log.warning(f"Scraping failed due to a Selenium timing out")

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtga.untapped.gg/profile/" in url and "/deck/" in url

    def _update_metadata(self) -> None:  # override
        self._metadata["source"] = "mtga.untapped.gg"
        name_tag = self._soup.select_one('span[class*="DeckListContainer__Title"]')
        strong_tag = name_tag.find("strong")
        self._metadata["name"] = strong_tag.text.strip()
        if not self.author:
            author_tag = self._soup.select_one(
                'div[class*="ProfileHeader__DisplayName-sc-mu9foi-4 hrSMYV"]')
            span_tag = author_tag.find("span")
            self._metadata["author"] = span_tag.text.strip().removesuffix("'s Profile")

    def _get_deck(self) -> Deck | None:  # override
        return ArenaParser(self._clipboard.splitlines(), metadata=self._metadata).deck


class UntappedRegularDeckScraper(DeckScraper):
    """Scraper of decklist page of Untapped.gg user's profile.
    """
    _XPATH = "//h1[contains(@class, 'styles__H1')]"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(self._normalize_url(url), metadata)
        try:
            self._soup, _, self._clipboard = get_dynamic_soup_by_xpath(
                self._url, self._XPATH, consent_xpath=CONSENT_XPATH,
                clipboard_xpath=CLIPBOARD_XPATH)
            self._update_metadata()
            self._deck = self._get_deck()
            pass
        except selenium.common.exceptions.TimeoutException:
            _log.warning(f"Scraping failed due to a Selenium timing out")

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtga.untapped.gg/decks/" in url

    @staticmethod
    def _normalize_url(url: str) -> str:
        return url.replace("input/", "") if "/input/" in url else url

    def _update_metadata(self) -> None:  # override
        self._metadata["source"] = "mtga.untapped.gg"
        name_tag = self._soup.select("h1[class*='styles__H1']")[-1]
        name = name_tag.text.strip()
        if " (" in name:
            name, *_ = name.split(" (")
        self._metadata["name"] = name

    def _get_deck(self) -> Deck | None:  # override
        return ArenaParser(self._clipboard.splitlines(), metadata=self._metadata).deck

