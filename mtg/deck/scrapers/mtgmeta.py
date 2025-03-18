"""

    mtg.deck.scrapers.mtgmeta.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGMeta.io decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils import extract_float
from mtg.utils.scrape import ScrapingError, dissect_js, get_wayback_soup, strip_url_query

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MtgMetaIoDeckScraper(DeckScraper):
    """Scraper of MTGMeta.io decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._json_data: Json | None = None

    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "mtgmeta.io/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        self._soup = get_wayback_soup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._json_data = dissect_js(self._soup, "const decklist = ", " ;\n  ")

    @override
    def _parse_metadata(self) -> None:
        if fmt_tag := self._soup.find(
            "a", class_="crumb", string=lambda s: s and "Home" not in s and "Decks" not in s):
            self._update_fmt(fmt_tag.text.strip())
        self._metadata["name"] = self._json_data["dname"]
        if player := self._json_data.get("pname"):
            self._metadata["author"] = player
        if event := self._json_data.get("tname"):
            self._metadata["event"] = {}
            self._metadata["event"]["name"] = event
        if place := self._json_data.get("place"):
            self._metadata.setdefault("event", {})["place"] = int(place)
        if info_tag := self._soup.select_one("ul#deckstats"):
            li_tags = [*info_tag.find_all("li")]
            for i, li_tag in enumerate(li_tags):
                text = li_tag.text.strip()
                if "Metashare" in text:
                    self._metadata.setdefault("meta", {})["share"] = extract_float(text)
                elif text.endswith(" Global Performance"):
                    self._metadata.setdefault("meta", {})[
                        "global_performance"] = text.removesuffix(" Global Performance")
                elif i == len(li_tags) - 1:
                    if " - " in text:
                        *_, text = text.split(" - ")
                    self._metadata["date"] = dateutil.parser.parse(text).date()

    @classmethod
    def _parse_card_json(cls, card_json: Json) -> list[Card]:
        name = card_json["card"]
        qty = int(card_json["quantity"])
        return cls.get_playset(cls.find_card(name), qty)

    @override
    def _parse_decklist(self) -> None:
        for card_json in self._json_data["main"]:
            self._maindeck += self._parse_card_json(card_json)

        if sideboard := self._json_data.get("side"):
            for card_json in sideboard:
                self._sideboard += self._parse_card_json(card_json)
