"""

    mtgcards.decks.streamdecker.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Streamdecker decklist page.

    @author: z33k

"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from mtgcards.const import Json
from mtgcards.decks import Deck, InvalidDeckError, UrlDeckParser
from mtgcards.scryfall import find_by_id, find_by_name
from mtgcards.utils.scrape import ScrapingError, timed_request


class StreamdeckerParser(UrlDeckParser):
    """Parser of Streamdecker deck page.
    """
    API_URL_TEMPLATE = "https://www.streamdecker.com/api/deck/{}"

    def __init__(self, url: str, fmt="standard", author="") -> None:
        super().__init__(url, fmt, author)
        *_, self._decklist_id = url.split("/")
        self._json_data = timed_request(
            self.API_URL_TEMPLATE.format(self._decklist_id), return_json=True)["data"]
        self._metadata = self._get_metadata()
        self._mainboard, self._sideboard, self._commander, self._companion = [], [], None, None
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:
        return "streamdecker.com/deck/" in url

    def _parse_date(self) -> date | None:
        date_text = self._json_data["updatedAt"].removesuffix(" ago")
        amount, time = date_text.split()
        amount = int(amount)
        dt = date.today()
        if time in ("days", "day"):
            return dt - timedelta(days=amount)
        elif time in ("months", "month"):
            return dt - relativedelta(months=amount)
        elif time in ("years", "year"):
            return date(dt.year - amount, dt.month, dt.day)
        return None

    def _get_metadata(self) -> Json:
        metadata = {
            "source": "www.streamdecker.com",
            "name": self._json_data["name"],
            "views": self._json_data["views"]["counter"]
        }
        if not self._author:
            metadata["author"] = self._json_data["userProfile"]["displayName"]
            metadata["author_twitch_id"] = self._json_data["userProfile"]["twitchId"]
        if self._fmt:
            metadata["format"] = self._fmt
        dt = self._parse_date()
        if dt:
            metadata["date"] = dt
        return metadata

    def _parse_card(self, json_card: Json) -> None:
        scryfall_id = json_card["scryfallId"]
        name = json_card["name"]
        card = find_by_id(scryfall_id)
        if not card:
            card = find_by_name(name)
            if not card:
                raise ScrapingError(f"{name!r} card cannot be found")
        if json_card["main"]:
            self._mainboard.extend([card] * json_card["main"])
        if json_card["sideboard"]:
            self._sideboard.extend([card] * json_card["sideboard"])
        if json_card["commander"]:
            self._commander.extend([card] * json_card["commander"])
        if json_card["companion"]:
            self._companion.extend([card] * json_card["companion"])

    def _get_deck(self) -> Deck | None:
        for card in self._json_data["cardList"]:
            self._parse_card(card)
        try:
            return Deck(self._mainboard, self._sideboard, self._commander, metadata=self._metadata)
        except InvalidDeckError:
            return None

