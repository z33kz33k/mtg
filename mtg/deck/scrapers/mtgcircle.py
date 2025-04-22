"""

    mtg.deck.scrapers.mtgcircle.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGCircle decklists.

    @author: z33k

"""
import json
import logging
from datetime import UTC, datetime
from typing import Callable, Type, override

from bs4 import BeautifulSoup, Tag

from mtg import Json
from mtg.deck import Deck
from mtg.deck.scrapers import DeckScraper, HybridContainerScraper, JsonBasedDeckParser
from mtg.scryfall import Card, all_formats
from mtg.utils import from_iterable
from mtg.utils.scrape import ScrapingError, dissect_js

_log = logging.getLogger(__name__)


class MtgCircleDeckJsonParser(JsonBasedDeckParser):
    """Parser of MTGCircle deck JSON data.
    """
    def _parse_metadata(self) -> None:
        if fmt := self._deck_data.get("format"):
            self._update_fmt(fmt)
        arch = self._deck_data.get("archetypeName")
        if arch:
            self._update_archetype_or_theme(arch)
        if name := self._deck_data.get("deckName"):
            self._metadata["name"] = name
        elif arch:
            self._metadata["name"] = arch
        if author := self._deck_data.get("deckAuthorName"):
            self._metadata["author"] = author
        if "gamesWon" in self._deck_data and self._deck_data["gamesWon"] is not None:
            self._metadata["games_won"] = self._deck_data["gamesWon"]
        if "gamesLost" in self._deck_data and self._deck_data["gamesLost"] is not None:
            self._metadata["games_lost"] = self._deck_data["gamesLost"]
        if winrate := self._deck_data.get("winrate"):
            self._metadata["winrate"] = winrate
        if source := self._deck_data.get("source"):
            self._metadata["original_source"] = source
        if date := self._deck_data.get("date"):
            self._metadata["date"] = datetime.fromtimestamp(date / 1000, UTC).date()
        if arena_fmt := self._deck_data.get("eventName"):
            self._metadata.setdefault("arena", {})["format"] = arena_fmt
        if arena_rank := self._deck_data.get("rank"):
            self._metadata.setdefault("arena", {})["rank"] = arena_rank
        if arena_mode := self._deck_data.get("gameMode"):
            self._metadata.setdefault("arena", {})["mode"] = arena_mode

    def _parse_card(self, card_json: Json) -> list[Card]:
        name = card_json["name"]
        qty = card_json["quantity"]
        setcode, collector_number = card_json.get("set", ""), card_json.get("collector_number", "")
        set_and_number = (setcode, collector_number) if setcode and collector_number else None
        oracle_id = card_json.get("oracle_id", "")
        return self.get_playset(self.find_card(
            name, set_and_collector_number=set_and_number, oracle_id=oracle_id), qty)

    @override
    def _parse_decklist(self) -> None:
        for card_json in self._deck_data["cards"]:
            match card_json["deckPos"]:
                case "mainDeck":
                    self._maindeck += self._parse_card(card_json)
                case "sideboard":
                    self._sideboard += self._parse_card(card_json)
                case "commander":
                    self._set_commander(self._parse_card(card_json)[0])
                case "companion":
                    self._companion = self._parse_card(card_json)[0]
                case _:
                    pass


def get_data(
        soup: BeautifulSoup, scraper: Type[DeckScraper] | Type[HybridContainerScraper],
        retriever: Callable[[Json], Json], start_pos=3) -> Json:
    try:
        tokens = "cards", "deckPos", "mainDeck", "name", "quantity"
        script_tag = soup.find("script", string=lambda s: s and all(t in s for t in tokens))
        js_data = dissect_js(
            script_tag, 'self.__next_f.push(', '|||dummy|||', end_processor=lambda t: t[:-1])
        data = json.loads(js_data[1][start_pos:])
        return retriever(data)
    except (AttributeError, KeyError):
        raise ScrapingError("Deck data not available", scraper=scraper)


@DeckScraper.registered
class MtgCircleVideoDeckScraper(DeckScraper):
    """Scraper of MTGCircle video decklist page.
    """
    DATA_FROM_SOUP = True  # override

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_parser: MtgCircleDeckJsonParser | None = None

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        if "mtgcircle.com/videos/" not in url.lower():
            return False
        *_, rest = url.lower().split("mtgcircle.com/videos/")
        if "/" not in rest:
            return False
        return True

    # TODO: naive approach won't cut it as they change the structure all the time - a generic
    #  retriever from structured data is needed that would accept the structure and a predicate
    #  on item that is looked for (#328)
    @staticmethod
    def _retrieve_deck_data(data: Json) -> Json:
        return data[1][3]["children"][3]["children"][2][3]["children"][0][3]["deck"]

    @override
    def _get_data_from_soup(self) -> Json:
        return get_data(self._soup, type(self), self._retrieve_deck_data)

    def _get_deck_parser(self) -> MtgCircleDeckJsonParser:
        return MtgCircleDeckJsonParser(self._data, self._metadata)

    @override
    def _parse_metadata(self) -> None:
        fmt_tags = self._soup.select("nav > ol > li > a")
        if fmt_tag := from_iterable(
                fmt_tags,
                lambda t: "#" not in t.attrs["href"] and t.text != "Videos"
                          and t.text.lower() in all_formats()):
            self._update_fmt(fmt_tag.text)

        self._deck_parser.update_metadata(**self._metadata)

    @override
    def _parse_decklist(self) -> None:
        pass

    @override
    def _build_deck(self) -> Deck:
        return self._deck_parser.parse()


@DeckScraper.registered
class MtgCircleRegularDeckScraper(MtgCircleVideoDeckScraper):
    """Scraper of MTGCircle regular decklist page.
    """
    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        if "mtgcircle.com/decks/" not in url.lower():
            return False
        *_, rest = url.lower().split("mtgcircle.com/decks/")
        if "/" not in rest:
            return False
        return True

    @staticmethod
    @override
    def _retrieve_deck_data(data) -> Json:
        return data[1][3]["children"][3]["children"][1][3]["deck"]


@HybridContainerScraper.registered
class MtgCircleArticleScraper(HybridContainerScraper):
    """Scraper of MTGCircle article page.
    """
    CONTAINER_NAME = "MTGCircle article"  # override
    JSON_BASED_DECK_PARSER = MtgCircleDeckJsonParser  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "mtgcircle.com/articles/" in url.lower()

    @staticmethod
    def _retrieve_date_data(data: Json) -> Json:
        return data[2][3]["children"][0][3]["children"][0][2][3]["children"][1][3]["children"][3][
            "children"][3]["children"][3]

    @override
    def _parse_metadata(self) -> None:
        headline_tag = self._soup.select_one("div.container-custom > div > h1")
        self._metadata["title"] = headline_tag.text.strip()
        css = "div.container-custom > div > span > a > li.items-center.bg-paper"
        fmt_tag, *info_tags = self._soup.select(css)
        self._update_fmt(fmt_tag.text.strip())
        self._metadata["article_tags"] = [t.text.strip().lower() for t in info_tags]
        date_data = get_data(
            self._soup, type(self), retriever=self._retrieve_date_data, start_pos=2)
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
        decks_data = get_data(
            self._soup, type(self), retriever=self._retrieve_decks_data, start_pos=2)
        article_tag = self._soup.find("article")
        if not article_tag:
            _log.warning("Article tag not found")
            return [], [], decks_data, []
        deck_urls, _ = self._get_links_from_tags(*article_tag.find_all("p"))
        return deck_urls, [], decks_data, []
