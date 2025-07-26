"""

    mtg.deck.arena
    ~~~~~~~~~~~~~~
    Parse Arena/MTGO decklist text format.

    @author: z33k

"""
import logging
import re
from typing import Generator, override

from mtg import Json
from mtg.deck import ARENA_MULTIFACE_SEPARATOR, CardNotFound, DeckParser
from mtg.scryfall import COMMANDER_FORMATS, Card, \
    MULTIFACE_SEPARATOR as SCRYFALL_MULTIFACE_SEPARATOR, \
    query_api_for_card
from mtg.utils import ParsingError, extract_int, getrepr, sanitize_whitespace, is_foreign

_log = logging.getLogger(__name__)

# pilfered from: https://stackoverflow.com/questions/36187349/python-regex-for-unicode-capitalized-words
_ALL_UPPERCASE = (
    "[\"_A-Z\u00C0-\u00D6\u00D8-\u00DE\u0100\u0102\u0104\u0106\u0108\u010A\u010C\u010E\u0110\u0112"
    "\u0114\u0116\u0118\u011A\u011C\u011E\u0120\u0122\u0124\u0126\u0128\u012A\u012C\u012E\u0130"
    "\u0132\u0134\u0136\u0139\u013B\u013D\u013F\u0141\u0143\u0145\u0147\u014A\u014C\u014E\u0150"
    "\u0152\u0154\u0156\u0158\u015A\u015C\u015E\u0160\u0162\u0164\u0166\u0168\u016A\u016C\u016E"
    "\u0170\u0172\u0174\u0176\u0178\u0179\u017B\u017D\u0181\u0182\u0184\u0186\u0187\u0189-\u018B"
    "\u018E-\u0191\u0193\u0194\u0196-\u0198\u019C\u019D\u019F\u01A0\u01A2\u01A4\u01A6\u01A7\u01A9"
    "\u01AC\u01AE\u01AF\u01B1-\u01B3\u01B5\u01B7\u01B8\u01BC\u01C4\u01C7\u01CA\u01CD\u01CF\u01D1"
    "\u01D3\u01D5\u01D7\u01D9\u01DB\u01DE\u01E0\u01E2\u01E4\u01E6\u01E8\u01EA\u01EC\u01EE\u01F1"
    "\u01F4\u01F6-\u01F8\u01FA\u01FC\u01FE\u0200\u0202\u0204\u0206\u0208\u020A\u020C\u020E\u0210"
    "\u0212\u0214\u0216\u0218\u021A\u021C\u021E\u0220\u0222\u0224\u0226\u0228\u022A\u022C\u022E"
    "\u0230\u0232\u023A\u023B\u023D\u023E\u0241\u0243-\u0246\u0248\u024A\u024C\u024E\u0370\u0372"
    "\u0376\u037F\u0386\u0388-\u038A\u038C\u038E\u038F\u0391-\u03A1\u03A3-\u03AB\u03CF\u03D2-"
    "\u03D4\u03D8\u03DA\u03DC\u03DE\u03E0\u03E2\u03E4\u03E6\u03E8\u03EA\u03EC\u03EE\u03F4\u03F7"
    "\u03F9\u03FA\u03FD-\u042F\u0460\u0462\u0464\u0466\u0468\u046A\u046C\u046E\u0470\u0472\u0474"
    "\u0476\u0478\u047A\u047C\u047E\u0480\u048A\u048C\u048E\u0490\u0492\u0494\u0496\u0498\u049A"
    "\u049C\u049E\u04A0\u04A2\u04A4\u04A6\u04A8\u04AA\u04AC\u04AE\u04B0\u04B2\u04B4\u04B6\u04B8"
    "\u04BA\u04BC\u04BE\u04C0\u04C1\u04C3\u04C5\u04C7\u04C9\u04CB\u04CD\u04D0\u04D2\u04D4\u04D6"
    "\u04D8\u04DA\u04DC\u04DE\u04E0\u04E2\u04E4\u04E6\u04E8\u04EA\u04EC\u04EE\u04F0\u04F2\u04F4"
    "\u04F6\u04F8\u04FA\u04FC\u04FE\u0500\u0502\u0504\u0506\u0508\u050A\u050C\u050E\u0510\u0512"
    "\u0514\u0516\u0518\u051A\u051C\u051E\u0520\u0522\u0524\u0526\u0528\u052A\u052C\u052E\u0531-"
    "\u0556\u10A0-\u10C5\u10C7\u10CD\u13A0-\u13F5\u1E00\u1E02\u1E04\u1E06\u1E08\u1E0A\u1E0C\u1E0E"
    "\u1E10\u1E12\u1E14\u1E16\u1E18\u1E1A\u1E1C\u1E1E\u1E20\u1E22\u1E24\u1E26\u1E28\u1E2A\u1E2C"
    "\u1E2E\u1E30\u1E32\u1E34\u1E36\u1E38\u1E3A\u1E3C\u1E3E\u1E40\u1E42\u1E44\u1E46\u1E48\u1E4A"
    "\u1E4C\u1E4E\u1E50\u1E52\u1E54\u1E56\u1E58\u1E5A\u1E5C\u1E5E\u1E60\u1E62\u1E64\u1E66\u1E68"
    "\u1E6A\u1E6C\u1E6E\u1E70\u1E72\u1E74\u1E76\u1E78\u1E7A\u1E7C\u1E7E\u1E80\u1E82\u1E84\u1E86"
    "\u1E88\u1E8A\u1E8C\u1E8E\u1E90\u1E92\u1E94\u1E9E\u1EA0\u1EA2\u1EA4\u1EA6\u1EA8\u1EAA\u1EAC"
    "\u1EAE\u1EB0\u1EB2\u1EB4\u1EB6\u1EB8\u1EBA\u1EBC\u1EBE\u1EC0\u1EC2\u1EC4\u1EC6\u1EC8\u1ECA"
    "\u1ECC\u1ECE\u1ED0\u1ED2\u1ED4\u1ED6\u1ED8\u1EDA\u1EDC\u1EDE\u1EE0\u1EE2\u1EE4\u1EE6\u1EE8"
    "\u1EEA\u1EEC\u1EEE\u1EF0\u1EF2\u1EF4\u1EF6\u1EF8\u1EFA\u1EFC\u1EFE\u1F08-\u1F0F\u1F18-\u1F1D"
    "\u1F28-\u1F2F\u1F38-\u1F3F\u1F48-\u1F4D\u1F59\u1F5B\u1F5D\u1F5F\u1F68-\u1F6F\u1FB8-\u1FBB"
    "\u1FC8-\u1FCB\u1FD8-\u1FDB\u1FE8-\u1FEC\u1FF8-\u1FFB\u2102\u2107\u210B-\u210D\u2110-\u2112"
    "\u2115\u2119-\u211D\u2124\u2126\u2128\u212A-\u212D\u2130-\u2133\u213E\u213F\u2145\u2160-\u216F"
    "\u2183\u24B6-\u24CF\u2C00-\u2C2E\u2C60\u2C62-\u2C64\u2C67\u2C69\u2C6B\u2C6D-\u2C70\u2C72\u2C75"
    "\u2C7E-\u2C80\u2C82\u2C84\u2C86\u2C88\u2C8A\u2C8C\u2C8E\u2C90\u2C92\u2C94\u2C96\u2C98\u2C9A"
    "\u2C9C\u2C9E\u2CA0\u2CA2\u2CA4\u2CA6\u2CA8\u2CAA\u2CAC\u2CAE\u2CB0\u2CB2\u2CB4\u2CB6\u2CB8"
    "\u2CBA\u2CBC\u2CBE\u2CC0\u2CC2\u2CC4\u2CC6\u2CC8\u2CCA\u2CCC\u2CCE\u2CD0\u2CD2\u2CD4\u2CD6"
    "\u2CD8\u2CDA\u2CDC\u2CDE\u2CE0\u2CE2\u2CEB\u2CED\u2CF2\uA640\uA642\uA644\uA646\uA648\uA64A"
    "\uA64C\uA64E\uA650\uA652\uA654\uA656\uA658\uA65A\uA65C\uA65E\uA660\uA662\uA664\uA666\uA668"
    "\uA66A\uA66C\uA680\uA682\uA684\uA686\uA688\uA68A\uA68C\uA68E\uA690\uA692\uA694\uA696\uA698"
    "\uA69A\uA722\uA724\uA726\uA728\uA72A\uA72C\uA72E\uA732\uA734\uA736\uA738\uA73A\uA73C\uA73E"
    "\uA740\uA742\uA744\uA746\uA748\uA74A\uA74C\uA74E\uA750\uA752\uA754\uA756\uA758\uA75A\uA75C"
    "\uA75E\uA760\uA762\uA764\uA766\uA768\uA76A\uA76C\uA76E\uA779\uA77B\uA77D\uA77E\uA780\uA782"
    "\uA784\uA786\uA78B\uA78D\uA790\uA792\uA796\uA798\uA79A\uA79C\uA79E\uA7A0\uA7A2\uA7A4\uA7A6"
    "\uA7A8\uA7AA-\uA7AE\uA7B0-\uA7B4\uA7B6\uFF21-\uFF3A\U00010400-\U00010427\U000104B0-"
    "\U000104D3\U00010C80-\U00010CB2\U000118A0-\U000118BF\U0001D400-\U0001D419\U0001D434-"
    "\U0001D44D\U0001D468-\U0001D481\U0001D49C\U0001D49E\U0001D49F\U0001D4A2\U0001D4A5\U0001D4A6"
    "\U0001D4A9-\U0001D4AC\U0001D4AE-\U0001D4B5\U0001D4D0-\U0001D4E9\U0001D504\U0001D505"
    "\U0001D507-\U0001D50A\U0001D50D-\U0001D514\U0001D516-\U0001D51C\U0001D538\U0001D539"
    "\U0001D53B-\U0001D53E\U0001D540-\U0001D544\U0001D546\U0001D54A-\U0001D550\U0001D56C-"
    "\U0001D585\U0001D5A0-\U0001D5B9\U0001D5D4-\U0001D5ED\U0001D608-\U0001D621\U0001D63C-"
    "\U0001D655\U0001D670-\U0001D689\U0001D6A8-\U0001D6C0\U0001D6E2-\U0001D6FA\U0001D71C-"
    "\U0001D734\U0001D756-\U0001D76E\U0001D790-\U0001D7A8\U0001D7CA\U0001E900-\U0001E921"
    "\U0001F130-\U0001F149\U0001F150-\U0001F169\U0001F170-\U0001F189]")


class PlaysetLine:
    """A line of text in MtG Arena decklist format that denotes a card playset.

    Example:
        '4 Commit /// Memory (AKR) 54'
    """
    # matches '4 Commit /// Memory' or '4x Commit /// Memory'
    PATTERN = re.compile("^\\d{1,3}\\s?x?\\s" + _ALL_UPPERCASE + "[\\w\\s'\"&/,.!:_-]+")
    # matches 'Commit /// Memory 4' or 'Commit /// Memory x4'
    INVERTED_PATTERN = re.compile("^" + _ALL_UPPERCASE + "[\\w\\s'\"&/,.!:_-]+\\sx?\\s?\\d{1,3}$")
    # matches '4 Commit /// Memory (AKR) 54' or '4x Commit /// Memory (AKR) 54'
    EXTENDED_PATTERN = re.compile(
        "^\\d{1,3}\\s?x?\\s" + _ALL_UPPERCASE +
        "[\\w\\s'\"&/,.!:_-]+\\s+\\([A-Za-z\\d]{3,6}\\)\\s+[A-Za-z\\d]{1,6}")

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
        "Deck List", "Mazo", "Mallet")


def _is_commander_line(line: str) -> bool:
    return _is_section_line(line, "Commander", "Comandante")


def _is_companion_line(line: str) -> bool:
    return _is_section_line(line, "Companion", "Companheiro")


def _is_sideboard_line(line: str) -> bool:
    return _is_section_line(
        line, "Side", "Sideboard", "Sidedeck", "Sidelist", "Reserva", "Side Board", "Side Deck",
        "Side List")


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
