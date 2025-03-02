"""

    mtg.deck.scrapers.mtgarenapro.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGArena.Pro decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError, dissect_js, getsoup

_log = logging.getLogger(__name__)
ALT_DOMAIN = "mtga.cc"


def get_source(src: str) -> str | None:
    if ALT_DOMAIN in src:
        return "mtgarena.pro"
    return None


@DeckScraper.registered
class MtgArenaProDeckScraper(DeckScraper):
    """Scraper of MTGArena.Pro decklist page.
    """
    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "mtgarena.pro/decks/" in url.lower() or f"{ALT_DOMAIN}/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return url.replace(ALT_DOMAIN, "mtgarena.pro")

    def _get_deck_data(self) -> Json:
        return dissect_js(
        self._soup, "var precachedDeck=", '"card_ids":', lambda s: s + '"card_ids":[]}')

    @override
    def _pre_parse(self) -> None:
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._deck_data = self._get_deck_data()
        if not self._deck_data or not self._deck_data.get("deck_order"):
            raise ScrapingError("Data not available")

    def _parse_fmt(self) -> str:
        if self._deck_data["explorer"]:
            return "explorer"
        elif self._deck_data["timeless"]:
            return "timeless"
        elif self._deck_data["alchemy"]:
            return "alchemy"
        elif self._deck_data["brawl"]:
            if self._deck_data["standard"]:
                return "standardbrawl"
            return "brawl"
        elif self._deck_data["historic"]:
            return "historic"
        elif self._deck_data["standard"]:
            return "standard"
        return ""

    @override
    def _parse_metadata(self) -> None:
        self._metadata["author"] = self._deck_data["author"]
        self._metadata["name"] = self._deck_data["humanname"]
        if fmt := self._parse_fmt():
            self._update_fmt(fmt)
        self._metadata["date"] = dateutil.parser.parse(self._deck_data["date"]).date()

    @classmethod
    def _parse_card_json(cls, card_json: Json) -> list[Card]:
        name = card_json["name"]
        quantity = card_json["cardnum"]
        card = cls.find_card(name)
        return cls.get_playset(card, quantity)

    @override
    def _parse_decklist(self) -> None:
        for card_json in self._deck_data["deck_order"]:
            self._maindeck.extend(self._parse_card_json(card_json))
        for card_json in self._deck_data["sidedeck_order"]:
            self._sideboard.extend(self._parse_card_json(card_json))
        for card_json in self._deck_data["commander_order"]:
            self._set_commander(self._parse_card_json(card_json)[0])
