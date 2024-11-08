"""

    mtg.deck.scrapers.deckstats.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Deckstats decklists.

    @author: z33k

"""
import itertools
import logging
from datetime import datetime

from mtg import Json
from mtg.deck.scrapers import ContainerScraper, DeckScraper
from mtg.utils.scrape import ScrapingError, dissect_js, getsoup, throttle, timed_request
from mtg.scryfall import Card

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


@DeckScraper.registered
class DeckstatsScraper(DeckScraper):
    """Scraper of Deckstats decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        if not "deckstats.net/decks/" in url.lower():
            return False
        url = url.removeprefix("https://").removeprefix("http://")
        if url.count("/") == 3:
            domain, _, user_id, deck_id = url.split("/")
            if all(ch.isdigit() for ch in user_id) and "-" in deck_id:
                return True
        return False

    def _get_json(self) -> Json:
        return dissect_js(
            self._soup, "init_deck_data(", "deck_display();", lambda s: s.removesuffix(", false);"))

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._json_data = self._get_json()

    def _parse_metadata(self) -> None:  # override
        author_text = self._soup.find("div", id="deck_folder_subtitle").text.strip()
        self._metadata["author"] = author_text.removeprefix("in  ").removesuffix("'s Decks")
        self._metadata["name"] = self._json_data["name"]
        self._metadata["views"] = self._json_data["views"]
        fmt = _FORMATS.get(self._json_data["format_id"])
        if fmt:
            self._update_fmt(fmt)
        self._metadata["date"] = datetime.utcfromtimestamp(self._json_data["updated"]).date()
        if tags := self._json_data.get("tags"):
            self._metadata["tags"] = tags
        if description := self._json_data.get("description"):
            self._metadata["description"] = description

    def _parse_card_json(self, card_json: Json) -> list[Card]:
        name = card_json["name"]
        quantity = card_json["amount"]
        if tcgplayer_id := card_json["data"].get("price_tcgplayer_id"):
            tcgplayer_id = int(tcgplayer_id)
        if mtgo_id := card_json["data"].get("price_cardhoarder_id"):
            mtgo_id = int(mtgo_id)
        card = self.find_card(name, tcgplayer_id=tcgplayer_id, mtgo_id=mtgo_id)
        if card_json.get("isCommander"):
            self._set_commander(card)
        return self.get_playset(card, quantity)

    def _parse_deck(self) -> None:  # override
        cards = itertools.chain(
            *[section["cards"] for section in self._json_data["sections"]])
        for card_json in cards:
            self._maindeck.extend(self._parse_card_json(card_json))
        if sideboard := self._json_data.get("sideboard"):
            for card_json in sideboard:
                self._sideboard.extend(self._parse_card_json(card_json))


@ContainerScraper.registered
class DeckstatsUserScraper(ContainerScraper):
    """Scraper of Deckstats user page.
    """
    CONTAINER_NAME = "Deckstats user"  # override
    API_URL_TEMPLATE = ("https://deckstats.net/api.php?action=user_folder_get&result_type="
                        "folder%3Bdecks%3Bparent_tree%3Bsubfolders&owner_id={}&folder_id=0&"
                        "decks_page={}")
    _DECK_SCRAPER = DeckstatsScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        url = url.removeprefix("https://").removeprefix("http://")
        if url.count("/") != 2:
            return False
        domain, _, user_id = url.split("/")
        if all(ch.isdigit() for ch in user_id):
            return True
        return False

    def _get_user_id(self) -> str:
        url = self.url.removeprefix("https://").removeprefix("http://")
        *_, user_id = url.split("/")
        return user_id

    def _collect(self) -> list[str]:  # override
        user_id = self._get_user_id()
        collected, total, page = [], 1, 1
        last_seen = None
        while len(collected) < total:
            if page != 1:
                throttle(*DeckScraper.THROTTLING)
            json_data = timed_request(
                self.API_URL_TEMPLATE.format(user_id, page), return_json=True)
            if collected and last_seen == json_data:
                break
            if not json_data:
                if not collected:
                    _log.warning("User data not available")
                break
            total = json_data["folder"]["decks_total"]
            collected += [f'https:{d["url_neutral"]}' for d in json_data["folder"]["decks"]]
            page += 1
            last_seen = json_data
        return collected

