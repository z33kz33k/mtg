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
from mtg.utils import from_iterable
from mtg.utils.scrape import ScrapingError, dissect_js
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MtgCircleVideoDeckScraper(DeckScraper):
    """Scraper of MTGCircle video decklist page.
    """
    _METADATA_IDX = 1

    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "mtgcircle.com/videos/" in url.lower()

    @staticmethod
    def _retrieve_deck_data(data) -> Json:
        return data[2][3]["children"][3]["children"][2][3]["children"][0][3]["deck"]

    def _get_deck_data(self) -> Json:
        try:
            script_tag = self._soup.find(
                "script", string=lambda s: s and "structured-data" in s and "@context" not in s)
            js_data = dissect_js(
                script_tag, 'self.__next_f.push(', '|||dummy|||', end_processor=lambda t: t[:-1])
            data = json.loads(js_data[1][3:])
            return self._retrieve_deck_data(data)
        except (AttributeError, KeyError):
            raise ScrapingError("Deck data not available")

    @override
    def _pre_parse(self) -> None:
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._deck_data = self._get_deck_data()

    def _get_arena_rank(self) -> str | None:
        a_tags = self._soup.select("ul > a")
        if a_tag := from_iterable(a_tags, lambda a: "?rank=" in a.attrs["href"]):
            *_, rank = a_tag.attrs["href"].split("?rank=")
            return rank
        return None

    def _parse_metadata_script_tag(self) -> None:
        script_tag = self._soup.find(
            "script", string=lambda s: s and "@context" in s and "structured-data" not in s)
        js_data = dissect_js(script_tag, 'self.__next_f.push(', ")")
        idx = self._METADATA_IDX
        data = json.loads(js_data[1])["@graph"] if isinstance(
            js_data, list) else js_data["@graph"]
        self._metadata["name"] = data[idx]["name"]
        self._metadata["date"] = dateutil.parser.parse(data[idx + 1]["startDate"]).date()
        arena_fmt = data[idx + 1]["name"]
        if arena_fmt != "Articles":
            self._metadata["arena_format"] = arena_fmt
        self._metadata["author"] = data[idx + 2]["name"]

    @override
    def _parse_metadata(self) -> None:
        fmt_tags = self._soup.select("nav > ol > li >a")
        if fmt_tag := from_iterable(
                fmt_tags, lambda t: "#" not in t.attrs["href"] and t.text != "Videos"):
            self._update_fmt(fmt_tag.text)
        self._parse_metadata_script_tag()
        if rank := self._get_arena_rank():
            self._metadata["arena_rank"] = rank
        # additional
        if arch := self._deck_data.get("archetypeName"):
            self._update_archetype_or_theme(arch)
        if "gamesWon" in self._deck_data and self._deck_data["gamesWon"] is not None:
            self._metadata["games_won"] = self._deck_data["gamesWon"]
        if "gamesLost" in self._deck_data and self._deck_data["gamesLost"] is not None:
            self._metadata["games_lost"] = self._deck_data["gamesLost"]
        if winrate := self._deck_data.get("winrate"):
            self._metadata["winrate"] = winrate
        if name := self._deck_data.get("deckName"):
            self._metadata["name"] = name
        if source := self._deck_data.get("source"):
            self._metadata["original_source"] = source
        if deck_url := self._deck_data.get("deckUrl"):
            self._metadata["original_url"] = deck_url

    def _parse_card(self, card_json: Json) -> list[Card]:
        name = card_json["name"]
        oracle_id = card_json.get("oracle_id", "")
        qty = card_json["quantity"]
        return self.get_playset(self.find_card(name, oracle_id=oracle_id), qty)

    @override
    def _parse_decklist(self) -> None:
        for cat in self._deck_data["decklist"]["mainDeck"]["categories"]:
            for card_json in cat["cards"]:
                self._maindeck += self._parse_card(card_json)

        if sideboard := self._deck_data["decklist"].get("sideboard"):
            for card_json in sideboard["cards"]:
                self._sideboard += self._parse_card(card_json)

        if commander := self._deck_data["decklist"].get("commander"):
            for card_json in commander["cards"]:
                self._set_commander(self._parse_card(card_json)[0])

        if companion := self._deck_data["decklist"].get("companion"):
            for card_json in companion["cards"]:
                self._companion = self._parse_card(card_json)[0]


@DeckScraper.registered
class MtgCircleRegularDeckScraper(MtgCircleVideoDeckScraper):
    """Scraper of MTGCircle regular decklist page.
    """
    _METADATA_IDX = 0  # override

    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "mtgcircle.com/decks/" in url.lower()

    @staticmethod
    @override
    def _retrieve_deck_data(data) -> Json:
        return data[2][3]["children"][3]["children"][1][3]["deck"]
