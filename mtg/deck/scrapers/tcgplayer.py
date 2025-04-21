"""

    mtg.deck.scrapers.tcgplayer.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TCG Player decklists.

    @author: z33k

"""
import json
import logging
from datetime import datetime
from typing import Type, override

import dateutil.parser
from bs4 import BeautifulSoup, Tag
from httpcore import ReadTimeout
from requests import HTTPError
from selenium.common import TimeoutException

from mtg import Json
from mtg.deck import Deck
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper, DecksJsonContainerScraper, \
    HybridContainerScraper, JsonBasedDeckParser
from mtg.scryfall import Card
from mtg.utils import extract_int
from mtg.utils.scrape import ScrapingError, getsoup, request_json, strip_url_query, throttle
from mtg.utils.scrape.dynamic import SCROLL_DOWN_TIMES, get_dynamic_soup

_log = logging.getLogger(__name__)


def get_source(src: str) -> str | None:
    if ".tcgplayer.com" in src:
        _, *parts = src.split(".")
        return ".".join(parts)
    return None


@DeckScraper.registered
class TcgPlayerDeckScraper(DeckScraper):
    """Scraper of TCG Player (old-site) decklist page.
    """
    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "decks.tcgplayer.com/" in url.lower() and "/search" not in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available", scraper=type(self))

    @override
    def _parse_metadata(self) -> None:
        info_tag = self._soup.find("div", class_="viewDeckHeader")
        h1_tag = info_tag.find("h1")
        self._metadata["name"] = h1_tag.find("a").text.strip()
        h3_tag = info_tag.find("h3")
        self._metadata["author"] = h3_tag.text.strip().removeprefix("by ")
        for sub_tag in info_tag.find_all("div"):
            if "Format:" in sub_tag.text:
                fmt = sub_tag.find("a").text.strip().lower()
                self._update_fmt(fmt)
            elif "Last Modified On:" in sub_tag.text:
                _, date_text = sub_tag.text.strip().split("On: ", maxsplit=1)
                self._metadata["date"] = datetime.strptime(date_text, "%m/%d/%Y").date()

    @classmethod
    def _process_deck_tag(cls, deck_tag: Tag) -> list[Card]:
        cards = []
        card_tags = deck_tag.find_all("a", class_="subdeck-group__card")
        for card_tag in card_tags:
            quantity_tag, name_tag = card_tag.find_all("span")
            quantity = extract_int(quantity_tag.text)
            cards += cls.get_playset(cls.find_card(name_tag.text.strip()), quantity)
        return cards

    @override
    def _parse_decklist(self) -> None:
        deck_tags = self._soup.find_all("div", class_="subdeck")
        for deck_tag in deck_tags:
            if deck_tag.find("h3").text.lower().startswith("command"):
                cards = self._process_deck_tag(deck_tag)
                for card in cards:
                    self._set_commander(card)
            elif deck_tag.find("h3").text.lower().startswith("sideboard"):
                self._sideboard = self._process_deck_tag(deck_tag)
            else:
                self._maindeck = self._process_deck_tag(deck_tag)


@DeckUrlsContainerScraper.registered
class TcgPlayerPlayerScraper(DeckUrlsContainerScraper):
    """Scraper of TCG Player (old-site) player search page.
    """
    CONTAINER_NAME = "TCGPlayer (old-site) player"  # override
    DECK_SCRAPERS = TcgPlayerDeckScraper,  # override
    DECK_URL_PREFIX = "https://decks.tcgplayer.com"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return ("decks.tcgplayer.com/magic/deck/search?" in url.lower()
                and"player=" in url)

    @override
    def _collect(self) -> list[str]:
        deck_tags = self._soup.find_all(
            "a", href=lambda h: h and "/magic/" in h and "/magic/deck" not in h)
        return [deck_tag.attrs["href"] for deck_tag in deck_tags]


# INFINITE ########################################################################################
INFINITE_URL_PREFIX = "https://infinite.tcgplayer.com"


class TcgPlyerInfiniteDeckJsonParser(JsonBasedDeckParser):
    """Parser of an TCG Player Infinite deck JSON.
    """
    @override
    def _parse_metadata(self) -> None:
        self._metadata["name"] = self._deck_data["deck"]["name"]
        self._update_fmt(self._deck_data["deck"]["format"])
        self._metadata["author"] = self._deck_data["deck"]["playerName"]
        if date_text := self._deck_data["deck"]["created"]:
            try:
                self._metadata["date"] = dateutil.parser.parse(date_text).date()
            except dateutil.parser.ParserError:
                pass
        if event_name := self._deck_data["deck"].get("eventName"):
            self._metadata["event"] = {}
            self._metadata["event"]["name"] = event_name
            if event_date := self._deck_data["deck"].get("eventDate"):
                self._metadata["event"]["date"] = dateutil.parser.parse(event_date).date()
            if event_level := self._deck_data["deck"].get("eventLevel"):
                self._metadata["event"]["level"] = event_level
            self._metadata["event"]["draws"] = self._deck_data["deck"]["eventDraws"]
            self._metadata["event"]["losses"] = self._deck_data["deck"]["eventLosses"]
            self._metadata["event"]["wins"] = self._deck_data["deck"]["eventWins"]
            self._metadata["event"]["placement_max"] = self._deck_data["deck"]["eventPlacementMax"]
            self._metadata["event"]["placement_min"] = self._deck_data["deck"]["eventPlacementMin"]
            if event_players := self._deck_data["deck"].get("eventPlayers"):
                self._metadata["event"]["players"] = event_players
            if event_rank := self._deck_data["deck"].get("eventRank"):
                self._metadata["event"]["rank"] = event_rank

    def _get_cardmap(self) -> dict[int, Card]:
        cardmap = {}
        for card_id, data in self._deck_data["cards"].items():
            name, tcgplayer_id, oracle_id = data["name"], data["tcgPlayerID"], data["oracleID"]
            card = self.find_card(name, tcgplayer_id=tcgplayer_id, oracle_id=oracle_id)
            cardmap[int(card_id)] = card
        return cardmap

    @override
    def _parse_decklist(self) -> None:
        cardmap = self._get_cardmap()
        sub_decks = self._deck_data["deck"]["subDecks"]
        if command_zone := sub_decks.get("commandzone"):
            for item in command_zone:
                try:
                    card_id, quantity = item["cardID"], item["quantity"]
                    self._set_commander(self.get_playset(cardmap[card_id], quantity)[0])
                except KeyError:
                    pass

        for item in sub_decks["maindeck"]:
            try:
                card_id, quantity = item["cardID"], item["quantity"]
                self._maindeck += self.get_playset(cardmap[card_id], quantity)
            except KeyError:
                pass

        if sideboard := sub_decks.get("sideboard"):
            for item in sideboard:
                try:
                    card_id, quantity = item["cardID"], item["quantity"]
                    self._sideboard += self.get_playset(cardmap[card_id], quantity)
                except KeyError:
                    pass


def _get_deck_data_from_api(
        url: str, api_url_template: str,
        scraper: Type[DeckScraper] | Type[DecksJsonContainerScraper]) -> Json:
    *_, decklist_id = url.split("/")
    json_data, tries = {}, 0
    try:
        json_data = request_json(api_url_template.format(decklist_id), handle_http_errors=False)
        tries += 1
    except HTTPError as e:
        if "404 Not Found" in str(e):
            api_url_template += "&external=true"
            json_data = request_json(api_url_template.format(decklist_id))
            tries += 1
    except ReadTimeout:
        raise ScrapingError("Request timed out", scraper=scraper)

    if not json_data and tries < 2:
        throttle(*DeckScraper.THROTTLING)
        api_url_template += "&external=true"
        json_data = request_json(api_url_template.format(decklist_id))

    if not json_data or not json_data.get(
            "result") or json_data["result"].get("deck") == {"deck": {}}:
        raise ScrapingError("Data not available", scraper=scraper)
    return json_data["result"]


@DeckScraper.registered
class TcgPlayerInfiniteDeckScraper(DeckScraper):
    """Scraper of TCG Player Infinite decklist page.
    """
    API_URL_TEMPLATE = ("https://infinite-api.tcgplayer.com/deck/magic/{}/?source=infinite-"
                        "content&subDecks=true&cards=true&stats=true")

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_parser: TcgPlyerInfiniteDeckJsonParser | None = None

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "infinite.tcgplayer.com/magic-the-gathering/deck/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        deck_data = _get_deck_data_from_api(self.url, self.API_URL_TEMPLATE, scraper=type(self))
        self._deck_parser = TcgPlyerInfiniteDeckJsonParser(deck_data, self._metadata)

    @override
    def _parse_metadata(self) -> None:
        pass

    @override
    def _parse_decklist(self) -> None:
        pass

    @override
    def _build_deck(self) -> Deck:
        return self._deck_parser.parse()


@DeckUrlsContainerScraper.registered
class TcgPlayerInfinitePlayerScraper(DeckUrlsContainerScraper):
    """Scraper of TCG Player new-site player page.
    """
    CONTAINER_NAME = "TCGPlayer Infinite player"  # override
    # 100 rows is pretty arbitrary but tested to work
    API_URL_TEMPLATE = ("https://infinite-api.tcgplayer.com/content/decks/magic?source=infinite"
                        "-content&rows=100&format=&playerName"
                        "={}&latest=true&sort=created&order=desc")
    DECK_SCRAPERS = TcgPlayerInfiniteDeckScraper,  # override
    DECK_URL_PREFIX = INFINITE_URL_PREFIX  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "infinite.tcgplayer.com/magic-the-gathering/decks/player/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    def _get_player_name(self) -> str:
        *_, last = self.url.split("/")
        return last

    @override
    def _collect(self) -> list[str]:
        json_data = request_json(self.API_URL_TEMPLATE.format(self._get_player_name()))
        if not json_data or not json_data.get("result"):
            _log.warning(self._error_msg)
            return []
        return [d["canonicalURL"] for d in json_data["result"]]


@DeckUrlsContainerScraper.registered
class TcgPlayerInfiniteAuthorSearchScraper(TcgPlayerInfinitePlayerScraper):
    """Scraper of TCG Player Infinite author search page.
    """
    CONTAINER_NAME = "TCGPlayer Infinite author search"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return ("infinite.tcgplayer.com/magic-the-gathering/decks/advanced-search" in url.lower()
                and "author=" in url.lower())

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return url.removesuffix("/")

    @override
    def _get_player_name(self) -> str:
        *_, author = self.url.split("author=")
        if "&" in author:
            author, *_ = author.split("&")
        return author


@DeckUrlsContainerScraper.registered
class TcgPlayerInfiniteEventScraper(DeckUrlsContainerScraper):
    """Scraper of TCG Player Infinite event page.
    """
    CONTAINER_NAME = "TCGPlayer Infinite event"  # override
    # 200 rows is pretty arbitrary but tested to work (even though usually events have fewer rows)
    API_URL_TEMPLATE = ("https://infinite-api.tcgplayer.com/content/decks/magic?source="
                        "infinite-content&rows=200&eventNames={}")  # override
    DECK_SCRAPERS = TcgPlayerInfiniteDeckScraper,  # override
    DECK_URL_PREFIX = INFINITE_URL_PREFIX  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "infinite.tcgplayer.com/magic-the-gathering/events/event/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    def _get_event_name(self) -> str:
        *_, last = self.url.split("/")
        return last

    @override
    def _collect(self) -> list[str]:
        json_data = request_json(self.API_URL_TEMPLATE.format(self._get_event_name()))
        if not json_data or not json_data.get("result"):
            _log.warning(self._error_msg)
            return []
        return [d["canonicalURL"] for d in json_data["result"]]


@DecksJsonContainerScraper.registered
class TcgPlayerInfiniteArticleScraper(DecksJsonContainerScraper):
    """Scraper of TCG Player Infinite article page.
    """
    CONTAINER_NAME = "TCGPlayer Infinite article"  # override
    _HOOK = "/magic-the-gathering/deck/"
    XPATH = f"//a[contains(@href, '{_HOOK}')]"  # override
    CONSENT_XPATH = ("//button[contains(@class, 'martech-button') and contains(@class, "
                     "'martech-medium') and contains(@class, 'martech-primary')]")  # override
    API_URL_TEMPLATE = TcgPlayerInfiniteDeckScraper.API_URL_TEMPLATE  # override
    JSON_BASED_DECK_PARSER = TcgPlyerInfiniteDeckJsonParser  # override

    @property
    def _scroll_down_times(self) -> int:
        doubled = False
        tokens = "-decks", "-ranking", "-rankings"
        if any(t in self.url.lower() for t in tokens):
            doubled = True
        if any(t in self.url.lower() for t in ("top-", "best-")) and "-deck" in self.url.lower():
            doubled = True
        return 3 * SCROLL_DOWN_TIMES if doubled else SCROLL_DOWN_TIMES

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return f"infinite.tcgplayer.com/article/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _collect(self) -> list[Json]:
        try:
            self._soup, _, _ = get_dynamic_soup(
                self.url, self.XPATH, consent_xpath=self.CONSENT_XPATH, scroll_down=True,
                wait_for_all=True, scroll_down_times=self._scroll_down_times, scroll_down_delay=2.0,
                timeout=5.0)
            if not self._soup:
                _log.warning(self._error_msg)
                return []
        except TimeoutException:
            return []

        div_tag = self._soup.find("div", class_="article-body")
        deck_urls = [
            strip_url_query(t.attrs["href"]) for t in div_tag.find_all(
                "a", href=lambda h: h and h.startswith(self._HOOK))]

        decks_data = []
        for url in deck_urls:
            try:
                decks_data.append(
                    _get_deck_data_from_api(url, self.API_URL_TEMPLATE, scraper=type(self)))
            except ScrapingError as err:
                _log.warning(f"{url!r} failed with: {err!r}")
                continue
            throttle(*DeckScraper.THROTTLING)
        return decks_data


@HybridContainerScraper.registered
class TcgPlayerInfiniteAuthorScraper(HybridContainerScraper):
    """Scraper of TCG Player Infinite author page.
    """
    CONTAINER_NAME = "TCGPlayer Infinite author"  # override
    XPATH = "//div[@class='grid']"  # override
    CONSENT_XPATH = TcgPlayerInfiniteArticleScraper.CONSENT_XPATH  # override
    AUTHOR_API_URL_TEMPLATE = ("https://infinite-api.tcgplayer.com/content/author/{}/?source="
                               "infinite-content&rows=48&game=&format=")
    CONTAINER_SCRAPERS = TcgPlayerInfiniteArticleScraper,  # override
    CONTAINER_URL_PREFIX = INFINITE_URL_PREFIX

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._author_id = None

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "infinite.tcgplayer.com/author/" in url.lower() and not url.lower().endswith(
            "/decks")

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @staticmethod
    def get_author_id(soup: BeautifulSoup) -> str | None:
        script_tag = soup.find(
            "script", string=lambda s: s and 'identifier' in s and 'description' in s)
        if script_tag is None:
            return None
        try:
            data = json.loads(script_tag.text)
            return data.get("mainEntity", {}).get("identifier")
        except json.decoder.JSONDecodeError:
            return None

    def _get_links_from_json(self) -> list[str]:
        json_data = request_json(self.AUTHOR_API_URL_TEMPLATE.format(self._author_id))
        if not json_data or not json_data.get("result"):
            return []
        return [d["canonicalURL"] for d in json_data["result"]["articles"]]

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        self._author_id = self.get_author_id(self._soup)
        if self._author_id is None:
            _log.warning("Author ID not available")
            return [], [], [], []

        return [], [], [], self._get_links_from_json()


@DeckUrlsContainerScraper.registered
class TcgPlayerInfiniteAuthorDecksPaneScraper(DeckUrlsContainerScraper):
    """Scraper of TCG Player Infinite author decks page.
    """
    CONTAINER_NAME = "TCGPlayer Infinite author decks pane"  # override
    XPATH = TcgPlayerInfiniteAuthorScraper.XPATH
    CONSENT_XPATH = TcgPlayerInfiniteArticleScraper.CONSENT_XPATH
    # 200 rows is pretty arbitrary but tested to work (even though usually events have fewer rows)
    DECKS_PANE_API_URL_TEMPLATE = ("https://infinite-api.tcgplayer.com/content/decks/?source"
                                   "=infinite-content&rows=2008&authorID={}&latest=true&sort="
                                   "created&order=desc")
    DECK_SCRAPERS = TcgPlayerInfiniteDeckScraper,  # override
    DECK_URL_PREFIX = INFINITE_URL_PREFIX  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "infinite.tcgplayer.com/author/" in url.lower() and url.lower().endswith("/decks")

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _collect(self) -> list[str]:
        author_id = TcgPlayerInfiniteAuthorScraper.get_author_id(self._soup)
        if author_id is None:
            _log.warning("Author ID not available")
            return []
        json_data = request_json(self.DECKS_PANE_API_URL_TEMPLATE.format(author_id))
        if not json_data or not json_data.get("result"):
            _log.warning(self._error_msg)
            return []
        return [d["canonicalURL"] for d in json_data["result"]]
