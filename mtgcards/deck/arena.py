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
from mtgcards.utils import ParsingError, extract_int, from_iterable, getrepr
from mtgcards.utils import is_foreign

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
        if is_foreign(self._name):
            if card := query_api_for_card(self._name, foreign=True):
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


def _is_section_line(line: str, *sections: str) -> bool:
    sections = {*sections}
    sections.update({section.upper() for section in sections})
    sections.update({f"{section}:" for section in sections})
    if line in sections:
        return True
    # TODO: account for lines like "Main (60)" or "Sideboard(15)"
    return False


def is_maindeck_line(line: str) -> bool:
    return _is_section_line(
        line, "Main", "Maindeck", "Mainboard", "Deck", "Decklist", "Main Deck", "Main Board",
        "Deck List")


def is_commander_line(line: str) -> bool:
    return _is_section_line(line, "Commander", "Comandante")


def is_companion_line(line: str) -> bool:
    return _is_section_line(line, "Companion", "Companheiro")


def is_sideboard_line(line: str) -> bool:
    return _is_section_line(
        line, "Side", "Sideboard", "Sidedeck", "Sidelist", "Reserva", "Side Board", "Side Deck",
        "Side List")


def is_arena_line(line: str) -> bool:
    if is_maindeck_line(line) or is_sideboard_line(line):
        return True
    elif is_commander_line(line) or is_companion_line(line):
        return True
    elif is_playset_line(line):
        return True
    return False


def get_arena_lines(*lines: str) -> Generator[str, None, None]:
    last_yielded_line = None
    for i, line in enumerate(lines):
        if is_maindeck_line(line):
            if last_yielded_line != "Deck":
                last_yielded_line = "Deck"
                yield "Deck"
        elif is_commander_line(line):
            if last_yielded_line != "Commander":
                last_yielded_line = "Commander"
                yield "Commander"
        elif is_companion_line(line):
            if last_yielded_line != "Companion":
                last_yielded_line = "Companion"
                yield "Companion"
        elif is_playset_line(line):
            if last_yielded_line is None:
                last_yielded_line = "Deck"
                yield "Deck"
            last_yielded_line = line
            yield line
        elif is_sideboard_line(line):
            if last_yielded_line != "Sideboard":
                last_yielded_line = "Sideboard"
                yield "Sideboard"
        elif (is_empty(line)
              and 1 < i < len(lines) - 1
              and is_playset_line(lines[i - 2])  # previous previous line
              and is_playset_line(lines[i - 1])  # previous line
              and (is_playset_line(lines[i + 1]) or is_sideboard_line(lines[i + 1]))):  # next line
            if not is_sideboard_line(lines[i + 1]) and last_yielded_line != "Sideboard":
                last_yielded_line = "Sideboard"
                yield "Sideboard"


def group_arena_lines(*arena_lines: str) -> Generator[list[str], None, None]:
    current_group, commander_on, companion_on = [], False, False
    for line in arena_lines:
        if is_commander_line(line):
            commander_on = True
            if current_group and not companion_on:
                yield current_group
                current_group = []  # reset
        elif is_companion_line(line):
            companion_on = True
            if current_group and not commander_on:
                yield current_group
                current_group = []  # reset
        elif is_maindeck_line(line):
            if current_group and (not commander_on or not companion_on):
                commander_on, companion_on = False, False
                yield current_group
                current_group = []  # reset
        current_group.append(line)
    if current_group:
        yield current_group


class ArenaParser(DeckParser):
    """Parser of lines of text that denote a deck in Arena format.
    """
    def __init__(self, lines: list[str], metadata: Json | None = None) -> None:
        super().__init__(metadata)
        self._lines = lines

    def _pre_parse(self) -> None:  # override
        name_line = from_iterable(self._lines, lambda l: l.startswith("Name "))
        if name_line:
            self._metadata["name"] = name_line.removeprefix("Name ")

        self._lines = [*get_arena_lines(*self._lines)]
        if not self._lines:
            raise ValueError("No Arena lines found")

        if not any(is_commander_line(l) for l in self._lines):
            idx = None
            for i, line in enumerate(self._lines):
                if is_maindeck_line(line):
                    idx = i
                    break
            if idx in (1, 2):
                self._lines.insert(0, "Commander")
        if not self._metadata.get("source"):
            self._metadata["source"] = "arena.decklist"

    def _parse_deck(self) -> None:  # override
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
