"""

    mtg.deck.scrapers.melee.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Melee.gg decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser

from mtg import SECRETS
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.utils import from_iterable
from mtg.utils.scrape import ScrapingError, get_links, getsoup

_log = logging.getLogger(__name__)


HEADERS = {
    "Host": "melee.gg",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
              "image/png,image/svg+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Cookie": SECRETS["melee_gg"]["cookie"],
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Priority": "u=0, i",
    "TE": "trailers",
}
ALT_DOMAIN = "mtgmelee.com"
URL_PREFIX = "https://melee.gg"


def get_source(src: str) -> str | None:
    if ALT_DOMAIN in src:
        return "melee.gg"
    return None


@DeckScraper.registered
class MeleeGgDeckScraper(DeckScraper):
    """Scraper of Melee.gg decklist page.
    """
    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "melee.gg/decklist/" in url.lower() or f"{ALT_DOMAIN}/decklist/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return url.replace(ALT_DOMAIN, "melee.gg")

    @override
    def _pre_parse(self) -> None:
        self._soup = getsoup(self.url, headers=HEADERS)
        if not self._soup:
            raise ScrapingError("Page not available")

    @override
    def _parse_metadata(self) -> None:
        self._metadata["name"] = self._soup.select_one("div.decklist-title").text.strip()
        if author_tag := self._soup.find(
                "a", class_=lambda c: c and "text-nowrap" in c and "text-muted" in c,
                href=lambda h: h and h.startswith("/Profile/Index/")):
            self._metadata["author"] = author_tag.attrs["href"].removeprefix("/Profile/Index/")
        if event_tag := self._soup.find(
                "a", class_=lambda c: c and "text-nowrap" in c,
                href=lambda h: h and h.startswith("/Tournament/View/")):
            self._metadata["event"] = event_tag.text.strip()
        if date_tag := self._soup.find("span", {"data-toggle": "date"}):
            self._metadata["date"] = dateutil.parser.parse(date_tag.attrs["data-value"]).date()
        info_tag = self._soup.select_one("div.decklist-details-row")
        info_text = info_tag.text.strip()
        sep = "&bullet;"
        parts = [p.strip() for p in info_text.split(sep)]
        if fmt := from_iterable(
                parts, lambda p: p != '-' and all(
                    t not in p for t in ("Magic: ", "Deck: ", "Sideboard: "))):
            self._update_fmt(fmt)

    @override
    def _parse_decklist(self) -> None:
        pass

    @override
    def _build_deck(self) -> Deck:
        decklist_tag = self._soup.select_one("pre#decklist-text")
        if not decklist_tag:
            raise ScrapingError("Decklist tag not found")
        decklist = decklist_tag.text.strip()
        return ArenaParser(decklist, metadata=self._metadata).parse(
            suppress_parsing_errors=False, suppress_invalid_deck=False)


@DeckUrlsContainerScraper.registered
class MeleeGgTournamentScraper(DeckUrlsContainerScraper):
    """Scraper of Melee.gg tournament page.
    """
    CONTAINER_NAME = "Melee.gg tournament"  # override
    XPATH = '//a[@data-type="decklist"]'  # override
    DECK_SCRAPERS = MeleeGgDeckScraper,  # override
    DECK_URL_PREFIX = URL_PREFIX  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "melee.gg/tournament/" in url.lower() or f"{ALT_DOMAIN}/tournament/" in url.lower()

    @override
    def _collect(self) -> list[str]:
        game_tag = self._soup.find("p", id="tournament-headline-game")
        if not game_tag.text.strip() == "Game: Magic: The Gathering":
            _log.warning("Not a MtG tournament")
            return []
        deck_tags = self._soup.find_all("a", href=lambda h: h and "/Decklist/View/" in h)
        return [deck_tag.attrs["href"] for deck_tag in deck_tags]


@DeckUrlsContainerScraper.registered
class MeleeGgProfileScraper(DeckUrlsContainerScraper):
    """Scraper of Melee.gg profile page.
    """
    CONTAINER_NAME = "Melee.gg profile"  # override
    XPATH = '//tr[@role="row"]'  # override
    DECK_SCRAPERS = MeleeGgDeckScraper,  # override
    DECK_URL_PREFIX = URL_PREFIX  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "melee.gg/profile/" in url.lower() or f"{ALT_DOMAIN}/profile/" in url.lower()

    @override
    def _collect(self) -> list[str]:
        links = get_links(self._soup)
        return [l for l in links if l.startswith('/Decklist/View/')]
