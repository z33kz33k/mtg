"""

    mtg.deck.scrapers.deckstats.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Deckstats decklists.

    @author: z33k

"""
import itertools
import logging
from datetime import UTC, datetime
from typing import override

import backoff
from bs4 import BeautifulSoup
from requests import Response

from mtg import Json
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError, dissect_js, request_json, strip_url_query, \
    throttle, timed_request

_log = logging.getLogger(__name__)


_FORMATS = {
    2: "vintage",
    3: "legacy",
    4: "modern",
    6: "standard",
    9: "pauper",
    10: "commander",
    15: "penny",
    16: "brawl",
    17: "oathbreaker",
    18: "pioneer",
    19: "historic",
    21: "duel",
    22: "explorer",
}


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
class DeckstatsDeckScraper(DeckScraper):
    """Scraper of Deckstats decklist page.
    """
    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        if "deckstats.net/decks/" not in url.lower():
            return False
        url = strip_url_query(url)
        url = url.removeprefix("https://").removeprefix("http://")
        if url.count("/") == 3:
            domain, _, user_id, deck_id = url.split("/")
            if all(ch.isdigit() for ch in user_id) and "-" in deck_id:
                return True
        return False

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

    def _get_deck_data(self) -> Json:
        return dissect_js(
            self._soup, "init_deck_data(", "deck_display();", lambda s: s.removesuffix(", false);"))

    @override
    def _pre_parse(self) -> None:
        response = self._get_response()
        if response.status_code == 429:
            raise ScrapingError(f"Page still not available after {_MAX_TRIES} backoff tries")
        self._soup = BeautifulSoup(response.text, "lxml")
        if error_tag := self._soup.find("div", class_="ui-state-error"):
            if "This deck does not exist." in error_tag.text:
                raise ScrapingError("Deck does not exist")
            elif "You do not have access to this page." in error_tag.text:
                raise ScrapingError("Access to deck page denied (is the deck private perhaps?)")
        self._deck_data = self._get_deck_data()

    @override
    def _parse_metadata(self) -> None:
        author_text = self._soup.find("div", id="deck_folder_subtitle").text.strip()
        self._metadata["author"] = author_text.removeprefix("in  ").removesuffix("'s Decks")
        self._metadata["name"] = self._deck_data["name"]
        self._metadata["views"] = self._deck_data["views"]
        if self._deck_data.get("format_id"):
            fmt = _FORMATS.get(self._deck_data["format_id"])
            if fmt:
                self._update_fmt(fmt)
        self._metadata["date"] = datetime.fromtimestamp(self._deck_data["updated"], UTC).date()
        if tags := self._deck_data.get("tags"):
            self._metadata["tags"] = self.process_metadata_deck_tags(tags)
        if description := self._deck_data.get("description"):
            self._metadata["description"] = description

    def _parse_card_json(self, card_json: Json) -> list[Card]:
        name = card_json["name"]
        quantity = card_json["amount"]
        if not card_json.get("data"):
            raise ScrapingError(f"No card data available for playset '{quantity} {name}'")
        if tcgplayer_id := card_json["data"].get("price_tcgplayer_id"):
            tcgplayer_id = int(tcgplayer_id)
        if mtgo_id := card_json["data"].get("price_cardhoarder_id"):
            mtgo_id = int(mtgo_id)
        card = self.find_card(name, tcgplayer_id=tcgplayer_id, mtgo_id=mtgo_id)
        if card_json.get("isCommander"):
            self._set_commander(card)
        return self.get_playset(card, quantity)

    @override
    def _parse_decklist(self) -> None:
        cards = itertools.chain(
            *[section["cards"] for section in self._deck_data["sections"]])
        for card_json in cards:
            self._maindeck.extend(self._parse_card_json(card_json))
        if sideboard := self._deck_data.get("sideboard"):
            for card_json in sideboard:
                self._sideboard.extend(self._parse_card_json(card_json))


@DeckUrlsContainerScraper.registered
class DeckstatsUserScraper(DeckUrlsContainerScraper):
    """Scraper of Deckstats user page.
    """
    THROTTLING = DeckUrlsContainerScraper.THROTTLING * 1.33  # override
    CONTAINER_NAME = "Deckstats user"  # override
    API_URL_TEMPLATE = ("https://deckstats.net/api.php?action=user_folder_get&result_type="
                        "folder%3Bdecks%3Bparent_tree%3Bsubfolders&owner_id={}&folder_id=0&"
                        "decks_page={}")  # override
    DECK_SCRAPERS = DeckstatsDeckScraper,  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        if "deckstats.net/decks/" not in url.lower():
            return False
        url = strip_url_query(url)
        url = url.removeprefix("https://").removeprefix("http://")
        if url.count("/") != 2:
            return False
        domain, _, user_id = url.split("/")
        if all(ch.isdigit() for ch in user_id):
            return True
        return False

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    def _get_user_id(self) -> str:
        url = self.url.removeprefix("https://").removeprefix("http://")
        *_, user_id = url.split("/")
        return user_id

    @override
    def _collect(self) -> list[str]:
        user_id = self._get_user_id()
        collected, total, page = [], 1, 1
        last_seen = None
        while len(collected) < total:
            if page != 1:
                throttle(*self.THROTTLING)
            json_data = request_json(self.API_URL_TEMPLATE.format(user_id, page))
            if collected and last_seen == json_data:
                break
            if not json_data or not json_data.get("folder") or not json_data["folder"].get("decks"):
                if not collected:
                    _log.warning(self._error_msg)
                break
            total = json_data["folder"]["decks_total"]
            collected += [f'https:{d["url_neutral"]}' for d in json_data["folder"]["decks"]]
            page += 1
            last_seen = json_data
        return collected

