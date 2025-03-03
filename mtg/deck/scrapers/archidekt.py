"""

    mtg.deck.scrapers.archidekt.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Archidekt decklists.

    @author: z33k

"""
import json
import logging
from datetime import datetime
from typing import override

from mtg import Json
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.utils.scrape import ScrapingError, get_links, getsoup, strip_url_query

_log = logging.getLogger(__name__)
URL_PREFIX = "https://archidekt.com"


@DeckScraper.registered
class ArchidektDeckScraper(DeckScraper):
    """Scraper of Archidekt decklist page.
    """
    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "archidekt.com/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        json_data = json.loads(self._soup.find("script", id="__NEXT_DATA__").text)
        self._deck_data = json_data["props"]["pageProps"]["redux"]["deck"]

    @override
    def _parse_metadata(self) -> None:
        fmt_tag = self._soup.find("div", class_=lambda c: c and "deckHeader_format" in c)
        if fmt_tag:
            fmt_text = fmt_tag.text
            suffix = fmt_tag.find("div").text if fmt_tag.find("div") else ""
            fmt = fmt_text.removesuffix(suffix).strip().lower()
            if "/" in fmt:
                fmt, *_ = fmt.split("/")
            self._update_fmt(fmt.strip())
        self._metadata["name"] = self._deck_data["name"]
        self._metadata["author"] = self._deck_data["owner"]
        self._metadata["views"] = self._deck_data["viewCount"]
        date_text = self._deck_data["updatedAt"].replace("Z", "+00:00")
        self._metadata["date"] = datetime.fromisoformat(date_text).date()
        if edh_bracket := self._deck_data.get("edhBracket"):
            self._metadata["edh_bracket"] = edh_bracket
        if tags := self._deck_data.get("deckTags"):
            self._metadata["tags"] = self.process_metadata_deck_tags(tags)

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

    @override
    def _parse_decklist(self) -> None:
        for v in self._deck_data["cardMap"].values():
            self._parse_card_json(v)


@DeckScraper.registered
class ArchidektSnapshotScraper(ArchidektDeckScraper):
    """Scraper of Archidekt snapshot decklist page.
    """
    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "archidekt.com/snapshots/" in url.lower()


@DeckUrlsContainerScraper.registered
class ArchidektFolderScraper(DeckUrlsContainerScraper):
    """Scraper of Archidekt folder page.
    """
    CONTAINER_NAME = "Archidekt folder"  # override
    DECK_SCRAPERS = ArchidektDeckScraper,  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "archidekt.com/folders/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _collect(self) -> list[str]:
        return get_links(self._soup, "a[class*='deck_link__']", URL_PREFIX)


@DeckUrlsContainerScraper.registered
class ArchidektUserScraper(DeckUrlsContainerScraper):
    """Scraper of Archidekt folder page.
    """
    CONTAINER_NAME = "Archidekt user"  # override
    DECK_SCRAPERS = ArchidektDeckScraper,  # override
    DECK_URL_PREFIX = URL_PREFIX  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        url = url.lower()
        return ("archidekt.com/u/" in url or "archidekt.com/user/" in url
                or ("archidekt.com/search/decks?" in url and "owner=" in url))

    @override
    def _collect(self) -> list[str]:
        info_tags = self._soup.find_all("div", class_="deckLink_info__ww_n5")
        return [div.find("a")["href"] for div in info_tags]
