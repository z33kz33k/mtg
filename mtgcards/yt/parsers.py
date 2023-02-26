"""

    mtgcards.yt.parsers.py
    ~~~~~~~~~~~~~~~~~~~~~~
    Parse YouTube video's descriptions for card data.

    @author: z33k

"""
import re
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Optional, Set, Type, Union

from bs4 import BeautifulSoup
from bs4.element import Tag

from mtgcards.scryfall import MULTIPART_SEPARATOR as SCRYFALL_MULTIPART_SEPARATOR
from mtgcards.scryfall import Card, Deck, find_by_name_narrowed_by_collector_number, set_cards, \
    InvalidDeckError
from mtgcards.utils import getrepr, parse_int_from_str, timed_request


class ParsingError(ValueError):
    """Raised on unexpected states of parsed data.
    """


class _ParsingState(Enum):
    """State machine for Arena lines parsing.
    """
    IDLE = auto()
    MAINLIST = auto()
    COMMANDER = auto()
    SIDEBOARD = auto()

    @classmethod
    def shift_to_idle(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state not in (_ParsingState.MAINLIST, _ParsingState.COMMANDER,
                                 _ParsingState.SIDEBOARD):
            raise RuntimeError(f"Invalid transition to IDLE from: {current_state.name}")
        return _ParsingState.IDLE

    @classmethod
    def shift_to_mainlist(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state is not _ParsingState.IDLE:
            raise RuntimeError(f"Invalid transition to MAIN_LIST from: {current_state.name}")
        return _ParsingState.MAINLIST

    @classmethod
    def shift_to_commander(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state is not _ParsingState.IDLE:
            raise RuntimeError(f"Invalid transition to COMMANDER from: {current_state.name}")
        return _ParsingState.COMMANDER

    @classmethod
    def shift_to_sideboard(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state is not _ParsingState.IDLE:
            raise RuntimeError(f"Invalid transition to SIDEBOARD from: {current_state.name}")
        return _ParsingState.SIDEBOARD


class _CardLine:
    """A line of text in MtG Arena decklist format that denotes a card.

    Example:
        '4 Commit /// Memory (AKR) 54'
    """
    MULTIPART_SEPARATOR = "///"  # this is different than in Scryfall data where they use: '//'
    # matches '4 Commit /// Memory'
    PATTERN = re.compile(r"\d{1,3}\s[A-Z][\w\s'&/,-]+")
    # matches '4 Commit /// Memory (AKR) 54'
    EXTENDED_PATTERN = re.compile(r"\d{1,3}\s[A-Z][\w\s'&/,-]+\([A-Z\d]{3}\)\s\d+")

    @property
    def raw_line(self) -> str:
        return self._raw_line

    @property
    def is_extended(self) -> bool:
        return self._is_extended

    @property
    def quantity(self) -> int:
        return self._quantity

    @property
    def name(self) -> str:
        return self._name

    @property
    def set_code(self) -> Optional[str]:
        return self._setcode

    @property
    def collector_number(self) -> Optional[int]:
        return self._collector_number

    def __init__(self, line: str) -> None:
        self._raw_line = line
        self._is_extended = self.EXTENDED_PATTERN.match(line) is not None
        quantity, rest = line.split(maxsplit=1)
        self._quantity = int(quantity)
        if self.is_extended:
            self._name, rest = rest.split("(")
            self._name = self._name.strip()
            self._setcode, rest = rest.split(")")
            self._collector_number = parse_int_from_str(rest.strip())
        else:
            self._name, self._setcode, self._collector_number = rest, None, None
        self._name = self._name.replace(self.MULTIPART_SEPARATOR, SCRYFALL_MULTIPART_SEPARATOR)

    def __repr__(self) -> str:
        pairs = [("quantity", self.quantity), ("name", self.name)]
        if self.is_extended:
            pairs += [("setcode", self.set_code), ("collector_number", self.collector_number)]
        return getrepr(self.__class__, *pairs)

    def process(self, format_cards: Set[Card]) -> List[Card]:
        """Process this Arena line into a number of cards.

        :param format_cards: provide a card pool corresponding to a MtG format to aid in searching
        :return a list of cards according to this line's quantity or an empty list if no card can be identified
        """
        if self.is_extended:
            cards = set_cards(self.set_code.lower())
            card = find_by_name_narrowed_by_collector_number(self.name, cards)
            if card:
                return [card] * self.quantity

        card = find_by_name_narrowed_by_collector_number(self.name, format_cards)
        return [card] * self.quantity if card else []


class ArenaParser:
    """Parser of YT video description lines that denote a deck in Arena format.
    """
    @property
    def deck(self) -> Optional[Deck]:
        return self._deck

    def __init__(self, lines: List[str], format_cards: Set[Card]) -> None:
        self._lines, self._format_cards = lines, format_cards
        self._state = _ParsingState.IDLE
        self._deck = self._parse_lines()

    @staticmethod
    def is_arena_line(line: str) -> bool:
        if not line or line.isspace():
            return True
        elif line.startswith("Sideboard"):
            return True
        elif line.startswith("Commander"):
            return True
        else:
            match = _CardLine.PATTERN.match(line)
            if match:
                return True
        return False

    def _parse_lines(self) -> Optional[Deck]:
        main_list, sideboard, commander = [], [], None
        for line in self._lines:
            if self._state is not _ParsingState.IDLE and (not line or line.isspace()):
                self._state = _ParsingState.shift_to_idle(self._state)
            elif line.startswith("Sideboard"):
                self._state = _ParsingState.shift_to_sideboard(self._state)
            elif line.startswith("Commander"):
                self._state = _ParsingState.shift_to_commander(self._state)
            else:
                match = _CardLine.PATTERN.match(line)
                if match:
                    if self._state is _ParsingState.IDLE:
                        try:
                            return Deck(main_list, sideboard, commander)
                        except InvalidDeckError:
                            pass
                        self._state = _ParsingState.shift_to_mainlist(self._state)
                        main_list, sideboard, commander = [], [], None  # reset state

                    if self._state is _ParsingState.SIDEBOARD:
                        sideboard.extend(_CardLine(line).process(self._format_cards))
                    elif self._state is _ParsingState.COMMANDER:
                        result = _CardLine(line).process(self._format_cards)
                        commander = result[0] if result else None
                    elif self._state is _ParsingState.MAINLIST:
                        main_list.extend(_CardLine(line).process(self._format_cards))

        try:
            return Deck(main_list, sideboard, commander)
        except InvalidDeckError:
            return None


class UrlParser(ABC):
    """Abstract base parser of URLs pointing to decklists.
    """
    @property
    @abstractmethod
    def url(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def deck(self) -> Optional[Deck]:
        raise NotImplementedError

    @abstractmethod
    def __init__(self, url: str, format_cards: Set[Card]) -> None:
        raise NotImplementedError


class AetherHubParser(UrlParser):
    """Parser of AetherHub deck page.
    """
    @property
    def url(self) -> str:
        return self._url

    @property
    def deck(self) -> Optional[Deck]:
        return self._deck

    def __init__(self, url: str, format_cards: Set[Card]) -> None:
        self._url, self._format_cards = url, format_cards
        self._markup = timed_request(url)
        self._soup = BeautifulSoup(self._markup, "lxml")
        self._deck = self._parse()

    # def _parse(self) -> Optional[Deck]:
    #     card_tags = [*self._soup.find_all("a", class_="cardLink")]
    #     card_tags = self._trim_duplicates(card_tags)
    #     playset_tags = defaultdict(list)
    #     for tag in card_tags:
    #         playset_tags[tag.attr["data-card-name"]].append(tag)
    #
    # @staticmethod
    # def _trim_duplicates(card_tags: List[Tag]) -> List[Tag]:
    #     names = [c.attrs["data-card-name"] for c in card_tags]
    #
    #     idx, offset = 0, 10
    #     searched = None
    #     marker_group = names[:offset]
    #     current_group = marker_group[:]
    #
    #     while current_group:
    #         idx += offset
    #         current_group = names[idx: idx + offset]
    #         if current_group == marker_group:
    #             searched = idx
    #             break
    #
    #     return card_tags[:searched] if searched else card_tags

    # @staticmethod
    # def _parse_playset_tags(playset_tags: List[Tag]) -> List[Card]:
    #     card_tag = playset_tags[0]
    #     name, set_code = card_tag.attrs["data-card-name"], card_tag.attrs["data-card-set"].lower()
    #     cards = set_cards(set_code)
    #     card = find_by_name_narrowed_by_collector_number(name, cards)
    #     return [card] * len(playset_tags) if card else []

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


def get_url_parser(designation: str) -> Type[UrlParser]:
    """Return decklist URL parser class according to provider ``designation``.
    """
    if designation == "aetherhub":
        return AetherHubParser
    else:
        raise ValueError(f"Unrecognized parser: {designation!r}")

