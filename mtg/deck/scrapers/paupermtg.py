"""

    mtg.deck.scrapers.paupermtg.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape PauperMTG decklists.

    @author: z33k

"""
import logging
from typing import override

from bs4 import Tag

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError, getsoup, strip_url_query

_log = logging.getLogger(__name__)


_STATES = {
    "土地": "land",
    "サイドボード": "sideboard",
    "プレイヤー": "player",
    "大会名": "tournament",
}


@DeckScraper.registered
class PauperMtgDeckScraper(DeckScraper):
    """Scraper of PauperMTG decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._main_tag, self._tags = None, {}
        self._is_edh = "/edhdeck/" in self.url

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "paupermtg.com/deck/" in url.lower() or "paupermtg.com/edhdeck/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available", scraper=type(self))
        self._main_tag = self._soup.find("div", class_="deckDetailList")
        state = "maindeck"
        for tag in self._main_tag:
            if tag.name == "h2":
                state = _STATES.get(tag.text.strip())
            elif tag.name == "ul" and state:
                self._tags[state] = tag

    @override
    def _parse_metadata(self) -> None:
        self._update_fmt("paupercommander") if self._is_edh else self._update_fmt("pauper")
        self._metadata["name"] = self._soup.find(
            "h1", class_=lambda c: c and "deckTitle" in c).text.strip()
        if "player" in self._tags:
            self._metadata["author"] = self._tags["player"].find("p").text.strip()
        if "tournament" in self._tags:
            self._metadata["event"] = self._tags["tournament"].find("p").text.strip()

    @classmethod
    def _parse_container(cls, container: Tag) -> list[Card]:
        cards = []
        li_tags = container.find_all("li")
        for li_tag in li_tags:
            qty, name = li_tag.find("p").text.strip().split(maxsplit=1)
            quantity = int(qty)
            card = cls.find_card(name.strip(), foreign=True)
            cards += cls.get_playset(card, quantity)
        return cards

    @override
    def _parse_decklist(self) -> None:
        if self._is_edh:
            commander, *maindeck = self._parse_container(self._tags["maindeck"])
            self._set_commander(commander)
            self._maindeck += maindeck
        else:
            self._maindeck += self._parse_container(self._tags["maindeck"])
        self._maindeck += self._parse_container(self._tags["land"])
        if "sideboard" in self._tags:
            self._sideboard += self._parse_container(self._tags["sideboard"])
