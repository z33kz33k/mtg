"""

    mtg.deck.scrapers.moxfield.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Moxfield decklists.

    @author: z33k

"""
import logging
from datetime import datetime

from selenium.common import TimeoutException

from mtg import Json
from mtg.deck.scrapers import DeckUrlsContainerScraper, DeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError, strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup, get_selenium_json

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MoxfieldDeckScraper(DeckScraper):
    """Scraper of Moxfield decklist page.
    """
    API_URL_TEMPLATE = "https://api2.moxfield.com/v3/decks/all/{}"

    def __init__(
            self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        *_, self._decklist_id = self.url.split("/")

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        url = url.lower()
        tokens = "public?q=", "/personal"
        return "moxfield.com/decks/" in url and all(t not in url for t in tokens)

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_query(url).removesuffix("/primer").removesuffix("/history")
        return url.rstrip(".,")

    def _pre_parse(self) -> None:  # override
        self._deck_data = get_selenium_json(self.API_URL_TEMPLATE.format(self._decklist_id))
        if not self._deck_data or not self._deck_data.get("boards"):
            raise ScrapingError("Data not available")

    def _parse_metadata(self) -> None:  # override
        fmt = self._deck_data["format"].lower()
        self._update_fmt(fmt)
        name = self._deck_data["name"]
        if " - " in name:
            *_, name = name.split(" - ")
        self._metadata["name"] = name
        self._metadata["likes"] = self._deck_data["likeCount"]
        self._metadata["views"] = self._deck_data["viewCount"]
        self._metadata["comments"] = self._deck_data["commentCount"]
        self._metadata["author"] = self._deck_data["createdByUser"]["displayName"]
        try:
            self._metadata["date"] = datetime.strptime(
                self._deck_data["lastUpdatedAtUtc"], "%Y-%m-%dT%H:%M:%S.%fZ").date()
        except ValueError:  # no fractional seconds part in the date string
            self._metadata["date"] = datetime.strptime(
                self._deck_data["lastUpdatedAtUtc"], "%Y-%m-%dT%H:%M:%SZ").date()
        if desc := self._deck_data["description"]:
            self._metadata["description"] = desc
        if hubs := self._deck_data.get("hubs"):
            self._metadata["hubs"] = hubs
        if edh_bracket := self._deck_data.get("autoBracket"):
            self._metadata["edh_bracket"] = edh_bracket

    @classmethod
    def _to_playset(cls, json_card: Json) -> list[Card]:
        scryfall_id = json_card["card"]["scryfall_id"]
        quantity = json_card["quantity"]
        name = json_card["card"]["name"]
        return cls.get_playset(cls.find_card(name, scryfall_id=scryfall_id), quantity)

    def _parse_decklist(self) -> None:  # override
        for card in self._deck_data["boards"]["mainboard"]["cards"].values():
            self._maindeck.extend(self._to_playset(card))
        for card in self._deck_data["boards"]["sideboard"]["cards"].values():
            self._sideboard.extend(self._to_playset(card))
        # Oathbreaker is not fully supported by Deck objects
        if signature_spells := self._deck_data["boards"]["signatureSpells"]:
            for card in signature_spells["cards"].values():
                self._maindeck.extend(self._to_playset(card))
        for card in self._deck_data["boards"]["commanders"]["cards"].values():
            result = self._to_playset(card)
            self._set_commander(result[0])
        if self._deck_data["boards"]["companions"]["cards"]:
            card = next(iter(self._deck_data["boards"]["companions"]["cards"].items()))[1]
            result = self._to_playset(card)
            self._companion = result[0]


@DeckUrlsContainerScraper.registered
class MoxfieldBookmarkScraper(DeckUrlsContainerScraper):
    """Scraper of Moxfield bookmark page.
    """
    CONTAINER_NAME = "Moxfield bookmark"  # override
    API_URL_TEMPLATE = "https://api2.moxfield.com/v1/bookmarks/{}"
    DECK_SCRAPERS = MoxfieldDeckScraper,  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "moxfield.com/bookmarks/" in url.lower()

    def _get_bookmark_id(self) -> str:
        *_, last = self.url.split("/")
        if "-" in last:
            id_, *_ = last.split("-")
            return id_
        return last

    def _collect(self) -> list[str]:  # override
        json_data = get_selenium_json(
            self.API_URL_TEMPLATE.format(self._get_bookmark_id()))
        if not json_data or not json_data.get("decks") or not json_data["decks"].get("data"):
            _log.warning(self._error_msg)
            return []
        return [d["deck"]["publicUrl"] for d in json_data["decks"]["data"]]


@DeckUrlsContainerScraper.registered
class MoxfieldUserScraper(DeckUrlsContainerScraper):
    """Scraper of Moxfield user page.
    """
    CONTAINER_NAME = "Moxfield user"  # override
    # 100 page size is pretty arbitrary but tested to work
    API_URL_TEMPLATE = ("https://api2.moxfield.com/v2/decks/search?includePinned=true&showIllegal"
                        "=true&authorUserNames={}&pageNumber=1&pageSize=100&sortType="
                        "updated&sortDirection=descending&board=mainboard")
    DECK_SCRAPERS = MoxfieldDeckScraper,  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "moxfield.com/users/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _get_user_name(self) -> str:
        *_, last = self.url.split("/")
        return last

    def _collect(self) -> list[str]:  # override
        json_data = get_selenium_json(self.API_URL_TEMPLATE.format(self._get_user_name()))
        if not json_data or not json_data.get("data"):
            _log.warning(self._error_msg)
            return []
        return [d["publicUrl"] for d in json_data["data"]]


@DeckUrlsContainerScraper.registered
class MoxfieldSearchScraper(DeckUrlsContainerScraper):
    """Scraper of Moxfield search results page.
    """
    CONTAINER_NAME = "Moxfield search results"  # override
    # 100 page size is pretty arbitrary but tested to work
    API_URL_TEMPLATE = ("https://api2.moxfield.com/v2/decks/search?pageNumber=1&pageSize=100&sort"
                        "Type=updated&sortDirection=descending&filter={}")
    DECK_SCRAPERS = MoxfieldDeckScraper,  # override
    XPATH = "//input[@id='filter']"

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "moxfield.com/decks/public?q=" in url.lower()

    def _get_filter(self) -> str | None:
        try:
            soup, _, _ = get_dynamic_soup(self.url, self.XPATH)
            if not soup:
                _log.warning(self._error_msg)
                return None
        except TimeoutException:
            _log.warning(self._error_msg)
            return None

        input_tag = soup.find("input", id="filter")
        if not input_tag:
            _log.warning(self._error_msg)
            return None

        return input_tag.attrs["value"]

    def _collect(self) -> list[str]:  # override
        filter_ = self._get_filter()
        if not filter_:
            _log.warning(self._error_msg)
            return []
        api_url = self.API_URL_TEMPLATE.format(filter_)
        json_data = get_selenium_json(api_url)
        if not json_data or not json_data.get("data"):
            _log.warning(self._error_msg)
            return []
        return [d["publicUrl"] for d in json_data["data"]]
