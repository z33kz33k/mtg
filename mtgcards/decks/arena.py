"""

    mtgcards.decks.arena.py
    ~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Arena decklist text format.

    @author: z33k

"""
import re

from mtgcards.decks import Deck, DeckParser, InvalidDeckError, ParsingState, format_cards
from mtgcards.scryfall import Card, MULTIPART_SEPARATOR as SCRYFALL_MULTIPART_SEPARATOR, \
    find_by_name, set_cards
from mtgcards.utils import extract_int, getrepr, getint


def _shift_to_idle(current_state: ParsingState) -> ParsingState:
    if current_state not in (
            ParsingState.MAINBOARD, ParsingState.COMMANDER, ParsingState.COMPANION,
            ParsingState.SIDEBOARD):
        raise RuntimeError(f"Invalid transition to IDLE from: {current_state.name}")
    return ParsingState.IDLE

def _shift_to_mainboard(current_state: ParsingState) -> ParsingState:
    if current_state is not ParsingState.IDLE:
        raise RuntimeError(f"Invalid transition to MAINBOARD from: {current_state.name}")
    return ParsingState.MAINBOARD

def _shift_to_sideboard(current_state: ParsingState) -> ParsingState:
    if current_state is not ParsingState.IDLE:
        raise RuntimeError(f"Invalid transition to SIDEBOARD from: {current_state.name}")
    return ParsingState.SIDEBOARD

def _shift_to_commander(current_state: ParsingState) -> ParsingState:
    if current_state is not ParsingState.IDLE:
        raise RuntimeError(f"Invalid transition to COMMANDER from: {current_state.name}")
    return ParsingState.COMMANDER

def _shift_to_companion(current_state: ParsingState) -> ParsingState:
    if current_state is not ParsingState.IDLE:
        raise RuntimeError(f"Invalid transition to COMPANION from: {current_state.name}")
    return ParsingState.COMPANION


class _PlaysetLine:
    """A line of text in MtG Arena decklist format that denotes a card playset.

    Example:
        '4 Commit /// Memory (AKR) 54'
    """
    MULTIPART_SEPARATOR = "///"  # this is different from Scryfall data where they use: '//'
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

    def to_playset(self, fmt: str) -> list[Card]:
        """Process this line into a playset of cards.

        Args:
            fmt: MtG format string designation

        Returns:
            a list of cards according to this line's quantity or an empty list if no card can be identified
        """
        if self.is_extended:
            cards = set_cards(self.set_code.lower())
            if card := find_by_name(self.name, cards):
                return [card] * self.quantity

        card = find_by_name(self.name, format_cards(fmt))
        return [card] * self.quantity if card else []


def is_playset(line: str) -> bool:
    return bool(_PlaysetLine.PATTERN.match(line))


def is_empty(line: str) -> bool:
    return not line or line.isspace()


class ArenaParser(DeckParser):
    """Parser of lines of text that denote a deck in Arena format.
    """
    def __init__(self, lines: list[str], fmt="standard") -> None:
        super().__init__(fmt)
        self._lines = lines
        self._deck = self._get_deck()

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander, companion = [], [], None, None
        for line in self._lines:
            if self._state is not ParsingState.IDLE and is_empty(line):
                self._state = _shift_to_idle(self._state)
            elif line == "Sideboard":
                self._state = _shift_to_sideboard(self._state)
            elif line == "Commander":
                self._state = _shift_to_commander(self._state)
            elif line == "Companion":
                self._state = _shift_to_companion(self._state)
            elif line == "Deck":
                self._state = _shift_to_mainboard(self._state)
            elif is_playset(line):
                if self._state is ParsingState.IDLE:
                    self._state = _shift_to_mainboard(self._state)

                if self._state is ParsingState.SIDEBOARD:
                    sideboard.extend(_PlaysetLine(line).to_playset(self._fmt))
                elif self._state is ParsingState.COMMANDER:
                    result = _PlaysetLine(line).to_playset(self._fmt)
                    commander = result[0] if result else None
                elif self._state is ParsingState.COMPANION:
                    result = _PlaysetLine(line).to_playset(self._fmt)
                    companion = result[0] if result else None
                elif self._state is ParsingState.MAINBOARD:
                    mainboard.extend(_PlaysetLine(line).to_playset(self._fmt))

        try:
            return Deck(mainboard, sideboard, commander, companion, {"format": self._fmt})
        except InvalidDeckError:
            return None
