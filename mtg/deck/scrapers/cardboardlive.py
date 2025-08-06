"""

    mtg.deck.scrapers.cardboardlive
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape CardBoard Live decklists.

    @author: z33k

"""
import logging
from typing import override

from mtg.deck.scrapers import DeckScraper, UrlHook
from mtg.utils.scrape import strip_url_query

_log = logging.getLogger(__name__)
CLIPBOARD_XPATH = "//span[text()='Export to Arena']"


URL_HOOKS = (
    # regular deck
    UrlHook(
        ('"app.cardboard.live/shared-deck/"', ),
    ),
)


@DeckScraper.registered
class CardBoardLiveDeckScraper(DeckScraper):
    """Scraper of a CardBoard Live decklist page.
    """
    SELENIUM_PARAMS = {  # override
        "xpath": CLIPBOARD_XPATH,
        "clipboard_xpath": CLIPBOARD_XPATH
    }

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "app.cardboard.live/shared-deck/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

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
    def _parse_deck(self) -> None:
        self._decklist = self._clipboard
