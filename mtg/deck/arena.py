"""

    mtg.deck.arena
    ~~~~~~~~~~~~~~
    Parse Arena/MTGO decklist text format.

    @author: z33k

"""
import logging
from typing import override

import regex as re

from mtg import Json
from mtg.deck import ARENA_MULTIFACE_SEPARATOR, CardNotFound, DeckParser
from mtg.scryfall import COMMANDER_FORMATS, Card, \
    MULTIFACE_SEPARATOR as SCRYFALL_MULTIFACE_SEPARATOR, query_api_for_card
from mtg.utils import ParsingError, extract_int, getrepr, is_foreign, sanitize_whitespace

_log = logging.getLogger(__name__)


# define the first character class for card names:
# uppercase Latin, underscore, double-quote, or Japanese character
_FIRST_CHAR = r'[\p{Lu}_"\p{Han}\p{Hiragana}\p{Katakana}]'
# the rest: word, whitespace, punctuation, or Japanese scripts
_REST_CHARS = r'[\w\s\'\"&/,.!:_\-（）\u3000-\u303F\p{Han}\p{Hiragana}\p{Katakana}]*'


class PlaysetLine:
    """A line of text in MtG Arena decklist format that denotes a card playset.
    """

    # Regular: '4 トリックスター、ザレス・サン'
    PATTERN = re.compile(
        rf"^\d{{1,3}}\s?x?\s{_FIRST_CHAR}{_REST_CHARS}", re.UNICODE
    )
    # Inverted: 'トリックスター、ザレス・サン 4'
    INVERTED_PATTERN = re.compile(
        rf"^{_FIRST_CHAR}{_REST_CHARS}\sx?\s?\d{{1,3}}$", re.UNICODE
    )
    # Extended: '4 トリックスター、ザレス・サン (ZNR) 242'
    EXTENDED_PATTERN = re.compile(
        rf"^\d{{1,3}}\s?x?\s{_FIRST_CHAR}{_REST_CHARS}\s+\([A-Za-z\d]{{3,6}}\)\s+[A-Za-z\d]{{1,6}}",
        re.UNICODE
    )

    @property
    def is_extended(self) -> bool:
        return self._is_extended

    @property
    def is_inverted(self) -> bool:
        return self._is_inverted

    @property
    def quantity(self) -> int:
        return self._quantity

    @property
    def name(self) -> str:
        return self._name.strip()

    @property
    def set_code(self) -> str:
        return self._set_code.lower()

    @property
    def collector_number(self) -> str:
        return self._collector_number

    def __init__(self, line: str) -> None:
        line = ArenaParser.sanitize_card_name(line)
        regular_match = self.PATTERN.match(line)
        extended_match = self.EXTENDED_PATTERN.match(line)
        inverted_match = self.INVERTED_PATTERN.match(line)
        self._is_extended = extended_match is not None
        self._is_inverted = inverted_match is not None
        if self.is_extended:
            matched_text = extended_match.group(0)
        elif self.is_inverted:
            matched_text = inverted_match.group(0)
        else:
            matched_text = regular_match.group(0)

        if self._is_inverted:
            rest, quantity = matched_text.rsplit(maxsplit=1)
        else:
            quantity, rest = matched_text.split(maxsplit=1)
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
        if is_foreign(self.name):
            if card := query_api_for_card(self.name, foreign=True):
                return ArenaParser.get_playset(card, self.quantity)
        return None

    def to_playset(self) -> list[Card]:
        set_and_collector_number = (
            self.set_code, self.collector_number) if self.is_extended else None
        try:
            return ArenaParser.get_playset(ArenaParser.find_card(
                self.name, set_and_collector_number), self.quantity)
        except CardNotFound as cnf:
            if cards := self._handle_foreign():
                return cards
            raise cnf


def _is_playset_line(line: str) -> bool:
    return bool(PlaysetLine.PATTERN.match(line)) or bool(PlaysetLine.INVERTED_PATTERN.match(line))


def is_empty(line: str) -> bool:
    return not line or line.isspace()


def _is_section_line(line: str, *sections: str) -> bool:
    sections = {*sections}
    sections.update({section.upper() for section in sections})
    sections.update({f"{section}:" for section in sections})
    pattern = re.compile(
        r"^\s*(" + "|".join(re.escape(section) for section in sections) + r")"
        r"(\s*[\[\(:]?\s*\d{1,3}[\]\)]?)?\s*:?$", re.IGNORECASE
    )
    return bool(pattern.match(line))


def _is_about_line(line: str) -> bool:
    return _is_section_line(line, "About")


def _is_name_line(line: str) -> bool:
    return line.startswith("Name ")


def _is_maindeck_line(line: str) -> bool:
    return _is_section_line(
        line, "Main", "Maindeck", "Mainboard", "Deck", "Decklist", "Main Deck", "Main Board",
        "Deck List", "Mazo", "Mallet", "デッキ")


def _is_commander_line(line: str) -> bool:
    return _is_section_line(line, "Commander", "Comandante", "統率者", "コマンダー")


def _is_companion_line(line: str) -> bool:
    return _is_section_line(line, "Companion", "Companheiro")


def _is_sideboard_line(line: str) -> bool:
    return _is_section_line(
        line, "Side", "Sideboard", "Sidedeck", "Sidelist", "Reserva", "Side Board", "Side Deck",
        "Side List", "サイドボード")


def is_arena_line(line: str) -> bool:
    if _is_maindeck_line(line) or _is_sideboard_line(line):
        return True
    elif _is_commander_line(line) or _is_companion_line(line):
        return True
    elif _is_about_line(line) or _is_name_line(line):
        return True
    elif _is_playset_line(line):
        return True
    return False


class LinesParser:
    @property
    def decklists(self) -> list[str]:
        return self._decklists

    def __init__(self, *lines: str):
        self._lines = lines
        self._buffer = []
        self._metadata, self._commander, self._companion = [], [], []
        self._maindeck, self._sideboard = [], []
        self._decklists: list[str] = []

    def _flush(self, section: list[str]) -> None:
        self._buffer.reverse()
        while self._buffer:
            section.append(self._buffer.pop())

    def _reset(self) -> None:
        self._metadata, self._commander, self._companion = [], [], []
        self._maindeck, self._sideboard = [], []

    def _concatenate(self) -> None:
        if self._commander and self._commander[0] != "Commander":
            self._commander.insert(0, "Commander")
        if self._companion and self._companion[0] != "Companion":
            self._companion.insert(0, "Companion")
        if self._maindeck and self._maindeck[0] != "Deck":
            self._maindeck.insert(0, "Deck")
        if self._sideboard and self._sideboard[0] != "Sideboard":
            self._sideboard.insert(0, "Sideboard")
        if self._commander == ["Commander"]:
            self._commander = []
        if self._companion == ["Companion"]:
            self._companion = []
        if self._sideboard == ["Sideboard"]:
            self._sideboard = []
        concatenated = (
                self._metadata + self._commander + self._companion + self._maindeck
                + self._sideboard)
        self._reset()
        return self._decklists.append("\n".join(concatenated))

    def parse(self) -> list[str]:
        self._reset()
        self._decklists = []
        last_line = None

        for line in self._lines:
            if _is_about_line(line):
                if self._maindeck and self._maindeck != ["Deck"]:
                    self._finish_decklist()
                if "About" not in self._metadata:
                    self._metadata.append("About")
            elif _is_name_line(line):
                if "About" in self._metadata:
                    self._metadata.append(line)
            elif _is_commander_line(line):
                if "Commander" not in self._commander:
                    if self._maindeck and self._maindeck != ["Deck"]:
                        self._finish_decklist()
                    else:
                        self._finish_section()
                    self._commander.append("Commander")
            elif _is_companion_line(line):
                if "Companion" not in self._companion:
                    if self._maindeck and self._maindeck != ["Deck"]:
                        self._finish_decklist()
                    else:
                        self._finish_section()
                    self._companion.append("Companion")
            elif _is_maindeck_line(line):
                if "Deck" not in self._maindeck:
                    if self._maindeck and self._maindeck != ["Deck"]:
                        self._finish_decklist()
                    else:
                        self._finish_section()
                    self._maindeck.append("Deck")
            elif _is_sideboard_line(line):
                if "Sideboard" not in self._sideboard:
                    if last_line and is_arena_line(last_line):
                        self._finish_section()
                    self._sideboard.append("Sideboard")
            elif _is_playset_line(line):
                # handle cases like:
                # Commander
                # 1 Some Commander Card
                # 1 Some Maindeck Card (without prior section separation)
                if (self._commander == ["Commander"]
                        and self._companion != ["Companion"]
                        and self._maindeck != ["Deck"]
                        and self._sideboard != ["Sideboard"]):
                    if len(self._buffer) == 1:
                        self._flush(self._commander)
                # handle cases like:
                # Companion
                # 1 Some Companion Card
                # 1 Some Maindeck Card (without prior section separation)
                elif (self._companion == ["Companion"]
                      and self._commander != ["Commander"]
                        and self._maindeck != ["Deck"]
                        and self._sideboard != ["Sideboard"]):
                    if len(self._buffer) == 1:
                        self._flush(self._companion)
                self._buffer.append(line)
            else:
                self._finish_section()

            last_line = line

        self._finish_decklist()
        return self._decklists

    def _finish_section(self) -> None:
        if self._buffer:
            if self._maindeck and self._maindeck != ["Deck"]:
                self._flush(self._sideboard)
            else:
                if len(self._buffer) == 1:
                    if self._companion == ["Companion"]:
                        self._flush(self._companion)
                    else:
                        self._flush(self._commander)
                elif len(self._buffer) == 2:
                    self._flush(self._commander)
                else:
                    self._flush(self._maindeck)
        elif self._maindeck and self._maindeck != ["Deck"]:
            self._concatenate()

    def _finish_decklist(self) -> None:
        if self._buffer:
            if self._maindeck:
                self._flush(self._sideboard)
            else:
                self._flush(self._maindeck)
        if self._maindeck and self._maindeck != ["Deck"]:
            self._concatenate()


def is_arena_decklist(decklist: str) -> bool:
    return all(is_arena_line(l) or is_empty(l) for l in decklist.splitlines())


class IllFormedArenaDecklist(ParsingError):
    """Raised on no ill-formed Arena decklists being parsed as one.
    """


class ArenaParser(DeckParser):
    """Parser of text decklists in Arena/MTGO format.
    """
    MAX_CARD_QUANTITY = 50

    def __init__(self, decklist: str, metadata: Json | None = None) -> None:
        super().__init__(metadata)
        self._decklist = decklist
        self._lines = [sanitize_whitespace(l) for l in self._decklist.splitlines()]
        self._no_maindeck_line = not any(_is_maindeck_line(l) for l in self._lines)

    def _handle_missing_commander_line(self):
        if not any(_is_commander_line(l) for l in self._lines):
            idx = None
            for i, line in enumerate(self._lines):
                if _is_maindeck_line(line):
                    idx = i
                    break
            if idx in (1, 2) and all(_is_playset_line(l) for l in self._lines[:idx]):
                self._lines.insert(0, "Commander")

    @override
    def _pre_parse(self) -> None:
        self._lines = [l for l in self._lines if is_arena_line(l) or is_empty(l)]
        if not self._lines:
            raise IllFormedArenaDecklist("No Arena lines found")
        self._handle_missing_commander_line()

    @override
    def _parse_metadata(self) -> None:
        if not self._metadata.get("source"):
            self._metadata["source"] = "arena.decklist"

    # last safeguard against lines that mimicked Arena lines successfully enough
    # not to be weeded out at this point
    def _quantity_exceeded(self, playset: list[Card]) -> bool:
        max_quantity, word = self.MAX_CARD_QUANTITY, "card"
        if self._state.is_commander:
            max_quantity, word = 1, "commander card"
        elif self._state.is_companion:
            max_quantity, word = 1, "companion card"
        if len(playset) > max_quantity:
            _log.warning(
                f"Quantity too high ({len(playset)}) for {word} {playset[0].name!r}. "
                f"Skipping...")
            return True
        return False

    @override
    def _parse_deck(self) -> None:
        for line in self._lines:
            if _is_maindeck_line(line):
                self._state.shift_to_maindeck()
            elif _is_sideboard_line(line):
                self._state.shift_to_sideboard()
            elif _is_commander_line(line):
                self._state.shift_to_commander()
            elif _is_companion_line(line):
                self._state.shift_to_companion()
            elif _is_name_line(line):
                self._metadata["name"] = line.removeprefix("Name ")
            elif _is_playset_line(line):
                if self._state.is_idle:
                    self._state.shift_to_maindeck()

                playset = PlaysetLine(line).to_playset()
                if self._quantity_exceeded(playset):
                    continue

                if self._state.is_sideboard:
                    self._sideboard.extend(playset)
                elif self._state.is_commander:
                    card = playset[0]
                    # handle cases when there's a commander section's line but no maindeck one
                    if self._no_maindeck_line:
                        if self._partner_commander is None:
                            if self._commander is not None and (
                                    len(playset) > 1 or not card.is_partner):
                                self._state.shift_to_maindeck()
                                self._maindeck.extend(playset)
                                continue
                        else:
                            self._state.shift_to_maindeck()
                            self._maindeck.extend(playset)
                            continue
                    self._set_commander(card)
                elif self._state.is_companion:
                    self._companion = playset[0]
                elif self._state.is_maindeck:
                    self._maindeck.extend(playset)


def normalize_decklist(decklist: str, fmt: str | None = None) -> str:
    """Normalize simple text decklists that only feature card lines and a sideboard demarcated
    by a blank line by adding proper section headers.

    If sideboard has only 1-2 card lines, it is assumed to be the commander sideboard. For
    additional certainty, one can pass a format string and then commander sideboard is assumed only
    if the passed format agrees.
    """
    commander, maindeck, sideboard, sideboard_on = [], [], [], False
    for line in decklist.splitlines():
        if not line:
            sideboard_on = True
            continue
        if sideboard_on:
            sideboard.append(line)
        else:
            maindeck.append(line)

    if len(sideboard) in (1, 2):
        if fmt is None:
            commander, sideboard = sideboard, commander
        else:
            if fmt in COMMANDER_FORMATS:
                commander, sideboard = sideboard, commander

    decklist = []
    if commander:
        decklist.append("Commander")
        decklist.extend(commander)
        decklist.append("")
    decklist.append("Deck")
    decklist.extend(maindeck)
    if sideboard:
        decklist.append("")
        decklist.append("Sideboard")
        decklist.extend(sideboard)

    return "\n".join(decklist)
