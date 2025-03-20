"""

    mtg.deck.scrapers.mtgcircle.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGCircle decklists.

    @author: z33k

"""
from datetime import datetime, UTC
import json
import logging
from typing import Callable, override

import dateutil.parser
from bs4 import BeautifulSoup, Tag

from mtg import Json
from mtg.deck import Deck
from mtg.deck.scrapers import DeckScraper, HybridContainerScraper, JsonBasedDeckParser
from mtg.scryfall import Card
from mtg.utils import from_iterable
from mtg.utils.scrape import ScrapingError, dissect_js
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)


class MtgCircleDeckJsonParser(JsonBasedDeckParser):
    """Parser of MTGCircle deck JSON data.
    """
    def _parse_metadata(self) -> None:
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


def get_data(soup: BeautifulSoup, retriever: Callable[[Json], Json], start_pos=3) -> Json:
    try:
        script_tag = soup.find(
            "script", string=lambda s: s and "structured-data" in s and "@context" not in s)
        js_data = dissect_js(
            script_tag, 'self.__next_f.push(', '|||dummy|||', end_processor=lambda t: t[:-1])
        data = json.loads(js_data[1][start_pos:])
        return retriever(data)
    except (AttributeError, KeyError):
        raise ScrapingError("Deck data not available")


@DeckScraper.registered
class MtgCircleVideoDeckScraper(DeckScraper):
    """Scraper of MTGCircle video decklist page.
    """
    _METADATA_IDX = 1

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_parser: MtgCircleDeckJsonParser | None = None

    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        if "mtgcircle.com/videos/" not in url.lower():
            return False
        *_, rest = url.lower().split("mtgcircle.com/videos/")
        if "/" not in rest:
            return False
        return True

    @staticmethod
    def _retrieve_deck_data(data: Json) -> Json:
        return data[2][3]["children"][3]["children"][2][3]["children"][0][3]["deck"]

    @override
    def _pre_parse(self) -> None:
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._deck_data = get_data(self._soup, self._retrieve_deck_data)

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

    @override
    def _parse_decklist(self) -> None:
        self._deck_parser = MtgCircleDeckJsonParser(self._deck_data, self._metadata)

    @override
    def _build_deck(self) -> Deck:
        return self._deck_parser.parse()


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


@HybridContainerScraper.registered
class MtgCircleArticleScraper(HybridContainerScraper):
    """Scraper of MTGCircle article page.
    """
    CONTAINER_NAME = "MTGCircle article"  # override
    JSON_BASED_DECK_PARSER = MtgCircleDeckJsonParser  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "mtgcircle.com/articles/" in url.lower()

    @staticmethod
    def _retrieve_date_data(data: Json) -> Json:
        return data[2][3]["children"][0][3]["children"][0][2][3]["children"][1][3]["children"][3][
            "children"][3]["children"][3]

    @override
    def _parse_metadata(self) -> None:
        headline_tag = self._soup.select_one("div.container-custom > div > h1")
        self._metadata["headline"] = headline_tag.text.strip()
        css = "div.container-custom > div > span > a > li.items-center.bg-paper"
        fmt_tag, *info_tags = self._soup.select(css)
        self._update_fmt(fmt_tag.text.strip())
        self._metadata["article_tags"] = [t.text.strip().lower() for t in info_tags]
        date_data = get_data(self._soup, retriever=self._retrieve_date_data, start_pos=2)
        self._metadata["date"] = datetime.fromtimestamp(date_data["date"] / 1000, UTC).date()

    @staticmethod
    def _retrieve_decks_data(data: Json) -> list[Json]:
        decks_data = []
        lst = data[2][3]["children"][0][3]["children"][1][3]["children"][1]
        for d in lst:
            try:
                decks_data.append(d[3]["children"][3]["children"][3]["deck"])
            except (KeyError, IndexError, TypeError):
                pass
        return decks_data

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        self._parse_metadata()
        decks_data = get_data(self._soup, retriever=self._retrieve_decks_data, start_pos=2)
        article_tag = self._soup.find("article")
        if not article_tag:
            _log.warning("Article tag not found")
            return [], [], decks_data, []
        deck_urls, _ = self._get_links_from_tags(*article_tag.find_all("p"))
        return deck_urls, [], decks_data, []
