"""

    mtgcards.deck.scrapers.melee.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Melee.gg decklists.

    @author: z33k

"""
import logging

import dateutil.parser

from mtgcards import Json
from mtgcards.deck.arena import ArenaParser
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import ScrapingError, getsoup

_log = logging.getLogger(__name__)


_HEADERS = {
    "Host": "melee.gg",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
              "image/png,image/svg+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Cookie": "_ga_0SLSY5ZVGM=GS1.1.1726273364.1.1.1726273386.0.0.0; "
              "_ga=GA1.2.1386763100.1726273364; _gid=GA1.2.1786863949.1726273364; _gat_gtag_UA_"
              "162951615_1=1; FunctionalCookie=false; AnalyticalCookie=false; CookieConsent="
              "true; i18n.langtag=en",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Priority": "u=0, i",
    "TE": "trailers",
}


class MeleeGgScraper(DeckScraper):
    """Scraper of Melee.gg decklist page.
    """
    ALT_DOMAIN = "mtgmelee.com"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(self.url, headers=_HEADERS)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._scrape_metadata()
        self._scrape_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "melee.gg/Decklist/" in url or "mtgmelee.com/Decklist/" in url

    def _scrape_metadata(self) -> None:  # override
        self._metadata["name"] = self._soup.select_one("a.decklist-card-title").text.strip()
        self._metadata["author"] = self._soup.select_one(
            "span.decklist-card-title-author").text.strip().removeprefix("by ")
        if event_tag := self._soup.select_one("div.decklist-card-info-tournament"):
            self._metadata["event"] = event_tag.text.strip()
        info_tags = [tag for tag in self._soup.select("div.decklist-card-info")
                     if not "Deck" in tag.text]
        for tag in info_tags:
            if "/" in tag.text and any(ch.isdigit() for ch in tag.text):
                self._metadata["date"] = dateutil.parser.parse(tag.text.strip())
            else:
                self._update_fmt(tag.text.strip())

    def _scrape_deck(self) -> None:  # override
        lines = self._soup.select_one(
            "textarea.decklist-builder-paste-field").text.strip().splitlines()
        self._deck = ArenaParser(lines, self._metadata).deck
