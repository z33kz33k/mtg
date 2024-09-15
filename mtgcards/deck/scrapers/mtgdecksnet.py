"""

    mtgcards.deck.scrapers.mtgdecksnet.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGDecks.net decklists.

    @author: z33k

"""
import logging

import dateutil.parser
from selenium.common.exceptions import TimeoutException

from deck import Deck
from mtgcards import Json
from mtgcards.deck.arena import ArenaParser
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import get_dynamic_soup_by_xpath
from utils.scrape import ScrapingError

_log = logging.getLogger(__name__)


# TODO: scrape the meta
@DeckScraper.registered
class MtgDecksNetScraper(DeckScraper):
    """Scraper of MTGDecks.net decklist page.
    """
    _XPATH = "//textarea[@id='arena_deck']"
    _CONSENT_XPATH = "//p[@class='fc-button-label']"

    _FORMATS = {
        "duel-commander": "duel",
        "brawl": "standardbrawl",
        "historic-brawl": "brawl",
        "old-school": "oldschool",
    }

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._arena_decklist = []

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgdecks.net/" in url and "-decklist-" in url

    def _pre_process(self) -> None:  # override
        try:
            self._soup, _, _ = get_dynamic_soup_by_xpath(
                self.url, self._XPATH, consent_xpath=self._CONSENT_XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _process_metadata(self) -> None:  # override
        info_tag = self._soup.find("div", class_="col-md-6")
        info = info_tag.text.strip()
        name_author_part, *event_parts, date_part = info.split("—")
        name, author = name_author_part.split("Builder:")
        self._metadata["name"] = name.strip().removesuffix(".")
        self._metadata["author"] = author.strip()
        self._metadata["event"] = "—".join(event_parts).strip().replace("\n", " ")
        if date_part:
            self._metadata["date"] = dateutil.parser.parse(date_part.strip()).date()
        fmt_tag = self._soup.select_one("div.breadcrumbs.pull-left")
        _, a_tag, *_ = fmt_tag.find_all("a")
        fmt = a_tag.text.strip().removeprefix("MTG ").lower()
        if found := self._FORMATS.get("fmt"):
            fmt = found
        self._update_fmt(fmt)

    def _build_deck(self) -> Deck:  # override
        return ArenaParser(self._arena_decklist, self._metadata).parse(supress_invalid_deck=False)

    def _process_deck(self) -> None:  # override
        deck_tag = self._soup.find("textarea", id="arena_deck")
        self._arena_decklist = deck_tag.text.strip().splitlines()
