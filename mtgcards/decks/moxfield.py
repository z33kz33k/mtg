"""

    mtgcards.decks.moxfield.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Moxfield decklist page.

    @author: z33k

"""
from datetime import datetime

from mtgcards.const import Json
from mtgcards.decks import Deck, InvalidDeckError, DeckParser
from mtgcards.scryfall import Card, all_sets
from mtgcards.utils.scrape import timed_request


class MoxfieldParser(DeckParser):
    """Parser of Moxfield decklist page.
    """
    API_URL_TEMPLATE = "https://api2.moxfield.com/v2/decks/all/{}"

    def __init__(self, url: str, fmt="standard", author="") -> None:
        super().__init__(fmt, author)
        *_, self._decklist_id = url.split("/")
        self._json_data = timed_request(
            self.API_URL_TEMPLATE.format(self._decklist_id), return_json=True)
        self._metadata = self._get_metadata()
        self._deck = self._get_deck()

    def _get_metadata(self) -> Json:
        metadata = {"source": "www.moxfield.com"}
        self._fmt = metadata["format"] = self._json_data["format"]
        name = self._json_data["name"]
        if " - " in name:
            *_, name = name.split(" - ")
        metadata["name"] = name
        metadata["likes"] = self._json_data["likeCount"]
        metadata["views"] = self._json_data["viewCount"]
        metadata["comments"] = self._json_data["commentCount"]
        metadata["author"] = self._author or self._json_data["createdByUser"]["displayName"]
        metadata["date"] = datetime.strptime(
            self._json_data["lastUpdatedAtUtc"], "%Y-%m-%dT%H:%M:%S.%fZ").date()
        return metadata

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander = [], [], None
        for _, card in self._json_data["mainboard"].items():
            mainboard.extend(self._parse_card(card))
        for _, card in self._json_data["sideboard"].items():
            sideboard.extend(self._parse_card(card))
        if self._json_data["commanders"]:
            card = next(iter(self._json_data["commanders"].items()))[1]
            result = self._parse_card(card)
            if result:
                commander = result[0]

        try:
            return Deck(mainboard, sideboard, commander, metadata=self._metadata)
        except InvalidDeckError:
            return None

    def _parse_card(self, json_card: Json) -> list[Card]:
        quantity = json_card["quantity"]
        set_code, name = json_card["card"]["set"], json_card["card"]["name"]
        set_code = set_code if set_code in set(all_sets()) else ""
        return self._get_playset(name, quantity, set_code)
