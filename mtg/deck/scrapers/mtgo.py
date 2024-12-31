"""

    mtg.deck.scrapers.mtgo.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGO decklists.

    @author: z33k

"""
import logging

import dateutil.parser
from bs4 import BeautifulSoup

from mtg import Json, SECRETS
from mtg.deck import Deck
from mtg.deck.scrapers import JsonBasedDeckScraper, UrlBasedDeckScraper
from mtg.scryfall import all_formats
from mtg.utils import from_iterable, get_ordinal_suffix
from mtg.utils.scrape import ScrapingError, dissect_js, getsoup, strip_url_params

_log = logging.getLogger(__name__)


HEADERS = {
    "Host": "www.mtgo.com",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Sec-GPC": "1",
    "Connection": "keep-alive",
    "Cookie": SECRETS["mtgo"]["cookie"],
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Priority": "u=0, i",
}


class MgtoJsonBasedDeckScraper(JsonBasedDeckScraper):
    """Scraper of MGTO individual decklist JSON data.
    """
    def _derive_name(self) -> str:
        name = self._deck_data["player"]
        if wins := self._deck_data.get("wins"):
            name += f" ({wins['wins']}-{wins['losses']})"
        elif rank := self._deck_data.get("final_rank"):
            rank = int(rank)
            name += f" ({rank}{get_ordinal_suffix(rank)} place)"
        return name

    def _parse_metadata(self) -> None:
        self._metadata["author"] = self._deck_data["player"]
        self._metadata["name"] = self._derive_name()
        if fmt := self._metadata.get("event", {}).get("format"):
            self._update_fmt(fmt)

    def _parse_card(self, card: Json) -> None:
        decklist = self._sideboard if card["sideboard"] == "true" else self._maindeck
        qty = int(card["qty"])
        name = card["card_attributes"]["card_name"]
        mtgo_id = int(card["card_attributes"]["digitalobjectcatalogid"])
        card = self.find_card(name, mtgo_id=mtgo_id)
        decklist += self.get_playset(card, qty)

    def _parse_decklist(self) -> None:
        for card in [*self._deck_data["main_deck"], *self._deck_data.get("sideboard_deck", [])]:
            self._parse_card(card)


@UrlBasedDeckScraper.registered
class MgtoUrlBasedDeckScraper(UrlBasedDeckScraper):
    """Scraper of MGTO decklists page that points to an individual deck.
    """
    _FORMATS = {
        "cstandard": "standard",
        "cmodern": "modern",
        "cpioneer": "pioneer",
        "cvintage": "vintage",
        "clegacy": "legacy",
        "cpauper": "pauper",
    }

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._json_data: Json | None = None
        self._player_name = self._parse_player_name()
        self._decks_data, self._deck_scraper = [], None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return f"mtgo.com/decklist/" in url.lower() and "#deck_" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url, with_endpoint=False)

    def _parse_player_name(self) -> str:
        *_, rest = self.url.split("/")
        _, rest = rest.split("#")
        return rest.removeprefix("deck_")

    @staticmethod
    def get_json(soup: BeautifulSoup) -> Json:
        data = dissect_js(
            soup, "window.MTGO.decklists.data = ", "window.MTGO.decklists.type",
            lambda s: s.rstrip().rstrip(";"))
        if data is None:
            raise ScrapingError("Data not available")
        return data

    @staticmethod
    def get_decks_data(json_data: Json) -> list[Json]:
        return json_data["decklists"]

    @classmethod
    def get_event_metadata(cls, json_data: Json) -> Json:
        metadata = {"event": {}}
        if name := json_data.get("description"):
            metadata["event"]["name"] = name
        elif name := json_data.get("name"):
            metadata["event"]["name"] = name
        if type_ := json_data.get("type"):
            metadata["event"]["type"] = type_.lower()
        if player_count := json_data.get("player_count", {}).get("players"):
            metadata["event"]["player_count"] = int(player_count)
        date = json_data.get("starttime") or json_data.get("publish_date")
        if date:
            metadata["event"]["date"] = dateutil.parser.parse(date).date()
        fmt = json_data.get("format")
        if fmt:
            fmt = cls._FORMATS.get(fmt.lower())
            if not fmt:
                if site_name := json_data.get("site_name"):
                    fmt = from_iterable(site_name.split("-"), lambda t: t in all_formats())
            if fmt:
                metadata["event"]["format"] = fmt
        return metadata

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._json_data = self.get_json(self._soup)
        self._decks_data = self.get_decks_data(self._json_data)
        deck_data = from_iterable(
            self._decks_data, lambda d: d["player"] == self._player_name)
        if not deck_data:
            raise ScrapingError(f"Deck designated by {self._player_name!r} not found")
        if rank_data := self._json_data.get("final_rank"):
            deck_rank_data = from_iterable(
                rank_data, lambda d: d["loginid"] == deck_data["loginid"])
            deck_data["final_rank"] = deck_rank_data["rank"]
        self._metadata.update(self.get_event_metadata(self._json_data))
        self._deck_scraper = MgtoJsonBasedDeckScraper(deck_data, self._metadata)

    def _parse_metadata(self) -> None:  # override
        pass

    def _parse_decklist(self) -> None:  # override
        pass

    def _build_deck(self) -> Deck:  # override
        return self._deck_scraper.scrape()
