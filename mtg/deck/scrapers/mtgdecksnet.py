"""

    mtg.deck.scrapers.mtgdecksnet.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGDecks.net decklists.

    @author: z33k

"""
import logging

import dateutil.parser
from selenium.common.exceptions import TimeoutException

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import ContainerScraper, DeckScraper
from mtg.utils.scrape import get_dynamic_soup, getsoup, strip_url_params
from mtg.utils.scrape import ScrapingError

_log = logging.getLogger(__name__)


# TODO: scrape the meta
@DeckScraper.registered
class MtgDecksNetScraper(DeckScraper):
    """Scraper of MTGDecks.net decklist page.
    """
    _XPATH = "//textarea[@id='arena_deck']"

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
        return "mtgdecks.net/" in url.lower() and "-decklist-" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url)
        return url.removesuffix("/visual")

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, _ = get_dynamic_soup(self.url, self._XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _parse_metadata(self) -> None:  # override
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
        return ArenaParser(self._arena_decklist, self._metadata).parse(suppress_invalid_deck=False)

    def _parse_deck(self) -> None:  # override
        deck_tag = self._soup.find("textarea", id="arena_deck")
        self._arena_decklist = deck_tag.text.strip().splitlines()


@ContainerScraper.registered
class MtgDecksNetTournamentScraper(ContainerScraper):
    """Scraper of MTGDecks.net tournament page.
    """
    CONTAINER_NAME = "MTGDecks.net tournament"  # override
    DECK_URL_TEMPLATE = "https://mtgdecks.net{}"
    _DECK_SCRAPER = MtgDecksNetScraper  # override
    _XPATH = '//a[contains(@href, "-decklist-")]'

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "mtgdecks.net/" in url.lower() and "-tournament-" in url.lower()

    def _collect(self) -> list[str]:  # override
        try:
            self._soup, _, _ = get_dynamic_soup(self.url, self._XPATH)
            if not self._soup:
                _log.warning("Tournament data not available")
                return []
        except TimeoutException:
            _log.warning("Tournament data not available")
            return []

        deck_tags = [
            tag for tag in self._soup.find_all("a", href=lambda h: h and "-decklist-" in h)]
        return [self.DECK_URL_TEMPLATE.format(deck_tag.attrs["href"]) for deck_tag in deck_tags]
