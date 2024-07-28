"""

    mtgcards.decks.untapped.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Untapped.gg decklist page.

    @author: z33k

"""
import logging

import selenium.common.exceptions

from mtgcards.const import Json
from mtgcards.decks import Deck, InvalidDeckError, UrlDeckParser
from mtgcards.scryfall import Card
from mtgcards.utils.scrape import get_dynamic_soup_by_xpath


_log = logging.getLogger(__name__)


class UntappedParser(UrlDeckParser):
    """Parser of Untapped.gg decklist page.
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

    def _get_sideboard(self) -> list[Card]:
        pass

    def _get_deck(self) -> Deck | None:
        mainboard, sideboard, commander, companion = [], [], None, None

        tabpanel_tag = self._soup.find("div", attrs={"role": "tabpanel"})
        li_tags = tabpanel_tag.find_all("li")

        if self._sideboard_soup:
            sideboard = self._get_sideboard()

        try:
            return Deck(mainboard, sideboard, commander, metadata=self._metadata)
        except InvalidDeckError:
            if self._throttled:
                raise
            return None
