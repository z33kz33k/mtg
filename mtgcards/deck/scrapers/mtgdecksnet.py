"""

    mtgcards.deck.scrapers.mtgdecksnet.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGDecks.net decklists.

    @author: z33k

"""
import logging

import dateutil.parser
from selenium.common.exceptions import TimeoutException

from mtgcards import Json
from mtgcards.deck.arena import ArenaParser
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import get_dynamic_soup_by_xpath

_log = logging.getLogger(__name__)


# TODO: scrape the meta
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
        try:
            self._soup, _, _ = get_dynamic_soup_by_xpath(
                self.url, self._XPATH, consent_xpath=self._CONSENT_XPATH)
            self._scrape_metadata()
            self._scrape_deck()
        except TimeoutException:
            _log.warning(f"Scraping failed due to Selenium timing out")

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgdecks.net/" in url and "-decklist-" in url

    def _scrape_metadata(self) -> None:  # override
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

    # MTGDecks.net puts a commander into sideboard and among other cards to boot - making it
    # essentially unscrapable
    def _scrape_deck(self) -> None:  # override
        deck_tag = self._soup.find("textarea", id="arena_deck")
        self._deck = ArenaParser(
            deck_tag.text.strip().splitlines(), self._metadata).deck
