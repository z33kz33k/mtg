"""

    mtgcards.decks.untapped.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Untapped.gg decklist page.

    @author: z33k

"""
from mtgcards.const import Json
from mtgcards.decks import Deck, UrlDeckParser
from mtgcards.utils.scrape import get_dynamic_soup_by_xpath


class UntappedParser(UrlDeckParser):
    """Parser of Untapped.gg decklist page.
    """
    _XPATH = "//div[@role='tab' and text()='SIDEBOARD']"
    _CONSENT_XPATH = ('//button[contains(@class, "fc-button fc-cta-consent") '
                      'and @aria-label="Consent"]')

    def __init__(self, url: str, fmt="standard", author="", throttled=False) -> None:
        super().__init__(url, fmt, author)
        self._soup, self._sideboard_soup = get_dynamic_soup_by_xpath(
            url, self._XPATH, click=True, consent_xpath=self._CONSENT_XPATH)
        self._metadata = self._get_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:
        return "mtga.untapped.gg/profile/" in url and "/deck/" in url

    def _get_metadata(self) -> Json:
        metadata = {"source": "mtga.untapped.gg"}
        return metadata

    def _get_deck(self) -> Deck | None:
        pass
