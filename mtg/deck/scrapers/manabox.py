"""

    mtg.deck.scrapers.manabox.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape ManaBox decklists.

    @author: z33k

"""
import logging

import dateutil.parser
from bs4 import Tag

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)


@DeckScraper.registered
class ManaBoxDeckScraper(DeckScraper):
    """Scraper of ManaBox decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_tag: Tag | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "manabox.app/decks/" in url.lower()

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
        info_tag = self._soup.find("div", class_="w-full").find("div", class_="mb-2")
        name_tag, _, fmt_tag, date_tag, *_ = info_tag.find_all("div")
        self._metadata["name"] = name_tag.text.strip()
        fmt, *_ = fmt_tag.text.strip().split(" - ")
        self._update_fmt(fmt)
        self._metadata["date"] = dateutil.parser.parse(date_tag.text.strip()).date()

    @classmethod
    def _parse_container(cls, container_div: Tag) -> list[Card]:
        cards = []
        for card_tag in container_div.find_all("div", class_=["hidden", "md:block"]):
            qty_tag, name_tag = card_tag.find_all("div", class_=lambda c: c and "text-sm" in c)
            qty, name = int(qty_tag.text.strip()), name_tag.text.strip()
            cards += cls.get_playset(cls.find_card(name), qty)
        return cards

    def _parse_decklist(self) -> None:  # override
        for container_div in self._soup.find_all("div", class_="mb-3"):
            header_tag = container_div.find(
                "div", class_=["flex", "whitespace-nowrap", "overflow-hidden", "text-ellipsis"])
            if "Commander" in header_tag.text:
                for card in self._parse_container(container_div):
                    self._set_commander(card)
            elif "Sideboard" in header_tag.text:
                self._sideboard += self._parse_container(container_div)
            else:
                self._maindeck += self._parse_container(container_div)
