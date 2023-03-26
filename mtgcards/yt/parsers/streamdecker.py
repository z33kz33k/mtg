"""

    mtgcards.yt.parsers.streamdecker.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Streamdecker decklist page.

    @author: z33k

"""
from typing import List, Optional, Set

from mtgcards.const import Json
from mtgcards.scryfall import Deck, Card, InvalidDeckError, \
    find_by_name_narrowed_by_collector_number, set_cards
from mtgcards.utils import timed_request
from mtgcards.yt.parsers import UrlParser


class StreamdeckerParser(UrlParser):
    """Parser of Streamdecker deck page.
    """
    API_URL_TEMPLATE = "https://www.streamdecker.com/api/deck/{}"

    def __init__(self, url: str, format_cards: Set[Card]) -> None:
        super().__init__(url, format_cards)
        *_, self._decklist_id = url.split("/")
        self._json_data = timed_request(self.API_URL_TEMPLATE.format(self._decklist_id),
                                        return_json=True)
        self._deck = self._get_deck()

    def _get_deck(self) -> Optional[Deck]:
        mainboard, sideboard, commander = [], [], None
        # TODO: adapt to streamdecker JSON
        # for _, card in self._json_data["mainboard"].items():
        #     mainboard.extend(self._get_playset(card))
        # for _, card in self._json_data["sideboard"].items():
        #     sideboard.extend(self._get_playset(card))
        # if self._json_data["commanders"]:
        #     card = next(iter(self._json_data["commanders"].items()))[1]
        #     result = self._get_playset(card)
        #     if result:
        #         commander = result[0]

        try:
            return Deck(mainboard, sideboard, commander)
        except InvalidDeckError:
            return None

    def _get_playset(self, json_card: Json) -> List[Card]:
        # TODO: adapt to streamdecker JSON
        # quantity = json_card["quantity"]
        # set_code, name = json_card["card"]["set"], json_card["card"]["name"]
        # cards = set_cards(set_code)
        # card = find_by_name_narrowed_by_collector_number(name, cards)
        # if card:
        #     return [card] * quantity
        # card = find_by_name_narrowed_by_collector_number(name, self._format_cards)
        # return [card] * quantity if card else []
        pass
