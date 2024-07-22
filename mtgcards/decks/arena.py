"""

    mtgcards.decks.arena.py
    ~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Arena decklist text format.

    @author: z33k

"""
import re
from enum import Enum, auto

from mtgcards.decks import Deck, InvalidDeckError, format_cards
from mtgcards.scryfall import Card, MULTIPART_SEPARATOR as SCRYFALL_MULTIPART_SEPARATOR, find_by_name, set_cards
from mtgcards.utils import extract_int, getrepr, getint


class _ParsingState(Enum):
    """State machine for Arena lines parsing.
    """
    IDLE = auto()
    MAINBOARD = auto()
    COMMANDER = auto()
    SIDEBOARD = auto()

    @classmethod
    def shift_to_idle(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state not in (_ParsingState.MAINBOARD, _ParsingState.COMMANDER,
                                 _ParsingState.SIDEBOARD):
            raise RuntimeError(f"Invalid transition to IDLE from: {current_state.name}")
        return _ParsingState.IDLE

    @classmethod
    def shift_to_mainlist(cls, current_state: "_ParsingState") -> "_ParsingState":
        if current_state is not _ParsingState.IDLE:
            raise RuntimeError(f"Invalid transition to MAINBOARD from: {current_state.name}")
        return _ParsingState.MAINBOARD

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
    MULTIPART_SEPARATOR = "///"  # this is different from in Scryfall data where they use: '//'
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
    def set_code(self) -> str | None:
        return self._setcode

    @property
    def collector_number(self) -> int | None:
        return self._collector_number

    def __init__(self, line: str) -> None:
        self._raw_line = line
        self._is_extended = self.EXTENDED_PATTERN.match(line) is not None
        quantity, rest = line.split(maxsplit=1)
        self._quantity = extract_int(quantity)
        if self.is_extended:
            self._name, rest = rest.split("(")
            self._name = self._name.strip()
            self._setcode, rest = rest.split(")")
            self._collector_number = getint(rest.strip())
        else:
            self._name, self._setcode, self._collector_number = rest, None, None
        self._name = self._name.replace(self.MULTIPART_SEPARATOR, SCRYFALL_MULTIPART_SEPARATOR)

    def __repr__(self) -> str:
        pairs = [("quantity", self.quantity), ("name", self.name)]
        if self.is_extended:
            pairs += [("setcode", self.set_code), ("collector_number", self.collector_number)]
        return getrepr(self.__class__, *pairs)

    def process(self, fmt: str) -> list[Card]:
        """Process this Arena line into a number of cards.

        :param fmt: MtG format string designation
        :return a list of cards according to this line's quantity or an empty list if no card can be identified
        """
        if self.is_extended:
            cards = set_cards(self.set_code.lower())
            card = find_by_name(self.name, cards)
            if card:
                return [card] * self.quantity

        card = find_by_name(self.name, format_cards(fmt))
        return [card] * self.quantity if card else []


class ArenaParser:
    """Parser of YT video description lines that denote a deck in Arena format.
    """
    @property
    def deck(self) -> Deck | None:
        return self._deck

    def __init__(self, lines: list[str], fmt="standard") -> None:
        self._lines, self._fmt = lines, fmt
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

    def _parse_lines(self) -> Deck | None:
        mainboard, sideboard, commander = [], [], None
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
                            return Deck(mainboard, sideboard, commander)
                        except InvalidDeckError:
                            pass
                        self._state = _ParsingState.shift_to_mainlist(self._state)
                        mainboard, sideboard, commander = [], [], None  # reset state

                    fmt_cards = format_cards(self._fmt)
                    if self._state is _ParsingState.SIDEBOARD:
                        sideboard.extend(_CardLine(line).process(self._fmt))
                    elif self._state is _ParsingState.COMMANDER:
                        result = _CardLine(line).process(self._fmt)
                        commander = result[0] if result else None
                    elif self._state is _ParsingState.MAINBOARD:
                        mainboard.extend(_CardLine(line).process(self._fmt))

        try:
            return Deck(mainboard, sideboard, commander)
        except InvalidDeckError:
            return None