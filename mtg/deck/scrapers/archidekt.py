"""

    mtg.deck.scrapers.archidekt.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Archidekt decklists.

    @author: z33k

"""
import json
import logging
from datetime import datetime

from bs4 import BeautifulSoup

from mtg import Json
from mtg.deck.scrapers import ContainerScraper, DeckScraper
from mtg.utils.scrape import ScrapingError, getsoup

_log = logging.getLogger(__name__)


@DeckScraper.registered
class ArchidektScraper(DeckScraper):
    """Scraper of Archidekt decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "archidekt.com/decks/" in url

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        json_data = json.loads(self._soup.find("script", id="__NEXT_DATA__").text)
        self._deck_data = json_data["props"]["pageProps"]["redux"]["deck"]

    def _parse_metadata(self) -> None:  # override
        fmt_tag = self._soup.find("div", class_=lambda c: c and "deckHeader_format" in c)
        if fmt_tag:
            fmt_text = fmt_tag.text
            suffix = fmt_tag.find("div").text
            fmt = fmt_text.removesuffix(suffix).strip().lower()
            if "/" in fmt:
                fmt, *_ = fmt.split("/")
            self._update_fmt(fmt.strip())
        self._metadata["name"] = self._deck_data["name"]
        self._metadata["author"] = self._deck_data["owner"]
        self._metadata["views"] = self._deck_data["viewCount"]
        date_text = self._deck_data["updatedAt"].replace("Z", "+00:00")
        self._metadata["date"] = datetime.fromisoformat(date_text).date()

    def _parse_card_json(self, card_json: Json) -> None:
        name = card_json["name"]
        quantity = card_json["qty"]
        set_code = card_json["setCode"]
        collector_number = card_json["collectorNumber"]
        categories = card_json["categories"]
        card = self.find_card(name, (set_code, collector_number))
        playset = self.get_playset(card, quantity)
        if "Commander" in categories:
            self._set_commander(card)
        elif "Sideboard" in categories:
            self._sideboard.extend(playset)
        else:
            self._maindeck.extend(playset)

    def _parse_deck(self) -> None:  # override
        for v in self._deck_data["cardMap"].values():
            self._parse_card_json(v)


@ContainerScraper.registered
class ArchidektFolderScraper(ContainerScraper):
    """Scraper of Archidekt folder page.
    """
    CONTAINER_NAME = "Archidekt folder"  # override
    URL_TEMPLATE = "https://archidekt.com{}"
    _DECK_SCRAPER = ArchidektScraper  #

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "archidekt.com/folders/" in url

    def _collect(self) -> list[str]:
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning("Folder data not available")
            return []

        deck_urls = []
        for a_tag in self._soup.select("a[class*='deck_link__']"):
            deck_urls.append(a_tag.attrs["href"])
        return [self.URL_TEMPLATE.format(url) for url in deck_urls]
