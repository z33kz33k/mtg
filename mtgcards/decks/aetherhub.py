"""

    mtgcards.decks.aetherhub.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse AetherHub decklist page.

    @author: z33k

"""
from datetime import datetime

from bs4 import Tag

from mtgcards.const import Json
from mtgcards.decks import Deck, InvalidDeckError, DeckParser
from mtgcards.utils import ParsingError, extract_int, from_iterable
from mtgcards.utils.scrape import ScrapingError, getsoup
from mtgcards.scryfall import Card, all_formats


# TODO: Companion
class AetherhubParser(DeckParser):
    """Parser of Aetherhub decklist page.
    """
    def __init__(self, url: str, fmt="standard", author="") -> None:
        super().__init__(fmt, author)
        self._soup = getsoup(url)
        self._metadata = self._get_metadata()
        self._deck = self._get_deck()

    def _get_metadata(self) -> Json:
        metadata = {}
        title_tag = self._soup.find("h2", class_="text-header-gold")
        if title_tag is None:
            raise ScrapingError(f"No title tag to scrape metadata from")
        fmt_part, name_part = title_tag.text.split("-", maxsplit=1)
        fmt = from_iterable(
            [t.lower() for t in fmt_part.split()], lambda p: p in all_formats())
        if fmt:
            self._fmt = fmt
            metadata["format"] = fmt
        metadata["name"] = name_part
        if not self._author:
            author_tag = self._soup.find('a', href=lambda href: href and "/User/" in href)
            metadata["author"] = author_tag.text
        date_tag = self._soup.select(
            "div.col-xs-7.col-sm-7.col-md-7.col-lg-7.pl-0.pr-0.text-left")[0]
        date_lines = [l.strip() for l in date_tag.text.strip().splitlines() if l]
        date_text = date_lines[0].removeprefix("Last Updated: ").strip()
        metadata["date"] = datetime.strptime(date_text, "%d %b %Y").date()
        metadata["views"] = int(date_lines[2])
        metadata["exports"] = int(date_lines[3])
        metadata["comments"] = int(date_lines[4])
        return metadata

    def _get_deck(self) -> Deck | None:  # override
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
        quantity = extract_int(quantity)

        card_tag = hover_tag.find("a")
        if card_tag is None:
            raise ParsingError(f"No 'a' tag inside 'hover-imglink' div tag: {hover_tag!r}")

        name, set_code = card_tag.attrs["data-card-name"], card_tag.attrs["data-card-set"].lower()
        return self._get_playset(name, quantity, set_code)
