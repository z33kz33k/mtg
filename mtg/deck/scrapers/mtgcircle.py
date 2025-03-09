"""

    mtg.deck.scrapers.mtgcircle.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGCircle decklists.

    @author: z33k

"""
import json
import logging
from typing import override

import dateutil.parser

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError, dissect_js
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MtgCircleVideoDeckScraper(DeckScraper):
    """Scraper of MTGCircle video decklist page.
    """
    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "mtgcircle.com/videos/" in url.lower()

    def _get_deck_data(self) -> Json:
        try:
            script_tag = self._soup.find("script", string=lambda s: s and "structured-data" in s)
            js_data = dissect_js(
                script_tag, 'self.__next_f.push(', '|||dummy|||', end_processor=lambda t: t[:-1])
            data = json.loads(js_data[1][3:])
            return data[2][3]["children"][3]["children"][2][3]["children"][0][3][
                "deck"]["decklist"]
        except (AttributeError, KeyError):
            raise ScrapingError("Deck data not available")

    @override
    def _pre_parse(self) -> None:
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._deck_data = self._get_deck_data()

    def _parse_fmt(self, arena_fmt: str) -> None:
        if "Standard Brawl" in arena_fmt:
            self._update_fmt("standardbrawl")
        elif "Historic Brawl" in arena_fmt:
            self._update_fmt("brawl")
        elif "Standard" in arena_fmt:
            self._update_fmt("standard")
        elif "Alchemy" in arena_fmt:
            self._update_fmt("alchemy")
        elif "Explorer" in arena_fmt:
            self._update_fmt("explorer")
        elif "Historic" in arena_fmt:
            self._update_fmt("historic")
        elif "Timeless" in arena_fmt:
            self._update_fmt("timeless")

    @override
    def _parse_metadata(self) -> None:
        script_tag = self._soup.find("script", string=lambda s: s and "@context" in s)
        js_data = dissect_js(script_tag, 'self.__next_f.push(', ")")
        data = json.loads(js_data[1])["@graph"]
        self._metadata["date"] = dateutil.parser.parse(data[0]["uploadDate"]).date()
        self._metadata["name"] = data[1]["name"]
        arena_fmt = data[2]["name"]
        self._metadata["arena_format"] = arena_fmt
        self._parse_fmt(arena_fmt)
        self._metadata["author"] = data[3]["name"]

    def _parse_card(self, card_json: Json) -> list[Card]:
        name = card_json["name"]
        oracle_id = card_json["oracle_id"]
        qty = card_json["quantity"]
        return self.get_playset(self.find_card(name, oracle_id=oracle_id), qty)

    @override
    def _parse_decklist(self) -> None:
        for cat in self._deck_data["mainDeck"]["categories"]:
            for card_json in cat["cards"]:
                self._maindeck += self._parse_card(card_json)

        if sideboard := self._deck_data.get("sideboard"):
            for card_json in sideboard["cards"]:
                self._sideboard += self._parse_card(card_json)

        if commander := self._deck_data.get("commander"):
            for card_json in commander["cards"]:
                self._set_commander(self._parse_card(card_json)[0])
