"""

    mtg.deck.scrapers.mtgo.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGO decklists.

    @author: z33k

"""
import logging

import dateutil.parser
from bs4 import BeautifulSoup, Tag

from mtg import Json, SECRETS
from mtg.deck import Deck, Mode
from mtg.deck.scrapers import DeckUrlsContainerScraper, JsonBasedDeckScraper, TagBasedDeckScraper, \
    UrlBasedDeckScraper
from mtg.scryfall import all_formats
from mtg.utils import extract_int, from_iterable, timed
from mtg.utils.scrape import ScrapingError, dissect_js, getsoup, http_requests_counted, \
    strip_url_params, \
    throttled_soup

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


# class MgtoJsonBasedDeckScraper(JsonBasedDeckScraper):
#     """Scraper of MGTO individual decklist JSON data.
#     """
#     _FORMATS = {
#         "cstandard": "standard",
#         "cmodern": "modern",
#         "cpioneer": "pioneer",
#         "cvintage": "vintage",
#         "clegacy": "legacy",
#         "cpauper": "pauper",
#     }
#
#
#
# @UrlBasedDeckScraper.registered
# class MgtoUrlBasedDeckScraper(MgtoJsonBasedDeckScraper, UrlBasedDeckScraper):
#     """Scraper of MGTO decklists page that points to an individual deck.
#     """
#     def __init__(self, url: str, metadata: Json | None = None) -> None:
#         super().__init__(url, metadata)
#         self._json_data: Json | None = None
#         self._player_name = self._parse_player_name()
#         self._decks_data, self._deck_data = [], None
#
#     @staticmethod
#     def is_deck_url(url: str) -> bool:  # override
#         return f"mtgo.com/decklist/" in url.lower() and "#deck_" in url.lower()
#
#     @staticmethod
#     def sanitize_url(url: str) -> str:  # override
#         return strip_url_params(url, with_endpoint=False)
#
#     def _parse_player_name(self) -> str:
#         *_, rest = self.url.split("/")
#         return rest.removeprefix("#deck_")
#
#     @staticmethod
#     def get_json(soup: BeautifulSoup) -> Json:
#         data = dissect_js(
#             soup, "window.MTGO.decklists.data = ", "window.MTGO.decklists.type",
#             lambda s: s.rstrip().rstrip(";"))
#         if data is None:
#             raise ScrapingError("Data not available")
#         return data
#
#     @staticmethod
#     def get_decks_data(json_data: Json) -> list[Json]:
#         return json_data["decklists"]
#
#     @classmethod
#     def get_event_metadata(cls, json_data: Json) -> Json:
#         metadata = {"event": {}}
#         if name := json_data.get("description"):
#             metadata["event"]["name"] = name
#         elif name := json_data.get("name"):
#             metadata["event"]["name"] = name
#         if type_ := json_data.get("type"):
#             metadata["event"]["type"] = type_.lower()
#         if player_count := json_data.get("player_count", {}).get("players"):
#             metadata["event"]["player_count"] = player_count
#         date = json_data.get("starttime") or json_data.get("publish_date")
#         if date:
#             metadata["event"]["date"] = dateutil.parser.parse(date).date()
#         fmt = json_data.get("format")
#         if fmt:
#             fmt = cls._FORMATS.get(fmt.lower())
#             if not fmt:
#                 if site_name := json_data.get("site_name"):
#                     fmt = from_iterable(site_name.split("-"), lambda t: t in all_formats())
#             if fmt:
#                 metadata["event"]["format"] = fmt
#         return metadata
#
#     def _pre_parse(self) -> None:  # override
#         self._soup = getsoup(self.url)
#         if not self._soup:
#             raise ScrapingError("Page not available")
#         self._json_data = self.get_json(self._soup)
#         self._decks_data = self.get_decks_data(self._json_data)
#         self._deck_data = from_iterable(
#             self._decks_data, lambda d: d["player"] == self._player_name)
#         if not self._deck_data:
#             raise ScrapingError(f"Deck designated by {self._player_name!r} not found")
#
#     def _parse_metadata(self) -> None:  # override
#         pass
#
#     def _parse_card_json(self, card_json: Json) -> None:
#         pass
#
#     def _parse_decklist(self) -> None:  # override
#         for card_data in self._json_data:
#             self._parse_card_json(card_data)
#         self._derive_commander_from_sideboard()
