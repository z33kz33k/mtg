"""

    mtg.deck.scrapers.melee.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Melee.gg decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser

from mtg import Json, SECRETS
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.utils.scrape import ScrapingError, getsoup

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


def get_source(src: str) -> str | None:
    if ALT_DOMAIN in src:
        return "melee.gg"
    return None


@DeckScraper.registered
class MeleeGgDeckScraper(DeckScraper):
    """Scraper of Melee.gg decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._arena_decklist = []

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
        self._metadata["name"] = self._soup.select_one("a.decklist-card-title").text.strip()
        if author_tag := self._soup.select_one("span.decklist-card-title-author"):
            self._metadata["author"] = author_tag.text.strip().removeprefix("by ")
        if event_tag := self._soup.select_one("div.decklist-card-info-tournament"):
            self._metadata["event"] = event_tag.text.strip()
        info_tags = [
            tag for tag in self._soup.select("div.decklist-card-info") if not "Deck" in tag.text]
        for tag in info_tags:
            if "/" in tag.text and any(ch.isdigit() for ch in tag.text):
                self._metadata["date"] = dateutil.parser.parse(tag.text.strip()).date()
            else:
                self._update_fmt(tag.text.strip())

    @override
    def _parse_decklist(self) -> None:
        self._arena_decklist = self._soup.select_one(
            "textarea.decklist-builder-paste-field").text.strip().splitlines()

    @override
    def _build_deck(self) -> Deck:
        return ArenaParser(self._arena_decklist, metadata=self._metadata).parse(
            suppress_invalid_deck=False)


@DeckUrlsContainerScraper.registered
class MeleeGgTournamentScraper(DeckUrlsContainerScraper):
    """Scraper of Melee.gg tournament page.
    """
    CONTAINER_NAME = "Melee.gg tournament"  # override
    XPATH = '//a[@data-type="decklist"]'  # override
    DECK_SCRAPERS = MeleeGgDeckScraper,  # override
    DECK_URL_PREFIX = "https://melee.gg"  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "melee.gg/tournament/" in url.lower()

    @override
    def _collect(self) -> list[str]:
        game_tag = self._soup.find("p", id="tournament-headline-game")
        if not game_tag.text.strip() == "Game: Magic: The Gathering":
            _log.warning("Not a MtG tournament")
            return []
        deck_tags = self._soup.find_all("a", href=lambda h: h and "/Decklist/View/" in h)
        return [deck_tag.attrs["href"] for deck_tag in deck_tags]
