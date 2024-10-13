"""

    mtg.deck.scrapers.moxfield.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Moxfield decklists.

    @author: z33k

"""
import logging
from datetime import datetime

from mtg import Json
from mtg.deck import Deck
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError, throttle, timed_request

_log = logging.getLogger(__name__)


HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Authorization": "Bearer undefined",
    "Cookie": "_ga=GA1.1.1202643745.1722108358; "
              "ncmp.domain=moxfield.com; _ga_BW2XPQDNK2=GS1.1.1722108357.1.1.1722108385.0.0.0",
    "Origin": "https://www.moxfield.com",
    "Priority": "u=1, i",
    "Referer": "https://www.moxfield.com/",
    "Sec-Ch-Ua": "\"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Google Chrome\";v=\"126\"",
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": "\"Linux\"",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0.0.0 Safari/537.36",
    "X-Moxfield-Version": "2024.07.26.5",
}


@DeckScraper.registered
class MoxfieldScraper(DeckScraper):
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
        return "moxfield.com/decks/" in url and "/personal" not in url and "/history" not in url

    def _pre_parse(self) -> None:  # override
        self._json_data = timed_request(
            self.API_URL_TEMPLATE.format(self._decklist_id), return_json=True, headers=HEADERS)
        if not self._json_data:
            raise ScrapingError("Data not available")

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = DeckScraper.sanitize_url(url)
        if url.endswith("/primer"):
            return url.removesuffix("/primer")
        elif url.endswith("/primer/"):
            return url.removesuffix("/primer/")
        if url.endswith("/"):
            return url.removesuffix("/")
        return url

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

    def _parse_deck(self) -> None:  # override
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


class MoxfieldBookmarkScraper:
    """Scraper of Moxfield bookmark page.
    """
    API_URL_TEMPLATE = "https://api2.moxfield.com/v1/bookmarks/{}"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        if not self.is_bookmark_url(url):
            raise ValueError(f"Not a Moxfield bookmark URL: {url!r}")
        self._url, self._metadata = url, metadata

    @staticmethod
    def is_bookmark_url(url: str) -> bool:
        return "moxfield.com/bookmarks/" in url

    def _get_bookmark_id(self) -> str:
        *_, last = self._url.split("/")
        if "-" in last:
            id_, *_ = last.split("-")
            return id_
        return last

    def scrape(self, *already_scraped_deck_urls: str) -> list[Deck]:
        throttle(*DeckScraper.THROTTLING)
        json_data = timed_request(
            self.API_URL_TEMPLATE.format(self._get_bookmark_id()), return_json=True,
            headers=HEADERS)
        deck_urls = [d["deck"]["publicUrl"] for d in json_data["decks"]["data"]]
        _log.info(
            f"Gathered {len(deck_urls)} deck URL(s) from a Moxfield bookmark at: {self._url!r}")
        for url in deck_urls:
            if url in already_scraped_deck_urls:
                _log.info(f"Skipping already scraped deck URL: {url!r}")
                deck_urls.remove(url)
        return [MoxfieldScraper(url, self._metadata).scrape(throttled=True) for url in deck_urls]
