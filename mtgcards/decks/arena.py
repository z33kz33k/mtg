"""

    mtgcards.decks.arena.py
    ~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Arena decklist text format.

    @author: z33k

"""
import logging
import re

from mtgcards.const import Json
from mtgcards.decks import ARENA_MULTIPART_SEPARATOR, Deck, DeckParser, InvalidDeckError, \
    ParsingState, get_playset
from mtgcards.scryfall import Card, MULTIPART_SEPARATOR as SCRYFALL_MULTIPART_SEPARATOR, \
    find_by_collector_number
from mtgcards.utils import extract_int, getint, getrepr


_log = logging.getLogger(__name__)


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


class PlaysetLine:
    """A line of text in MtG Arena decklist format that denotes a card playset.

    Example:
        '4 Commit /// Memory (AKR) 54'
    """
    # matches '4 Commit /// Memory'
    PATTERN = re.compile(r"\d{1,3}x?\s[A-Z][\w\s'&/,-]+")
    # matches '4 Commit /// Memory (AKR) 54'
    EXTENDED_PATTERN = re.compile(r"\d{1,3}x?\s[A-Z][\w\s'&/,-]+\([A-Z\d]{3}\)\s\d+")

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
    def set_code(self) -> str:
        return self._set_code

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
            self._set_code, rest = rest.split(")")
            self._collector_number = getint(rest.strip())
        else:
            self._name, self._set_code, self._collector_number = rest, "", None
        self._name = self._name.replace(ARENA_MULTIPART_SEPARATOR, SCRYFALL_MULTIPART_SEPARATOR)

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
            try:
                if card := find_by_collector_number(self.collector_number, self.set_code):
                    return [card] * self.quantity
            except ValueError as ve:  # Scryfall has different codes for Alchemy sets than Arena
                if "Invalid set code" in str(ve):
                    pass
        return get_playset(self.name, self.quantity, self.set_code, fmt)


def is_playset_line(line: str) -> bool:
    return bool(PlaysetLine.PATTERN.match(line))


def is_empty(line: str) -> bool:
    return not line or line.isspace()


def is_arena_line(line: str) -> bool:
    if line == "Deck":
        return True
    elif line == "Commander":
        return True
    elif line == "Companion":
        return True
    elif line == "Sideboard":
        return True
    elif is_playset_line(line):
        return True
    return False


class ArenaParser(DeckParser):
    """Parser of lines of text that denote a deck in Arena format.
    """
    def __init__(self, lines: list[str], metadata: Json | None = None) -> None:
        super().__init__(metadata)
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
            elif is_playset_line(line):
                if self._state is ParsingState.IDLE:
                    self._state = _shift_to_mainboard(self._state)

                if self._state is ParsingState.SIDEBOARD:
                    sideboard.extend(PlaysetLine(line).to_playset(self.fmt))
                elif self._state is ParsingState.COMMANDER:
                    result = PlaysetLine(line).to_playset(self.fmt)
                    commander = result[0] if result else None
                elif self._state is ParsingState.COMPANION:
                    result = PlaysetLine(line).to_playset(self.fmt)
                    companion = result[0] if result else None
                elif self._state is ParsingState.MAINBOARD:
                    mainboard.extend(PlaysetLine(line).to_playset(self.fmt))

        try:
            return Deck(mainboard, sideboard, commander, companion, self._metadata)
        except InvalidDeckError as err:
            _log.warning(f"Parsing failed with: {err}")
            return None
