"""

    mtg.deck.scrapers.mtgdecksnet.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGDecks.net decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser
from selenium.common.exceptions import TimeoutException

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.utils.scrape import ScrapingError
from mtg.utils.scrape import strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup

_log = logging.getLogger(__name__)


# TODO: scrape the meta
@DeckScraper.registered
class MtgDecksNetDeckScraper(DeckScraper):
    """Scraper of MTGDecks.net decklist page.
    """
    XPATH = "//textarea[@id='arena_deck']"
    _FORMATS = {
        "brawl": "standardbrawl",
        "historic-brawl": "brawl",
    }

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._arena_decklist = []

    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "mtgdecks.net/" in url.lower() and "-decklist-" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(url)
        return url.removesuffix("/visual")

    @override
    def _pre_parse(self) -> None:
        try:
            self._soup, _, _ = get_dynamic_soup(self.url, self.XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    @override
    def _parse_metadata(self) -> None:
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

    @override
    def _parse_decklist(self) -> None:
        deck_tag = self._soup.find("textarea", id="arena_deck")
        self._arena_decklist = deck_tag.text.strip().splitlines()

    @override
    def _build_deck(self) -> Deck:  # override
        return ArenaParser(self._arena_decklist, self._metadata).parse(suppress_invalid_deck=False)


@DeckUrlsContainerScraper.registered
class MtgDecksNetTournamentScraper(DeckUrlsContainerScraper):
    """Scraper of MTGDecks.net tournament page.
    """
    CONTAINER_NAME = "MTGDecks.net tournament"  # override
    XPATH = '//a[contains(@href, "-decklist-")]'  # override
    DECK_SCRAPERS = MtgDecksNetDeckScraper,  # override
    DECK_URL_PREFIX = "https://mtgdecks.net"  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "mtgdecks.net/" in url.lower() and "-tournament-" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return url.removesuffix("/").removesuffix("/winrates")

    @override
    def _collect(self) -> list[str]:
        deck_tags = [
            tag for tag in self._soup.find_all("a", href=lambda h: h and "-decklist-" in h)]
        return [deck_tag.attrs["href"] for deck_tag in deck_tags]
