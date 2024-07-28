"""

    mtgcards.decks.untapped.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Untapped.gg decklist page.

    @author: z33k

"""
import logging

import selenium.common.exceptions
from bs4 import BeautifulSoup

from mtgcards.const import Json
from mtgcards.decks import Deck, InvalidDeckError, UrlDeckParser, get_playset
from mtgcards.scryfall import Card
from mtgcards.utils.scrape import get_dynamic_soup_by_xpath


_log = logging.getLogger(__name__)


class UntappedParser(UrlDeckParser):
    """Parser of decklist page of Untapped.gg user's profile.
    """
    _XPATH = "//div[@role='tab' and text()='SIDEBOARD']"
    _CONSENT_XPATH = ('//button[contains(@class, "fc-button fc-cta-consent") '
                      'and @aria-label="Consent"]')

    def __init__(self, url: str, metadata: Json | None = None, throttled=False) -> None:
        super().__init__(url, metadata)
        self._throttled = throttled
        try:
            self._soup, self._sideboard_soup = get_dynamic_soup_by_xpath(
                url, self._XPATH, click=True, consent_xpath=self._CONSENT_XPATH)
            self._update_metadata()
            self._deck = self._get_deck()
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

    @staticmethod
    def _parse_soup(soup: BeautifulSoup) -> list[Card]:
        board = []
        tabpanel_tag = soup.find("div", attrs={"role": "tabpanel"})
        li_tags = tabpanel_tag.find_all("li")

        for li_tag in li_tags:
            name_tag = li_tag.select_one(".name")
            name = name_tag.text.strip()
            quantity_tag = li_tag.find("span")
            quantity = int(quantity_tag.text.strip())
            board.extend(get_playset(name, quantity))\

        return board

    def _get_deck(self) -> Deck | None:
        try:
            return Deck(
                self._parse_soup(self._soup),
                self._parse_soup(self._sideboard_soup) if self._sideboard_soup else None,
                metadata=self._metadata)
        except InvalidDeckError:
            if self._throttled:
                raise
            return None

