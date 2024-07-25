"""

    mtgcards.decks.aetherhub.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse AetherHub decklist page.

    @author: z33k

"""
from datetime import datetime

from bs4 import Tag

from mtgcards.const import Json
from mtgcards.decks import Archetype, Deck, DeckParser, InvalidDeckError, Mode
from mtgcards.scryfall import Card
from mtgcards.utils import ParsingError, extract_float, extract_int
from mtgcards.utils.scrape import ScrapingError, getsoup


# TODO: Companion
class AetherhubParser(DeckParser):
    """Parser of Aetherhub decklist page.
    """
    FORMATS = {
        "Arena Standard": ("standard", Mode.BO1),
        "Standard": ("standard", Mode.BO3),
        "Alchemy": ("alchemy", Mode.BO1),
        "Traditional Alchemy": ("alchemy", Mode.BO3),
        "Historic": ("historic", Mode.BO1),
        "Traditional Historic": ("historic", Mode.BO3),
        "Explorer": ("explorer", Mode.BO1),
        "Traditional Explorer": ("explorer", Mode.BO3),
        "Timeless": ("timeless", Mode.BO1),
        "Traditional Timeless": ("timeless", Mode.BO3),
        "Brawl": ("standardbrawl", Mode.BO3),
        "Historic Brawl": ("brawl", Mode.BO3),
        "Pioneer": ("pioneer", Mode.BO3),
        "Modern": ("modern", Mode.BO3),
        "Legacy": ("legacy", Mode.BO3),
        "Vintage": ("vintage", Mode.BO3),
        "Commander": ("commander", Mode.BO3),
        "Oathbreaker": ("oathbreaker", Mode.BO3),
    }

    def __init__(self, url: str, fmt="standard", author="") -> None:
        super().__init__(fmt, author)
        self._soup = getsoup(url)
        self._metadata = self._get_metadata()
        self._deck = self._get_deck()

    def _get_metadata(self) -> Json:
        metadata = {"source": "aetherhub.com"}

        # name and format
        if title_tag := self._soup.find("h2", class_="text-header-gold"):
            fmt_part, name_part = title_tag.text.strip().split("-", maxsplit=1)
            fmt_part = fmt_part.strip()
            if fmt_pair := self.FORMATS.get(fmt_part):
                fmt, mode = fmt_pair
                self._fmt = fmt
                metadata["format"] = fmt
                metadata["mode"] = mode.value
            metadata["name"] = name_part.strip()

        # author (only in user-submitted decklists)
        if not self._author:
            if author_tag := self._soup.find('a', href=lambda href: href and "/User/" in href):
                metadata["author"] = author_tag.text

        # date and other (only in user-submitted decklists)
        if date_tags := self._soup.select(
            "div.col-xs-7.col-sm-7.col-md-7.col-lg-7.pl-0.pr-0.text-left"):
            date_tag = date_tags[0]
            date_lines = [l.strip() for l in date_tag.text.strip().splitlines() if l]
            date_text = date_lines[0].removeprefix("Last Updated: ").strip()
            metadata["date"] = datetime.strptime(date_text, "%d %b %Y").date()
            metadata["views"] = int(date_lines[2])
            metadata["exports"] = int(date_lines[3])
            metadata["comments"] = int(date_lines[4])

        # archetype
        if archetype_tag := self._soup.find("div", class_="archetype-tag"):
            archetype = archetype_tag.text.strip().lower()
            if archetype in {a.value for a in Archetype}:
                metadata["archetype"] = archetype

        # meta (only in meta-decklists)
        if meta_tag := self._soup.find("h5", class_="text-center"):
            text = meta_tag.text.strip()
            share_part, change_part = text.split("of meta")
            metadata["meta_share"] = extract_float(share_part)
            metadata["meta_share_change"] = extract_float(change_part)

            count_tag = self._soup.select("h4.text-center.pt-2")[0]
            count_text, _ = count_tag.text.strip().split("decks,")
            metadata["meta_count"] = extract_int(count_text)

        return metadata

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander = [], [], None

        tables = self._soup.find_all("table", class_="table table-borderless")
        if not tables:
            raise ScrapingError(
                f"No 'table table-borderless' tables (that contain grouped card data) in the soup")

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
            raise ScrapingError(
                f"Unexpected number of 'hover-imglink' div tags (that contain card data): "
                f"{len(hovers)}")

        for tag in main_list_tags:
            mainboard.extend(self._parse_hover_tag(tag))

        for tag in sideboard_tags:
            sideboard.extend(self._parse_hover_tag(tag))

        if commander_tag is not None:
            result = self._parse_hover_tag(commander_tag)
            if result:
                commander = result[0]

        try:
            return Deck(mainboard, sideboard, commander, metadata=self._metadata)
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
