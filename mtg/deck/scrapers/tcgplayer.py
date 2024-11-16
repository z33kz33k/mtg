"""

    mtg.deck.scrapers.tcgplayer.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TCG Player decklists.

    @author: z33k

"""
import logging
from datetime import datetime

import dateutil.parser
from bs4 import Tag
from httpcore import ReadTimeout

from mtg import Json
from mtg.deck.scrapers import ContainerScraper, DeckScraper
from mtg.scryfall import Card
from mtg.utils import extract_int
from mtg.utils.scrape import ScrapingError, getsoup, request_json, strip_url_params

_log = logging.getLogger(__name__)


@DeckScraper.registered
class OldSiteTcgPlayerScraper(DeckScraper):
    """Scraper of TCG Player old-site decklist page.
    """
    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "decks.tcgplayer.com/" in url.lower() and "/search" not in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url, with_endpoint=False)

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
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

    def _parse_deck(self) -> None:  # override
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


@ContainerScraper.registered
class OldSiteTcgPlayerUserScraper(ContainerScraper):
    """Scraper of TCG Player old-site user search page.
    """
    CONTAINER_NAME = "TCGPlayer (old-site) user"  # override
    DECK_URL_TEMPLATE = "https://decks.tcgplayer.com{}"
    _DECK_SCRAPER = OldSiteTcgPlayerScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return ("https://decks.tcgplayer.com/magic/deck/search?" in url.lower()
                and"player=" in url)

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning("User search data not available")
            return []

        deck_tags = self._soup.find_all(
            "a", href=lambda h: h and "/magic/" in h and "/magic/deck" not in h)
        return [self.DECK_URL_TEMPLATE.format(deck_tag.attrs["href"]) for deck_tag in deck_tags]


@DeckScraper.registered
class NewSiteTcgPlayerScraper(DeckScraper):
    """Scraper of TCG Player new-site decklist page.
    """
    API_URL_TEMPLATE = ("https://infinite-api.tcgplayer.com/deck/magic/{}/?source=infinite-"
                        "content&subDecks=true&cards=true&stats=true")

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        *_, self._decklist_id = self.url.split("/")
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "infinite.tcgplayer.com/magic-the-gathering/deck/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url)

    def _pre_parse(self) -> None:  # override
        try:
            json_data = request_json(self.API_URL_TEMPLATE.format(self._decklist_id))
        except ReadTimeout:
            raise ScrapingError("Request timed out")
        if not json_data or not json_data.get(
                "result") or json_data["result"].get("deck") == {"deck": {}}:
            raise ScrapingError("Data not available")
        self._json_data = json_data["result"]

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._json_data["deck"]["name"]
        self._update_fmt(self._json_data["deck"]["format"])
        self._metadata["author"] = self._json_data["deck"]["playerName"]
        self._metadata["date"] = dateutil.parser.parse(self._json_data["deck"]["created"]).date()
        if event_name := self._json_data["deck"].get("eventName"):
            self._metadata["event"] = {}
            self._metadata["event"]["name"] = event_name
            if event_date := self._json_data["deck"].get("eventDate"):
                self._metadata["event"]["date"] = dateutil.parser.parse(event_date).date()
            if event_level := self._json_data["deck"].get("eventLevel"):
                self._metadata["event"]["level"] = event_level
            self._metadata["event"]["draws"] = self._json_data["deck"]["eventDraws"]
            self._metadata["event"]["losses"] = self._json_data["deck"]["eventLosses"]
            self._metadata["event"]["wins"] = self._json_data["deck"]["eventWins"]
            self._metadata["event"]["placement_max"] = self._json_data["deck"]["eventPlacementMax"]
            self._metadata["event"]["placement_min"] = self._json_data["deck"]["eventPlacementMin"]
            if event_players := self._json_data["deck"].get("eventPlayers"):
                self._metadata["event"]["players"] = event_players
            if event_rank := self._json_data["deck"].get("eventRank"):
                self._metadata["event"]["rank"] = event_rank

    def _get_cardmap(self) -> dict[int, Card]:
        cardmap = {}
        for card_id, data in self._json_data["cards"].items():
            name, tcgplayer_id, oracle_id = data["name"], data["tcgPlayerID"], data["oracleID"]
            card = self.find_card(name, tcgplayer_id=tcgplayer_id, oracle_id=oracle_id)
            cardmap[int(card_id)] = card
        return cardmap

    def _parse_deck(self) -> None:  # override
        cardmap = self._get_cardmap()
        sub_decks = self._json_data["deck"]["subDecks"]
        if command_zone := sub_decks.get("commandzone"):
            for item in command_zone:
                card_id, quantity = item["cardID"], item["quantity"]
                self._set_commander(self.get_playset(cardmap[card_id], quantity)[0])

        for item in sub_decks["maindeck"]:
            card_id, quantity = item["cardID"], item["quantity"]
            self._maindeck += self.get_playset(cardmap[card_id], quantity)

        if sideboard := sub_decks.get("sideboard"):
            for item in sideboard:
                card_id, quantity = item["cardID"], item["quantity"]
                self._sideboard += self.get_playset(cardmap[card_id], quantity)


@ContainerScraper.registered
class NewSiteTcgPlayerUserScraper(ContainerScraper):
    """Scraper of TCG Player new-site user page.
    """
    CONTAINER_NAME = "TCGPlayer (new-site) user"  # override
    # 100 rows is pretty arbitrary but tested to work
    API_URL_TEMPLATE = ("https://infinite-api.tcgplayer.com/content/decks/magic?source=infinite"
                        "-content&rows=100&format=&playerName"
                        "={}&latest=true&sort=created&order=desc")
    DECK_URL_TEMPLATE = "https://infinite.tcgplayer.com{}"
    _DECK_SCRAPER = NewSiteTcgPlayerScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "infinite.tcgplayer.com/magic-the-gathering/decks/player/" in url.lower()

    def _get_user_name(self) -> str:
        *_, last = self.url.split("/")
        return last

    def _collect(self) -> list[str]:  # override
        json_data = request_json(
            self.API_URL_TEMPLATE.format(self._get_user_name()))
        if not json_data or not json_data.get("result"):
            _log.warning("User data not available")
            return []
        return [self.DECK_URL_TEMPLATE.format( d["canonicalURL"]) for d in json_data["result"]]


@ContainerScraper.registered
class NewSiteTcgPlayerUserSearchScraper(NewSiteTcgPlayerUserScraper):
    """Scraper of TCG Player new-site user search page.
    """
    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return ("infinite.tcgplayer.com/magic-the-gathering/decks/advanced-search" in url.lower()
                and "author=" in url.lower())

    def _get_user_name(self) -> str:  # override
        *_, user = self.url.split("author=")
        if "&" in user:
            user, *_ = user.split("&")
        return user
