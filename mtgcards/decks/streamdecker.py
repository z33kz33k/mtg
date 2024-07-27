"""

    mtgcards.decks.streamdecker.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Streamdecker decklist page.

    @author: z33k

"""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from mtgcards.const import Json
from mtgcards.decks import Deck, InvalidDeckError, DeckParser
from mtgcards.scryfall import Card
from mtgcards.utils.scrape import timed_request


class StreamdeckerParser(DeckParser):
    """Parser of Streamdecker deck page.
    """
    API_URL_TEMPLATE = "https://www.streamdecker.com/api/deck/{}"

    def __init__(self, url: str, fmt="standard", author="") -> None:
        super().__init__(fmt, author)
        *_, self._decklist_id = url.split("/")
        self._json_data = timed_request(
            self.API_URL_TEMPLATE.format(self._decklist_id), return_json=True)
        self._metadata = self._get_metadata()
        self._deck = self._get_deck()

    def _parse_date(self) -> date | None:
        date_text = self._json_data["updatedAt"].removesuffix(" ago")
        amount, time = date_text.split()
        amount = int(amount)
        dt = date.today()
        if time in ("days", "day"):
            return dt - timedelta(days=amount)
        elif time in ("months", "month"):
            return dt - relativedelta(months=amount)
        elif time in ("years", "years"):
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

    def _get_deck(self) -> Deck | None:
        mainboard, sideboard, commander = [], [], None
        # TODO: adapt to streamdecker JSON
        # for _, card in self._json_data["mainboard"].items():
        #     mainboard.extend(self._parse_card(card))
        # for _, card in self._json_data["sideboard"].items():
        #     sideboard.extend(self._parse_card(card))
        # if self._json_data["commanders"]:
        #     card = next(iter(self._json_data["commanders"].items()))[1]
        #     result = self._parse_card(card)
        #     if result:
        #         commander = result[0]

        try:
            return Deck(mainboard, sideboard, commander, metadata=self._metadata)
        except InvalidDeckError:
            return None

    def _parse_card(self, json_card: Json) -> list[Card]:
        # TODO: adapt to streamdecker JSON
        # quantity = json_card["quantity"]
        # set_code, name = json_card["card"]["set"], json_card["card"]["name"]
        # return self._get_playset(name, quantity, set_code)
        pass
