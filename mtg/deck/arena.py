"""

    mtg.deck.arena
    ~~~~~~~~~~~~~~
    Parse Arena/MTGO decklist text format.

    @author: z33k

"""
import logging
import regex as re
from typing import Generator, override



from mtg import Json
from mtg.deck import ARENA_MULTIFACE_SEPARATOR, CardNotFound, DeckParser
from mtg.scryfall import COMMANDER_FORMATS, Card, \
    MULTIFACE_SEPARATOR as SCRYFALL_MULTIFACE_SEPARATOR, \
    query_api_for_card
from mtg.utils import ParsingError, extract_int, getrepr, sanitize_whitespace, is_foreign

_log = logging.getLogger(__name__)

_log = logging.getLogger(__name__)

# define the first character class for card names:
# uppercase Latin, underscore, double-quote, or Japanese character
_FIRST_CHAR = r'[\p{Lu}_"\p{Han}\p{Hiragana}\p{Katakana}]'
# the rest: word, whitespace, punctuation, or Japanese scripts
_REST_CHARS = r'[\w\s\'"&/,.!:_\-{}\(\)\[\]\u3000-\u303F\p{Han}\p{Hiragana}\p{Katakana}]*'

class PlaysetLine:
    """A line of text in MtG Arena decklist format that denotes a card playset."""

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


def get_arena_lines(*lines: str) -> list[str]:
    arena_lines, regular_lines, inverted_lines = [], set(), set()
    for i, line in enumerate(lines):
        if _is_about_line(line) and i < len(lines) - 1:
            if _is_name_line(lines[i + 1]):
                arena_lines.append("About")
                if "Deck" in arena_lines:
                    arena_lines.remove("Deck")
        elif _is_name_line(line) and i > 0:
            if _is_about_line(lines[i - 1]):
                arena_lines.append(line)
        elif _is_maindeck_line(line):
            if "Deck" not in arena_lines:
                arena_lines.append("Deck")
        elif _is_commander_line(line):
            if "Commander" not in arena_lines:
                arena_lines.append("Commander")
                if "Deck" in arena_lines:
                    arena_lines.remove("Deck")
        elif _is_companion_line(line):
            if "Companion" not in arena_lines:
                arena_lines.append("Companion")
                if "Deck" in arena_lines:
                    arena_lines.remove("Deck")
        elif _is_playset_line(line):
            if not arena_lines:
                if i < len(lines) - 3 and any(_is_maindeck_line(l) for l in lines[i + 1:i + 4]):
                    arena_lines.append("Commander")
                else:
                    arena_lines.append("Deck")
            if bool(PlaysetLine.INVERTED_PATTERN.match(line)):
                inverted_lines.add(line)
            else:
                regular_lines.add(line)
            arena_lines.append(line)
        elif _is_sideboard_line(line):
            if "Sideboard" not in arena_lines:
                arena_lines.append("Sideboard")
        elif (is_empty(line)
              and 1 < i < len(lines) - 1
              and _is_playset_line(lines[i - 2])  # previous previous line
              and _is_playset_line(lines[i - 1])  # previous line
              and (_is_playset_line(lines[i + 1]) or _is_sideboard_line(lines[i + 1]))):  # next line
            if not _is_sideboard_line(lines[i + 1]) and "Sideboard" not in arena_lines:
                arena_lines.append("Sideboard")

    # return either inverted or regular playset lines, but not both
    if len(inverted_lines) > len(regular_lines):
        arena_lines = [l for l in arena_lines if l not in regular_lines]
    else:
        arena_lines = [l for l in arena_lines if l not in inverted_lines]

    # trim empty "Commander"
    if len(arena_lines) >= 2 and arena_lines[:2] == ["Commander", "Deck"]:
        return arena_lines[1:]
    return arena_lines


def group_arena_lines(*arena_lines: str) -> Generator[list[str], None, None]:
    current_group, about_on, commander_on, companion_on = [], False, False, False
    for line in arena_lines:
        if _is_about_line(line):
            about_on = True
            if current_group and not (commander_on or companion_on):
                yield current_group
                current_group = []  # reset
        elif _is_commander_line(line):
            commander_on = True
            if current_group and not (companion_on or about_on):
                yield current_group
                current_group = []  # reset
        elif _is_companion_line(line):
            companion_on = True
            if current_group and not (commander_on or about_on):
                yield current_group
                current_group = []  # reset
        elif _is_maindeck_line(line):
            if current_group and not (commander_on or companion_on or about_on):
                about_on, commander_on, companion_on = False, False, False
                yield current_group
                current_group = []  # reset
        current_group.append(line)
    if current_group:
        yield current_group


def is_arena_decklist(decklist: str) -> bool:
    return all(is_arena_line(l) or is_empty(l) for l in decklist.splitlines())


class IllFormedArenaDecklist(ParsingError):
    """Raised on no ill-formed Arena decklists being parsed as one.
    """


class ArenaParser(DeckParser):
    """Parser of lines of text that denote a deck in Arena format.
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
        self._lines = get_arena_lines(*self._lines)
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
