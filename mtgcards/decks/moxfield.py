"""

    mtgcards.decks.moxfield.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Moxfield decklist page.

    @author: z33k

"""

from mtgcards.const import Json
from mtgcards.decks import UrlParser
from mtgcards.scryfall import Card, Deck, InvalidDeckError
from mtgcards.utils import timed_request


class MoxfieldParser(UrlParser):
    """Parser of Moxfield decklist page.
    """
    API_URL_TEMPLATE = "https://api2.moxfield.com/v2/decks/all/{}"

    def __init__(self, url: str, format_cards: set[Card]) -> None:
        super().__init__(url, format_cards)
        *_, self._decklist_id = url.split("/")
        self._json_data = timed_request(self.API_URL_TEMPLATE.format(self._decklist_id),
                                        return_json=True)
        self._deck = self._get_deck()

    def _get_deck(self) -> Deck | None:
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
            return Deck(mainboard, sideboard, commander)
        except InvalidDeckError:
            return None

    def _parse_card(self, json_card: Json) -> list[Card]:
        quantity = json_card["quantity"]
        set_code, name = json_card["card"]["set"], json_card["card"]["name"]
        return self._get_playset(name, quantity, set_code)
