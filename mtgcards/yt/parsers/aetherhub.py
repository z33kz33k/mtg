"""

    mtgcards.yt.parsers.aetherhub.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse AetherHub decklist page.

    @author: z33k

"""
from typing import List, Optional

from bs4 import Tag

from mtgcards import Card
from mtgcards.scryfall import Deck, InvalidDeckError, find_by_name_narrowed_by_collector_number, \
    set_cards
from mtgcards.yt.parsers import ParsingError, UrlParser


class AetherHubParser(UrlParser):
    """Parser of AetherHub decklist page.
    """
    def _parse(self) -> Optional[Deck]:
        main_list, sideboard, commander = [], [], None

        tables = self._soup.find_all("table", class_="table table-borderless")
        if not tables:
            raise ParsingError(f"No 'table table-borderless' tables (that contain grouped card "
                               f"data) in the soup")

        hovers = []
        for table in tables:
            hovers.append([*table.find_all("div", "hover-imglink")])
        hovers = [h for h in hovers if h]
        hovers = sorted([h for h in hovers if h], key=lambda h: len(h), reverse=True)

        if len(hovers[-1]) == 1:  # commander
            hovers, commander = hovers[:-1], hovers[-1]

        if len(hovers) == 2:
            main_list_tags, sideboard_tags = hovers
        elif len(hovers) == 1:
            main_list_tags, sideboard_tags = hovers[0], []
        else:
            raise ParsingError(f"Unexpected number of 'hover-imglink' div tags "
                               f"(that contain card data): {len(hovers)}")

        for tag in main_list_tags:
            main_list.extend(self._parse_hover_tag(tag))

        for tag in sideboard_tags:
            sideboard.extend(self._parse_hover_tag(tag))

        try:
            return Deck(main_list, sideboard, commander)
        except InvalidDeckError:
            return None

    def _parse_hover_tag(self, hover_tag: Tag) -> List[Card]:
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
        cards = set_cards(set_code)
        card = find_by_name_narrowed_by_collector_number(name, cards)
        if card:
            return [card] * quantity
        card = find_by_name_narrowed_by_collector_number(name, self._format_cards)
        return [card] * quantity if card else []
