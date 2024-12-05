"""

    mtg.deck.scrapers.tappedout.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TappedOut decklists.

    @author: z33k

"""
import logging
from datetime import datetime

import backoff
from bs4 import BeautifulSoup
from requests import Response

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import ContainerScraper, DeckScraper
from mtg.utils import extract_int, get_date_from_ago_text
from mtg.utils.scrape import ScrapingError, getsoup, request_json, strip_url_params, \
    throttle, timed_request

_log = logging.getLogger(__name__)


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
class TappedoutScraper(DeckScraper):
    """Scraper of TappedOut decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._arena_decklist = []

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "tappedout.net/mtg-decks/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url)

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

    def _pre_parse(self) -> None:  # override
        response = self._get_response()
        if response.status_code == 429:
            raise ScrapingError(f"Page still not available after {_MAX_TRIES} backoff tries")
        self._soup = BeautifulSoup(response.text, "lxml")
        if "Page not found (404)" in self._soup.text:
            raise ScrapingError("Page not found (404)")

    def _parse_metadata(self) -> None:  # override
        fmt_tag = self._soup.select_one("a.btn.btn-success.btn-xs")
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

    def _build_deck(self) -> Deck:  # override
        return ArenaParser(self._arena_decklist, self._metadata).parse(suppress_invalid_deck=False)

    def _parse_deck(self) -> None:  # override
        lines = self._soup.find("textarea", id="mtga-textarea").text.strip().splitlines()
        _, name_line, _, _, *lines = lines
        self._arena_decklist = [*lines]
        self._metadata["name"] = name_line.removeprefix("Name ")


@ContainerScraper.registered
class TappedoutUserScraper(ContainerScraper):
    """Scraper of Tappedout user page.
    """
    CONTAINER_NAME = "Tappedout user"  # override
    API_URL_TEMPLATE = "https://tappedout.net/api/users/{}/deck-list/?p={}&o=-date_updated"
    DECK_URL_TEMPLATE = "https://tappedout.net{}"
    _DECK_SCRAPER = TappedoutScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "tappedout.net/users/" in url.lower() and "/deck-folders" not in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url)

    def _get_user_name(self) -> str:
        url = self.url.removeprefix("https://").removeprefix("http://")
        first, second, user, *_ = url.split("/")
        return user

    def _collect(self) -> list[str]:  # override
        username = self._get_user_name()
        collected, total, page = [], 1, 1
        while len(collected) < total:
            if page != 1:
                throttle(*DeckScraper.THROTTLING)
            json_data = request_json(self.API_URL_TEMPLATE.format(username, page))
            if not json_data or not json_data.get("results") or not json_data.get("total_decks"):
                if not collected:
                    _log.warning("User data not available")
                break
            total = json_data["total_decks"]
            collected += [
                self.DECK_URL_TEMPLATE.format(result["url"]) for result in json_data["results"]]
            page += 1
        return collected


@ContainerScraper.registered
class TappedoutFolderScraper(ContainerScraper):
    """Scraper of Tappedout folder page.
    """
    CONTAINER_NAME = "Tappedout folder"  # override
    API_URL_TEMPLATE = "https://tappedout.net/api/folder/{}/detail/"
    DECK_URL_TEMPLATE = "https://tappedout.net{}"
    _DECK_SCRAPER = TappedoutScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "tappedout.net/mtg-deck-folders/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url)

    def _get_folder_id(self) -> int:
        soup = getsoup(self.url)
        start_hook, end_hook = "window.django = ", ";"
        script_tag = soup.find("script", string=lambda s: s and start_hook in s and end_hook in s)
        text = script_tag.text
        *_, first = text.split(start_hook)
        second, *_ = first.split(end_hook)
        *_, third = second.split("folderId: ")
        return extract_int(third)

    def _collect(self) -> list[str]:  # override
        json_data = request_json(self.API_URL_TEMPLATE.format(self._get_folder_id()))
        if not json_data or not json_data.get("folder") or not json_data["folder"].get("decks"):
            _log.warning("Folder data not available")
            return []
        return [self.DECK_URL_TEMPLATE.format(d["url"]) for d in json_data["folder"]["decks"]]


@ContainerScraper.registered
class TappedoutUserFolderScraper(TappedoutUserScraper):
    """Scraper of Tappedout user folders page.
    """
    CONTAINER_NAME = "Tappedout user folder"  # override
    API_URL_TEMPLATE = "https://tappedout.net/api/folder/{}/list/?page_num={}"

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "tappedout.net/users/" in url.lower() and "/deck-folders" in url.lower()

    def _collect(self) -> list[str]:  # override
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
                self.DECK_URL_TEMPLATE.format(
                    d["url"]) for folder in json_data["results"] for d in folder["decks"]]
            page += 1
        return sorted(set(collected))


