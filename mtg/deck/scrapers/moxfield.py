"""

    mtg.deck.scrapers.moxfield.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Moxfield decklists.

    @author: z33k

"""
import logging
from datetime import datetime
from typing import override

from selenium.common import TimeoutException

from mtg import Json
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper, FolderContainerScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError, strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup, get_selenium_json

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MoxfieldDeckScraper(DeckScraper):
    """Scraper of Moxfield decklist page.
    """
    API_URL_TEMPLATE = "https://api2.moxfield.com/v3/decks/all/{}"

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        url = url.lower()
        tokens = "public?q=", "/personal"
        return "moxfield.com/decks/" in url and all(t not in url for t in tokens)

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(
            url).removesuffix("/primer").removesuffix("/history").removesuffix("/settings")
        return url.rstrip(".,")

    @override
    def _get_data_from_api(self) -> Json:
        *_, self._decklist_id = self.url.split("/")
        return get_selenium_json(self.API_URL_TEMPLATE.format(self._decklist_id))

    @override
    def _validate_data(self) -> None:
        if not self._data or not self._data.get("boards"):
            raise ScrapingError("Data not available", scraper=type(self), url=self.url)

    @override
    def _parse_metadata(self) -> None:
        fmt = self._data["format"].lower()
        self._update_fmt(fmt)
        name = self._data["name"]
        if " - " in name:
            *_, name = name.split(" - ")
        self._metadata["name"] = name
        self._metadata["likes"] = self._data["likeCount"]
        self._metadata["views"] = self._data["viewCount"]
        self._metadata["comments"] = self._data["commentCount"]
        self._metadata["author"] = self._data["createdByUser"]["displayName"]
        try:
            self._metadata["date"] = datetime.strptime(
                self._data["lastUpdatedAtUtc"], "%Y-%m-%dT%H:%M:%S.%fZ").date()
        except ValueError:  # no fractional seconds part in the date string
            self._metadata["date"] = datetime.strptime(
                self._data["lastUpdatedAtUtc"], "%Y-%m-%dT%H:%M:%SZ").date()
        if desc := self._data["description"]:
            self._metadata["description"] = desc
        if hubs := self._data.get("hubs"):
            self._metadata["hubs"] = self.process_metadata_deck_tags(hubs)
        if edh_bracket := self._data.get("autoBracket"):
            self._metadata["edh_bracket"] = edh_bracket

    @classmethod
    def _to_playset(cls, json_card: Json) -> list[Card]:
        scryfall_id = json_card["card"]["scryfall_id"]
        quantity = json_card["quantity"]
        name = json_card["card"]["name"]
        return cls.get_playset(cls.find_card(name, scryfall_id=scryfall_id), quantity)

    @override
    def _parse_decklist(self) -> None:
        for card in self._data["boards"]["mainboard"]["cards"].values():
            self._maindeck.extend(self._to_playset(card))
        for card in self._data["boards"]["sideboard"]["cards"].values():
            self._sideboard.extend(self._to_playset(card))
        # Oathbreaker is not fully supported by Deck objects
        if signature_spells := self._data["boards"]["signatureSpells"]:
            for card in signature_spells["cards"].values():
                self._maindeck.extend(self._to_playset(card))
        for card in self._data["boards"]["commanders"]["cards"].values():
            result = self._to_playset(card)
            self._set_commander(result[0])
        if self._data["boards"]["companions"]["cards"]:
            card = next(iter(self._data["boards"]["companions"]["cards"].items()))[1]
            result = self._to_playset(card)
            self._companion = result[0]


@FolderContainerScraper.registered
@DeckUrlsContainerScraper.registered
class MoxfieldBookmarkScraper(DeckUrlsContainerScraper):
    """Scraper of Moxfield bookmark page.
    """
    CONTAINER_NAME = "Moxfield bookmark"  # override
    API_URL_TEMPLATE = "https://api2.moxfield.com/v1/bookmarks/{}"  # override
    DECK_SCRAPERS = MoxfieldDeckScraper,  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "moxfield.com/bookmarks/" in url.lower()

    def _get_bookmark_id(self) -> str:
        *_, last = self.url.split("/")
        if "-" in last:
            id_, *_ = last.split("-")
            return id_
        return last

    @override
    def _get_data_from_api(self) -> Json:
        return get_selenium_json(self.API_URL_TEMPLATE.format(self._get_bookmark_id()))

    def _validate_data(self) -> None:
        if not self._data or not self._data.get("decks") or not self._data["decks"].get("data"):
            raise ScrapingError("Data not available", scraper=type(self), url=self.url)

    @override
    def _collect(self) -> list[str]:
        return [d["deck"]["publicUrl"] for d in self._data["decks"]["data"]]


@DeckUrlsContainerScraper.registered
class MoxfieldUserScraper(DeckUrlsContainerScraper):
    """Scraper of Moxfield user page.
    """
    CONTAINER_NAME = "Moxfield user"  # override
    # 100 page size is pretty arbitrary but tested to work
    API_URL_TEMPLATE = ("https://api2.moxfield.com/v2/decks/search?includePinned=true&showIllegal"
                        "=true&authorUserNames={}&pageNumber=1&pageSize=100&sortType="
                        "updated&sortDirection=descending&board=mainboard")  # override
    DECK_SCRAPERS = MoxfieldDeckScraper,  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "moxfield.com/users/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _get_data_from_api(self) -> Json:
        *_, last = self.url.split("/")
        return get_selenium_json(self.API_URL_TEMPLATE.format(last))

    def _validate_data(self) -> None:
        if not self._data or not self._data.get("data"):
            raise ScrapingError("Data not available", scraper=type(self), url=self.url)

    @override
    def _collect(self) -> list[str]:
        return [d["publicUrl"] for d in self._data["data"]]


@DeckUrlsContainerScraper.registered
class MoxfieldSearchScraper(DeckUrlsContainerScraper):
    """Scraper of Moxfield search results page.
    """
    SELENIUM_PARAMS = {  # override
        "xpath": "//input[@id='filter']"
    }
    CONTAINER_NAME = "Moxfield search results"  # override
    # 100 page size is pretty arbitrary but tested to work
    API_URL_TEMPLATE = ("https://api2.moxfield.com/v2/decks/search?pageNumber=1&pageSize=100&sort"
                        "Type=updated&sortDirection=descending&filter={}")  # override
    DECK_SCRAPERS = MoxfieldDeckScraper,  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "moxfield.com/decks/public?q=" in url.lower()

    @override
    def _pre_parse(self) -> None:
        pass

    def _get_filter(self) -> str | None:
        try:
            soup, _, _ = get_dynamic_soup(self.url, self.SELENIUM_PARAMS["xpath"])
            if not soup:
                return None
        except TimeoutException:
            return None

        input_tag = soup.find("input", id="filter")
        if not input_tag:
            return None

        return input_tag.attrs["value"]

    @override
    def _collect(self) -> list[str]:
        filter_ = self._get_filter()
        if not filter_:
            raise ScrapingError(
                "API URL 'filter' parameter not found", scraper=type(self), url=self.url)
        api_url = self.API_URL_TEMPLATE.format(filter_)
        json_data = get_selenium_json(api_url)
        if not json_data or not json_data.get("data"):
            raise ScrapingError("Data not available", scraper=type(self), url=self.url)
        return [d["publicUrl"] for d in json_data["data"]]
