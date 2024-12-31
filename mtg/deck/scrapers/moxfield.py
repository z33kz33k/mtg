"""

    mtg.deck.scrapers.moxfield.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Moxfield decklists.

    @author: z33k

"""
import logging
from datetime import datetime

from mtg import Json
from mtg.deck.scrapers import DeckUrlsContainerScraper, UrlBasedDeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError, get_selenium_json, strip_url_params

_log = logging.getLogger(__name__)


@UrlBasedDeckScraper.registered
class MoxfieldDeckScraper(UrlBasedDeckScraper):
    """Scraper of Moxfield decklist page.
    """
    API_URL_TEMPLATE = "https://api2.moxfield.com/v3/decks/all/{}"
    def __init__(
            self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        *_, self._decklist_id = self.url.split("/")
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        url = url.lower()
        return "moxfield.com/decks/" in url and "/personal" not in url and "/history" not in url

    def _pre_parse(self) -> None:  # override
        self._json_data = get_selenium_json(self.API_URL_TEMPLATE.format(self._decklist_id))
        if not self._json_data or not self._json_data.get("boards"):
            raise ScrapingError("Data not available")

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url, with_endpoint=False)
        if url.endswith("/primer"):
            return url.removesuffix("/primer")
        elif url.endswith("/primer/"):
            return url.removesuffix("/primer/")
        return url.rstrip(".,")

    def _parse_metadata(self) -> None:  # override
        fmt = self._json_data["format"].lower()
        self._update_fmt(fmt)
        name = self._json_data["name"]
        if " - " in name:
            *_, name = name.split(" - ")
        self._metadata["name"] = name
        self._metadata["likes"] = self._json_data["likeCount"]
        self._metadata["views"] = self._json_data["viewCount"]
        self._metadata["comments"] = self._json_data["commentCount"]
        self._metadata["author"] = self._json_data["createdByUser"]["displayName"]
        try:
            self._metadata["date"] = datetime.strptime(
                self._json_data["lastUpdatedAtUtc"], "%Y-%m-%dT%H:%M:%S.%fZ").date()
        except ValueError:  # no fractional seconds part in the date string
            self._metadata["date"] = datetime.strptime(
                self._json_data["lastUpdatedAtUtc"], "%Y-%m-%dT%H:%M:%SZ").date()

        if desc := self._json_data["description"]:
            self._metadata["description"] = desc

    @classmethod
    def _to_playset(cls, json_card: Json) -> list[Card]:
        scryfall_id = json_card["card"]["scryfall_id"]
        quantity = json_card["quantity"]
        name = json_card["card"]["name"]
        return cls.get_playset(cls.find_card(name, scryfall_id=scryfall_id), quantity)

    def _parse_decklist(self) -> None:  # override
        for card in self._json_data["boards"]["mainboard"]["cards"].values():
            self._maindeck.extend(self._to_playset(card))
        for card in self._json_data["boards"]["sideboard"]["cards"].values():
            self._sideboard.extend(self._to_playset(card))
        # Oathbreaker is not fully supported by Deck objects
        if signature_spells := self._json_data["boards"]["signatureSpells"]:
            for card in signature_spells["cards"].values():
                self._maindeck.extend(self._to_playset(card))
        for card in self._json_data["boards"]["commanders"]["cards"].values():
            result = self._to_playset(card)
            self._set_commander(result[0])
        if self._json_data["boards"]["companions"]["cards"]:
            card = next(iter(self._json_data["boards"]["companions"]["cards"].items()))[1]
            result = self._to_playset(card)
            self._companion = result[0]


@DeckUrlsContainerScraper.registered
class MoxfieldBookmarkScraper(DeckUrlsContainerScraper):
    """Scraper of Moxfield bookmark page.
    """
    CONTAINER_NAME = "Moxfield bookmark"  # override
    API_URL_TEMPLATE = "https://api2.moxfield.com/v1/bookmarks/{}"
    _DECK_SCRAPER = MoxfieldDeckScraper  # override

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
    _DECK_SCRAPER = MoxfieldDeckScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "moxfield.com/users/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url, with_endpoint=False)

    def _get_user_name(self) -> str:
        *_, last = self.url.split("/")
        return last

    def _collect(self) -> list[str]:  # override
        json_data = get_selenium_json(self.API_URL_TEMPLATE.format(self._get_user_name()))
        if not json_data or not json_data.get("data"):
            _log.warning(self._error_msg)
            return []
        return [d["publicUrl"] for d in json_data["data"]]
