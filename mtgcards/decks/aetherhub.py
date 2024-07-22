"""

    mtgcards.decks.aetherhub.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse AetherHub decklist page.

    @author: z33k

"""

from bs4 import Tag

from mtgcards.decks import Deck, InvalidDeckError, UrlParser
from mtgcards.utils import ParsingError
from mtgcards.scryfall import Card


class AetherHubParser(UrlParser):
    """Parser of AetherHub decklist page.
    """
    def __init__(self, url: str, fmt="standard") -> None:
        super().__init__(url, fmt)
        self._soup = self._get_soup()
        self._deck = self._get_deck()

    def _get_deck(self) -> Deck | None:
        mainboard, sideboard, commander = [], [], None

        tables = self._soup.find_all("table", class_="table table-borderless")
        if not tables:
            raise ParsingError(f"No 'table table-borderless' tables (that contain grouped card "
                               f"data) in the soup")

        hovers = []
        for table in tables:
            hovers.append([*table.find_all("div", "hover-imglink")])
        hovers = [h for h in hovers if h]
        hovers = sorted([h for h in hovers if h], key=lambda h: len(h), reverse=True)

        commander_tag = None
        if len(hovers[-1]) == 1:  # commander
            hovers, commander_tag = hovers[:-1], hovers[-1][0]

        if len(hovers) == 2:
            main_list_tags, sideboard_tags = hovers
        elif len(hovers) == 1:
            main_list_tags, sideboard_tags = hovers[0], []
        else:
            raise ParsingError(f"Unexpected number of 'hover-imglink' div tags "
                               f"(that contain card data): {len(hovers)}")

        for tag in main_list_tags:
            mainboard.extend(self._parse_hover_tag(tag))

        for tag in sideboard_tags:
            sideboard.extend(self._parse_hover_tag(tag))

        if commander_tag is not None:
            result = self._parse_hover_tag(commander_tag)
            if result:
                commander = result[0]

        try:
            return Deck(mainboard, sideboard, commander)
        except InvalidDeckError:
            return None

    def _parse_hover_tag(self, hover_tag: Tag) -> list[Card]:
        quantity, *_ = hover_tag.text.split()
        try:
            quantity = int(quantity)
        except ValueError:
            raise ParsingError(f"Can't parse card quantity from tag's text:"
                               f" {hover_tag.text.split()}")

        card_tag = hover_tag.find("a")
        if card_tag is None:
            raise ParsingError(f"No 'a' tag inside 'hover-imglink' div tag: {hover_tag!r}")

        name, set_code = card_tag.attrs["data-card-name"], card_tag.attrs["data-card-set"].lower()
        return self._get_playset(name, quantity, set_code)
