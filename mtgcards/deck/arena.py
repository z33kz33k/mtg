"""

    mtgcards.deck.arena.py
    ~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Arena decklist text format.

    @author: z33k

"""
import logging
import re
from typing import Generator

from mtgcards import Json
from mtgcards.deck import ARENA_MULTIFACE_SEPARATOR, CardNotFound, DeckParser, ParsingState
from mtgcards.scryfall import Card, MULTIFACE_SEPARATOR as SCRYFALL_MULTIFACE_SEPARATOR, \
    query_api_for_card
from mtgcards.utils import ParsingError, extract_int, getrepr
from mtgcards.utils import detect_lang

_log = logging.getLogger(__name__)


class PlaysetLine:
    """A line of text in MtG Arena decklist format that denotes a card playset.

    Example:
        '4 Commit /// Memory (AKR) 54'
    """
    # matches '4 Commit /// Memory'
    PATTERN = re.compile("\\d{1,3}x?\\s[A-Z][\\w\\s'\"&/,.!:-]+")
    # matches '4 Commit /// Memory (AKR) 54'
    EXTENDED_PATTERN = re.compile(
        "\\d{1,3}x?\\s[A-Z][\\w\\s'\"&/,.!:-]+\\(([A-Za-z\\d]{3,6})\\)\\s[A-Za-z\\d]{1,6}")

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
        return self._set_code.lower()

    @property
    def collector_number(self) -> str:
        return self._collector_number

    def __init__(self, line: str) -> None:
        line = ArenaParser.sanitize_card_name(line)
        self._is_extended = self.EXTENDED_PATTERN.match(line) is not None
        quantity, rest = line.split(maxsplit=1)
        self._quantity = extract_int(quantity)
        if self.is_extended:
            self._name, rest = rest.split("(")
            self._name = self._name.strip()
            self._set_code, rest = rest.split(")")
            self._collector_number = rest.strip()
        else:
            self._name, self._set_code, self._collector_number = rest, "", ""
            if "(" in self.name and ")" in self.name and (self.name and self.name[-1].isdigit()):
                _log.warning(
                    f"{self.name!r} looks fishy for a card name. It seems like {line!r} Arena line "
                    f"is in extended format and hasn't been recognized as such by the parser")
        self._name = self._name.replace(ARENA_MULTIFACE_SEPARATOR, SCRYFALL_MULTIFACE_SEPARATOR)

    def __repr__(self) -> str:
        pairs = [("quantity", self.quantity), ("name", self.name)]
        if self.is_extended:
            pairs += [("setcode", self.set_code), ("collector_number", self.collector_number)]
        return getrepr(self.__class__, *pairs)

    def _handle_foreign(self) -> list[Card] | None:
        try:
            lang = detect_lang(self._name)
        except ValueError:
            return None
        if lang.iso_code_639_1.name.lower() == "en":
            return None
        _log.info(
            f"Querying Scryfall for English equivalent of {self._name!r} ({lang.name.title()})...")
        if card := query_api_for_card(self._name, foreign=True):
            _log.info(f"Acquired English card: {card.name!r}")
            return ArenaParser.get_playset(card, self.quantity)
        return None

    def to_playset(self) -> list[Card]:
        set_and_collector_number = (
            self.set_code, self.collector_number) if self.is_extended else None
        try:
            return ArenaParser.get_playset(ArenaParser.find_card(
                self._name, set_and_collector_number), self.quantity)
        except CardNotFound as cnf:
            if cards := self._handle_foreign():
                return cards
            raise cnf


def is_playset_line(line: str) -> bool:
    return bool(PlaysetLine.PATTERN.match(line))


def is_empty(line: str) -> bool:
    return not line or line.isspace()


def is_maindeck_line(line: str) -> bool:
    names = "Main", "Maindeck", "Mainboard", "Deck"
    if line in names:
        return True
    if line in [f"{name}:" for name in names]:
        return True
    return False


def is_commander_line(line: str) -> bool:
    return line == "Commander" or line == "Commander:"


def is_companion_line(line: str) -> bool:
    return line == "Companion" or line == "Companion:"


def is_sideboard_line(line: str) -> bool:
    names = "Side", "Sideboard", "Sidedeck"
    if line in names:
        return True
    if line in [f"{name}:" for name in names]:
        return True
    return False


def is_arena_line(line: str) -> bool:
    if is_maindeck_line(line) or is_sideboard_line(line):
        return True
    elif is_commander_line(line) or is_companion_line(line):
        return True
    elif is_playset_line(line):
        return True
    return False


def get_arena_lines(*lines: str) -> Generator[str, None, None]:
    for i, line in enumerate(lines):
        if is_arena_line(line):
            yield line
        elif (is_empty(line)
              and 0 < i < len(lines) - 1
              and is_arena_line(lines[i - 1])  # previous line
              and is_arena_line(lines[i + 1])  # next line
              and not is_sideboard_line(lines[i + 1])):
            yield "Sideboard"


class ArenaParser(DeckParser):
    """Parser of lines of text that denote a deck in Arena format.
    """
    def __init__(self, lines: list[str], metadata: Json | None = None) -> None:
        super().__init__(metadata)
        self._lines = lines

    def _pre_process(self) -> None:  # override
        self._lines = [*get_arena_lines(*self._lines)]
        if not self._lines:
            raise ValueError("No Arena lines found")
        if not self._metadata.get("source"):
            self._metadata["source"] = "arena.decklist"

    def _process_deck(self) -> None:  # override
        for line in self._lines:
            if is_maindeck_line(line):
                self._shift_to_maindeck()
            elif is_sideboard_line(line):
                self._shift_to_sideboard()
            elif is_commander_line(line):
                self._shift_to_commander()
            elif is_companion_line(line):
                self._shift_to_companion()
            elif is_playset_line(line):
                if self._state is ParsingState.IDLE:
                    self._shift_to_maindeck()

                if self._state is ParsingState.SIDEBOARD:
                    self._sideboard.extend(PlaysetLine(line).to_playset())
                elif self._state is ParsingState.COMMANDER:
                    if result := PlaysetLine(line).to_playset():
                        self._set_commander(result[0])
                    else:
                        raise ParsingError(f"Invalid commander line: {line!r}")
                elif self._state is ParsingState.COMPANION:
                    if result := PlaysetLine(line).to_playset():
                        self._companion = result[0]
                    else:
                        raise ParsingError(f"Invalid companion line: {line!r}")
                elif self._state is ParsingState.MAINDECK:
                    self._maindeck.extend(PlaysetLine(line).to_playset())
