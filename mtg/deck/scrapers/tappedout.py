"""

    mtg.deck.scrapers.tappedout.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TappedOut decklists.

    @author: z33k

"""
import logging
from datetime import datetime
from typing import override

import backoff
from bs4 import BeautifulSoup
from requests import Response

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckUrlsContainerScraper, DeckScraper
from mtg.utils import extract_int, get_date_from_ago_text
from mtg.utils.scrape import ScrapingError, getsoup, prepend_url, request_json, strip_url_query, \
    throttle, timed_request

_log = logging.getLogger(__name__)
URL_PREFIX = "https://tappedout.net"
_MAX_TRIES = 3


def _backoff_predicate(response: Response) -> bool:
    if response.status_code == 429:
        msg = f"Request to TappedOut failed with: {response.status_code} {response.reason}"
        _log.warning(f"{msg}. Re-trying with backoff...")
        return True
    return False


def _backoff_handler(details: dict) -> None:
    _log.info("Backing off {wait:0.1f} seconds after {tries} tries...".format(**details))


@DeckScraper.registered
class TappedoutDeckScraper(DeckScraper):
    """Scraper of TappedOut decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._arena_decklist = ""

    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "tappedout.net/mtg-decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @backoff.on_predicate(
        backoff.runtime,
        predicate=_backoff_predicate,
        value=lambda r: int(r.headers.get("Retry-After") or 60),
        jitter=None,
        max_tries=_MAX_TRIES,
        on_backoff=_backoff_handler,
    )
    def _get_response(self) -> Response | None:
        return timed_request(self.url, handle_http_errors=False)

    @override
    def _pre_parse(self) -> None:
        response = self._get_response()
        if response.status_code == 429:
            raise ScrapingError(f"Page still not available after {_MAX_TRIES} backoff tries")
        self._soup = BeautifulSoup(response.text, "lxml")
        if "Page not found (404)" in self._soup.text:
            raise ScrapingError("Page not found (404)")

    @override
    def _parse_metadata(self) -> None:
        fmt_tag = self._soup.select_one("a.btn.btn-success.btn-xs")
        if fmt_tag is None:
            raise ScrapingError(f"Format tag not found: {self.url!r}")
        fmt = fmt_tag.text.strip().removesuffix("*").lower()
        self._update_fmt(fmt)
        self._metadata["author"] = self._soup.select_one('a[href*="/users/"]').text.strip()
        deck_details_table = self._soup.find("table", id="deck-details")
        for row in deck_details_table.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) != 2:
                continue
            name_col, value_col = cols
            if name_col.text.strip() == "Last updated":
                date_text = value_col.text.strip()
                if date_text == "a few seconds":
                    self._metadata["date"] = datetime.today()
                else:
                    self._metadata["date"] = get_date_from_ago_text(value_col.text.strip())
            elif name_col.text.strip() == "Views":
                if views := value_col.text.strip():
                    self._metadata["views"] = extract_int(views)

    @override
    def _parse_decklist(self) -> None:
        decklist_tag = self._soup.find("textarea", id="mtga-textarea")
        if not decklist_tag:
            raise ScrapingError("Decklist tag not found")
        lines = decklist_tag.text.strip().splitlines()
        _, name_line, _, _, *lines = lines
        self._arena_decklist = "\n".join(lines)
        self._metadata["name"] = name_line.removeprefix("Name ")

    @override
    def _build_deck(self) -> Deck:
        return ArenaParser(self._arena_decklist, self._metadata).parse(
            suppress_parsing_errors=False, suppress_invalid_deck=False)


@DeckUrlsContainerScraper.registered
class TappedoutUserScraper(DeckUrlsContainerScraper):
    """Scraper of Tappedout user page.
    """
    CONTAINER_NAME = "Tappedout user"  # override
    # override
    API_URL_TEMPLATE = "https://tappedout.net/api/users/{}/deck-list/?p={}&o=-date_updated"
    DECK_SCRAPERS = TappedoutDeckScraper,  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "tappedout.net/users/" in url.lower() and "/deck-folders" not in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    def _get_user_name(self) -> str:
        url = self.url.removeprefix("https://").removeprefix("http://")
        first, second, user, *_ = url.split("/")
        return user

    @override
    def _collect(self) -> list[str]:
        username = self._get_user_name()
        collected, total, page = [], 1, 1
        while len(collected) < total:
            if page != 1:
                throttle(*DeckScraper.THROTTLING)
            json_data = request_json(self.API_URL_TEMPLATE.format(username, page))
            if not json_data or not json_data.get("results") or not json_data.get("total_decks"):
                if not collected:
                    _log.warning(self._error_msg)
                break
            total = json_data["total_decks"]
            collected += [prepend_url(result["url"], URL_PREFIX) for result in json_data["results"]]
            page += 1
        return collected


@DeckUrlsContainerScraper.registered
class TappedoutFolderScraper(DeckUrlsContainerScraper):
    """Scraper of Tappedout folder page.
    """
    CONTAINER_NAME = "Tappedout folder"  # override
    API_URL_TEMPLATE = "https://tappedout.net/api/folder/{}/detail/"  # override
    DECK_SCRAPERS = TappedoutDeckScraper,  # override
    DECK_URL_PREFIX = URL_PREFIX  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "tappedout.net/mtg-deck-folders/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    def _get_folder_id(self) -> int:
        soup = getsoup(self.url)
        start_hook, end_hook = "window.django = ", ";"
        script_tag = soup.find("script", string=lambda s: s and start_hook in s and end_hook in s)
        text = script_tag.text
        *_, first = text.split(start_hook)
        second, *_ = first.split(end_hook)
        *_, third = second.split("folderId: ")
        return extract_int(third)

    @override
    def _collect(self) -> list[str]:
        json_data = request_json(self.API_URL_TEMPLATE.format(self._get_folder_id()))
        if not json_data or not json_data.get("folder") or not json_data["folder"].get("decks"):
            _log.warning(self._error_msg)
            return []
        return [d["url"] for d in json_data["folder"]["decks"]]


@DeckUrlsContainerScraper.registered
class TappedoutUserFolderScraper(TappedoutUserScraper):
    """Scraper of Tappedout user folders page.
    """
    CONTAINER_NAME = "Tappedout user folder"  # override
    API_URL_TEMPLATE = "https://tappedout.net/api/folder/{}/list/?page_num={}"  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "tappedout.net/users/" in url.lower() and "/deck-folders" in url.lower()

    @override
    def _collect(self) -> list[str]:
        username = self._get_user_name()
        collected, has_next, page = [], True, 1
        while has_next:
            if page != 1:
                throttle(*DeckScraper.THROTTLING)
            json_data = request_json(self.API_URL_TEMPLATE.format(username, page))
            if not json_data or not json_data.get("results"):
                if not collected:
                    _log.warning("User folder data not available")
                break
            has_next = json_data.get("hasNext", False)
            collected += [
                prepend_url(d["url"], URL_PREFIX) for folder in json_data["results"]
                for d in folder["decks"]]
            page += 1
        return sorted(set(collected))
