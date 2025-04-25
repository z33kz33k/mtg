"""

    mtg.deck.scrapers.mtgarenapro.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGArena.Pro decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError, dissect_js

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
    DATA_FROM_SOUP = True  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "mtgarena.pro/decks/" in url.lower() or f"{ALT_DOMAIN}/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return url.replace(ALT_DOMAIN, "mtgarena.pro")

    @override
    def _get_data_from_soup(self) -> Json:
        return dissect_js(
        self._soup, "var precachedDeck=", '"card_ids":', lambda s: s + '"card_ids":[]}')

    @override
    def _validate_data(self) -> None:
        super()._validate_data()
        if not self._data.get("deck_order"):
            raise ScrapingError("Data not available", scraper=type(self))

    def _parse_fmt(self) -> str:
        if self._data["explorer"]:
            return "explorer"
        elif self._data["timeless"]:
            return "timeless"
        elif self._data["alchemy"]:
            return "alchemy"
        elif self._data["brawl"]:
            if self._data["standard"]:
                return "standardbrawl"
            return "brawl"
        elif self._data["historic"]:
            return "historic"
        elif self._data["standard"]:
            return "standard"
        return ""

    @override
    def _parse_metadata(self) -> None:
        self._metadata["author"] = self._data["author"]
        self._metadata["name"] = self._data["humanname"]
        if fmt := self._parse_fmt():
            self._update_fmt(fmt)
        self._metadata["date"] = dateutil.parser.parse(self._data["date"]).date()

    @classmethod
    def _parse_card_json(cls, card_json: Json) -> list[Card]:
        name = card_json["name"]
        quantity = card_json["cardnum"]
        card = cls.find_card(name)
        return cls.get_playset(card, quantity)

    @override
    def _parse_decklist(self) -> None:
        for card_json in self._data["deck_order"]:
            self._maindeck.extend(self._parse_card_json(card_json))
        for card_json in self._data["sidedeck_order"]:
            self._sideboard.extend(self._parse_card_json(card_json))
        for card_json in self._data["commander_order"]:
            self._set_commander(self._parse_card_json(card_json)[0])
