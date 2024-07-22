"""

    mtgcards.scryfall.py
    ~~~~~~~~~~~~~~~~~~~
    Handle Scryfall data.

    @author: z33k

"""
import json
import math
import re
from collections import defaultdict, namedtuple
from dataclasses import dataclass
from datetime import date
from enum import Enum
from functools import cached_property, lru_cache
from pprint import pprint
from types import EllipsisType
from typing import Callable, Iterable, Optional

import scrython

from mtgcards.const import DATADIR, Json
from mtgcards.mtgwiki import CLASSES, RACES
from mtgcards.utils import from_iterable, getrepr, parse_int_from_str
from mtgcards.utils.files import download_file, getdir

FILENAME = "scryfall.json"


class ScryfallError(ValueError):
    """Raised on invalid Scryfall data.
    """


def download_scryfall_bulk_data() -> None:
    """Download Scryfall 'Oracle Cards' bulk data JSON.
    """
    bd = scrython.BulkData()
    data = bd.data()[0]  # retrieve 'Oracle Cards' data dict
    url = data["download_uri"]
    download_file(url, file_name=FILENAME, dst_dir=DATADIR)


MULTIPART_SEPARATOR = "//"  # separates parts of card's name in multipart cards
MULTIPART_LAYOUTS = ('adventure', 'art_series', 'double_faced_token', 'flip', 'modal_dfc', 'split',
                     'transform')

# all cards that got Alchemy rebalance treatment have their rebalanced counterparts with names
# prefixed by 'A-'
ALCHEMY_REBALANCE_INDICATOR = "A-"


class Color(Enum):
    COLORLESS = ()  # technically, not a color
    # singletons
    WHITE = ("W",)
    BLUE = ("U",)
    BLACK = ("B",)
    RED = ("R",)
    GREEN = ("G",)
    # pairs
    GOLGARI = ("B", "G")
    RAKDOS = ("B", "R")
    DIMIR = ("B", "U")
    ORZHOV = ("B", "W")
    GRUUL = ("G", "R")
    SIMIC = ("G", "U")
    SELESNYA = ("G", "W")
    IZZET = ("R", "U")
    BOROS = ("R", "W")
    AZORIUS = ("U", "W")
    # triples
    JUND = ("B", "G", "R")
    SULTAI = ("B", "G", "U")
    ABZAN = ("B", "G", "W")
    GRIXIS = ("B", "R", "U")
    MARDU = ("B", "R", "W")
    ESPER = ("B", "U", "W")
    TEMUR = ("G", "R", "U")
    NAYA = ("G", "R", "W")
    BANT = ("G", "U", "W")
    JESKAI = ("R", "U", "W")
    # quadruples
    CHAOS = ("B", "G", "R", "U")
    AGGRESSION = ("B", "G", "R", "W")
    GROWTH = ("B", "G", "U", "W")
    ARTIFICE = ("B", "R", "U", "W")
    ALTRUISM = ("G", "R", "U", "W")
    # other
    ALL = ("B", "G", "R", "U", "W")

    @property
    def is_multi(self) -> bool:
        return len(self.value) > 1

    @staticmethod
    def from_letters(letters: Iterable[str]) -> "Color":
        letters = [*letters]
        if (any(letter not in Color.ALL.value for letter in letters)
                or any(letters.count(letter) > 1 for letter in letters)):
            raise ValueError(f"Invalid color letter designations: {letters}")
        relevant_colors = [color for color in Color if len(color.value) == len(letters)]
        if not relevant_colors:
            raise ValueError(f"Invalid number of color letter designation. Must be 1-5, "
                             f"got {len(letters)}")
        result = from_iterable(relevant_colors,
                               lambda color: all(letter in color.value for letter in letters))
        if not result:
            raise ValueError(f"No color for designations: {letters}")
        return result

    @staticmethod
    def from_cards(cards: Iterable["Card"]) -> "Color":
        letters = set()
        for card in cards:
            letters.update(card.color_identity.value)
        return Color.from_letters(letters)


class Rarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    MYTHIC = "mythic"
    SPECIAL = "special"
    BONUS = "bonus"

    @property
    def weight(self) -> float | None:
        """Return fractional weight of this rarity based on frequency of occurrence in boosters.

        Based on: https://mtg.fandom.com/wiki/Rarity
        """
        if self is Rarity.MYTHIC:
            return 1 / (1 / 15 * 1 / 8)  # 120.00
        if self is Rarity.RARE:
            return 1 / (1 / 15 * 7 / 8)  # 17.14
        if self is Rarity.UNCOMMON:
            return 1 / (1 / 15 * 3)  # 5.00
        if self is Rarity.COMMON:
            return 1 / (1 / 15 * 11)  # 1.36
        return None

    @property
    def is_special(self) -> bool:
        return self is Rarity.SPECIAL or self is Rarity.BONUS


class TypeLine:
    """Parser of type line in Scryfall data.
    """
    SEPARATOR = "—"

    SUPERTYPES = {"Basic", "Elite", "Host", "Legendary", "Ongoing", "Snow", "Token", "Tribal",
                  "World"}
    PERMANENT_TYPES = {"Artifact", "Battle", "Creature", "Enchantment", "Land", "Planeswalker"}
    NONPERMANENT_TYPES = {"Sorcery", "Instant"}

    @property
    def text(self) -> str:
        return self._text

    @property
    def supertypes(self) -> list[str]:
        return [t for t in self._types if t in self.SUPERTYPES]

    @property
    def regular_types(self) -> list[str]:
        return [t for t in self._types if t not in self.SUPERTYPES]

    @property
    def subtypes(self) -> list[str]:
        return self._subtypes

    @property
    def is_permanent(self) -> bool:
        return all(p in self.PERMANENT_TYPES for p in self.regular_types)

    @property
    def is_nonpermanent(self) -> bool:
        # type not being permanent doesn't mean it's 'non-permanent', e.g. 'dungeon' is neither
        return all(p in self.NONPERMANENT_TYPES for p in self.regular_types)

    @property
    def is_artifact(self) -> bool:
        return "Artifact" in self.regular_types

    @property
    def is_creature(self) -> bool:
        return "Creature" in self.regular_types

    @property
    def is_enchantment(self) -> bool:
        return "Enchantment" in self.regular_types

    @property
    def is_instant(self) -> bool:
        return "Instant" in self.regular_types

    @property
    def is_land(self) -> bool:
        return "Land" in self.regular_types

    @property
    def is_planeswalker(self) -> bool:
        return "Planeswalker" in self.regular_types

    @property
    def is_sorcery(self) -> bool:
        return "Sorcery" in self.regular_types

    @property
    def races(self) -> list[str]:
        return [t for t in self.subtypes if t in RACES]

    @property
    def classes(self) -> list[str]:
        return [t for t in self.subtypes if t in CLASSES]

    def __init__(self, text: str) -> None:
        if MULTIPART_SEPARATOR in text:
            raise ValueError("Multipart type line")
        self._text = text
        self._types, self._subtypes = self._parse()

    def _parse(self) -> tuple[list[str], list[str]]:
        """Parse text into types and subtypes.
        """
        if self.SEPARATOR in self.text:
            types, subtypes = self.text.split(f" {self.SEPARATOR} ", maxsplit=1)
            return types.split(), subtypes.split()
        return self.text.split(), []


class LordSentence:
    """Parser of 'lord'-effect related part of card's Oracle text.

    More on lords:  https://mtg.fandom.com/wiki/Lord

    A proper input should be a single isolated sentence (stripped of the trailing dot) from the
    whole bulk of any given card's Oracle text, e.g. for 'Leaf-Crowned Visionary' the relevant
    part is:

        'Other Elves you control get +1/+1'

    """
    PATTERN = re.compile(r".*(\bget\s\+[\dX]/\+[\dX]\b).*")

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def buff(self) -> str:
        return self._buff

    @property
    def suffix(self) -> str:
        return self._suffix

    @property
    def is_valid(self) -> bool:
        return bool(self.buff)

    def __init__(self, text: str) -> None:
        self._text = text
        self._prefix, self._buff, self._suffix = self._parse()

    def _parse(self) -> tuple[str, str, str]:
        match = self.PATTERN.match(self._text)
        if match:
            prefix, suffix = self._text.split(match.group(1), maxsplit=1)
            return prefix.strip(), match.group(1), suffix.strip()
        return "", "", ""


# TODO: make Card inherit from CardFace
@dataclass(frozen=True)
class CardFace:
    """Thin wrapper on card face data that lives inside Scryfall card data.

    Somewhat similar to regular card but much simpler.
    """
    json: Json

    def __eq__(self, other: "Card") -> bool:
        left = self.name, self.mana_cost, self.type_line, self.oracle_text
        right = other.name, other.mana_cost, other.type_line, other.oracle_text
        return left == right

    def __hash__(self) -> int:
        return hash((self.name, self.mana_cost, self.type_line, self.oracle_text))

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        return self.json["name"]

    @property
    def name_parts(self) -> set[str]:
        return {*self.name.split()}

    @property
    def mana_cost(self) -> str:
        return self.json["mana_cost"]

    @property
    def type_line(self) -> str | None:
        return self.json.get("type_line")

    @property
    def oracle_text(self) -> str:
        return self.json["oracle_text"]

    @property
    def colors(self) -> list[str]:
        result = self.json.get("colors")
        return result if result else []

    @lru_cache
    def parse_types(self) -> TypeLine | None:
        return TypeLine(self.type_line) if self.type_line else None

    @property
    def supertypes(self) -> list[str]:
        return self.parse_types().supertypes if self.parse_types() else []

    @property
    def regular_types(self) -> list[str]:
        return self.parse_types().regular_types if self.parse_types() else []

    @property
    def subtypes(self) -> list[str]:
        return self.parse_types().subtypes if self.parse_types() else []

    @property
    def races(self) -> list[str]:
        return self.parse_types().races if self.parse_types() else []

    @property
    def classes(self) -> list[str]:
        return self.parse_types().classes if self.parse_types() else []

    @cached_property
    def lord_sentences(self) -> list[LordSentence]:
        return Card.parse_lord_sentences(self.oracle_text)

    @property
    def loyalty(self) -> str | None:
        return self.json.get("loyalty")

    @property
    def loyalty_int(self) -> int | None:
        return parse_int_from_str(self.loyalty) if self.loyalty is not None else None

    @property
    def has_special_loyalty(self) -> bool:
        return self.loyalty is not None and self.loyalty_int is None

    @property
    def power(self) -> int | None:
        return self.json.get("power")

    @property
    def power_int(self) -> int | None:
        return parse_int_from_str(self.power) if self.power is not None else None

    @property
    def has_special_power(self) -> bool:
        return self.power is not None and self.power_int is None

    @property
    def toughness(self) -> str | None:
        return self.json.get("toughness")

    @property
    def toughness_int(self) -> int | None:
        return parse_int_from_str(self.toughness) if self.toughness is not None else None

    @property
    def has_special_toughness(self) -> bool:
        return self.toughness is not None and self.toughness_int is None


@dataclass(frozen=True)
class Card:
    """Thin wrapper on Scryfall JSON data for an MtG card.

    Provides convenience access to the most important data pieces.
    """
    json: Json

    def __eq__(self, other: "Card") -> bool:
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __str__(self) -> str:
        text = f"{self.name} ({self.set.upper()})"
        if self.collector_number:
            text += f" {self.collector_number}"
        return text

    def __repr__(self) -> str:
        return getrepr(self.__class__, ("name", self.name), ("set", self.set),
                       ("collector_number", self.collector_number))

    def __post_init__(self) -> None:
        if self.is_multipart and self.card_faces is None:
            raise ScryfallError(f"Card faces data missing for multipart card {self.name!r}")
        if self.is_multipart and self.layout not in MULTIPART_LAYOUTS:
            raise ScryfallError(f"Invalid layout {self.layout!r} for multipart card {self.name!r}")

    @property
    def card_faces(self) -> list[CardFace]:
        data = self.json.get("card_faces")
        if data is None:
            return []
        return [CardFace(item) for item in data]

    @property
    def cmc(self) -> int:
        return math.ceil(self.json["cmc"])

    @property
    def color_identity(self) -> Color:
        # 'color_identity' is a wider term than 'colors' (that only take mana cost into account)
        # more on this here: https://mtg.fandom.com/wiki/Color_identity
        return Color(tuple(self.json["color_identity"]))

    @property
    def colors(self) -> list[str]:
        result = self.json.get("colors")
        return result if result else []

    @property
    def collector_number(self) -> str:
        return self.json["collector_number"]

    @property
    def collector_number_int(self) -> int | None:
        """Return collector number as an integer, if it can be parsed as such.

        .. note: Parsing logic strips any non-digits and then parses a number. This means that
        some alternative versions (e.g. Alchemy variants) will have the same number. However,
        it needs to be this way, because there are some basic cards that still have the collector
        number in this format (for instance both parts of Meld pairs from BRO).

        `collector_number` can look like that:
            {"12e", "67f", "233f", "A-268", "4e"}
        """
        cn = "".join(char for char in self.collector_number if char.isdigit())
        return parse_int_from_str(cn)

    @property
    def formats(self) -> list[str]:
        """Return list of all Scryfall string format designations.
        """
        return sorted(fmt for fmt in self.legalities)

    @property
    def games(self) -> list[str]:
        return self.json["games"]

    @property
    def id(self) -> str:
        return self.json["id"]

    @property
    def keywords(self) -> list[str]:
        return self.json["keywords"]

    @property
    def layout(self) -> str:
        return self.json["layout"]

    @property
    def legalities(self) -> dict[str, str]:
        return self.json["legalities"]

    @property
    def loyalty(self) -> str | None:
        return self.json.get("loyalty")

    @property
    def loyalty_int(self) -> int | None:
        return parse_int_from_str(self.loyalty) if self.loyalty is not None else None

    @property
    def has_special_loyalty(self) -> bool:
        return self.loyalty is not None and self.loyalty_int is None

    @property
    def mana_cost(self) -> str | None:
        return self.json.get("mana_cost")

    @property
    def oracle_text(self) -> str | None:
        return self.json.get("oracle_text")

    @property
    def name(self) -> str:
        return self.json["name"]

    @property
    def name_parts(self) -> set[str]:
        if not self.is_multipart:
            return {*self.name.split()}
        return {part for face in self.card_faces for part in face.name_parts}

    @property
    def main_name(self) -> str:
        return self.card_faces[0].name if self.is_multipart else self.name

    @property
    def power(self) -> int | None:
        return self.json.get("power")

    @property
    def power_int(self) -> int | None:
        return parse_int_from_str(self.power) if self.power is not None else None

    @property
    def has_special_power(self) -> bool:
        return self.power is not None and self.power_int is None

    @property
    def price(self) -> float | None:
        """Return price in USD or `None` if unavailable.
        """
        return self.json["prices"].get("usd")

    @property
    def rarity(self) -> Rarity:
        return Rarity(self.json["rarity"])

    @property
    def has_special_rarity(self) -> bool:
        return self.rarity.is_special

    @property
    def is_common(self) -> bool:
        return self.rarity is Rarity.COMMON

    @property
    def is_uncommon(self) -> bool:
        return self.rarity is Rarity.UNCOMMON

    @property
    def is_rare(self) -> bool:
        return self.rarity is Rarity.RARE

    @property
    def is_mythic(self) -> bool:
        return self.rarity is Rarity.MYTHIC

    @property
    def released_at(self) -> date:
        return date.fromisoformat(self.json["released_at"])

    @property
    def reprint(self) -> bool:
        return self.json["reprint"]

    @property
    def set(self) -> str:
        return self.json["set"]

    @property
    def set_name(self) -> str:
        return self.json["set_name"]

    @property
    def set_type(self) -> str:
        return self.json["set_type"]

    @property
    def toughness(self) -> str | None:
        return self.json.get("toughness")

    @property
    def toughness_int(self) -> int | None:
        return parse_int_from_str(self.toughness) if self.toughness is not None else None

    @property
    def has_special_toughness(self) -> bool:
        return self.toughness is not None and self.toughness_int is None

    @property
    def type_line(self) -> str:
        return self.json["type_line"]

    @property
    def is_multipart(self) -> bool:
        return MULTIPART_SEPARATOR in self.name

    def is_legal_in(self, fmt: str) -> bool:
        """Returns `True` if this card is legal in format designated by `fmt`.

        Run formats() to see available format designations.

        :param fmt: Scryfall format designation
        :raises: ValueError on invalid format designation
        """
        if fmt.lower() not in self.formats:
            raise ValueError(f"No such format: {fmt!r}")

        if self.legalities[fmt] == "legal":
            return True
        return False

    def is_banned_in(self, fmt: str) -> bool:
        """Returns `True` if this card is banned in format designated by `fmt`.

        Run formats() to see available format designations.

        :param fmt: Scryfall format designation
        :raises: ValueError on invalid format designation
        """
        if fmt.lower() not in self.formats:
            raise ValueError(f"No such format: {fmt!r}")

        if self.legalities[fmt] == "banned":
            return True
        return False

    def is_restricted_in(self, fmt: str) -> bool:
        """Returns `True` if this card is restricted in format designated by `fmt`.

        Run formats() to see available format designations.

        :param fmt: Scryfall format designation
        :raises: ValueError on invalid format designation
        """
        if fmt.lower() not in self.formats:
            raise ValueError(f"No such format: {fmt!r}")

        if self.legalities[fmt] == "restricted":
            return True
        return False

    @lru_cache
    def parse_types(self) -> TypeLine | None:
        if self.is_multipart:
            return None
        return TypeLine(self.type_line)

    @property
    def supertypes(self) -> list[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.supertypes})
        return self.parse_types().supertypes

    @property
    def regular_types(self) -> list[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.regular_types})
        return self.parse_types().regular_types

    @property
    def is_artifact(self) -> bool:
        return "Artifact" in self.regular_types

    @property
    def is_creature(self) -> bool:
        return "Creature" in self.regular_types

    @property
    def is_battle(self) -> bool:
        return "Battle" in self.regular_types

    @property
    def is_enchantment(self) -> bool:
        return "Enchantment" in self.regular_types

    @property
    def is_instant(self) -> bool:
        return "Instant" in self.regular_types

    @property
    def is_land(self) -> bool:
        return "Land" in self.regular_types

    @property
    def is_basic_land(self) -> bool:
        return "Land" in self.regular_types and "Basic" in self.supertypes

    @property
    def is_planeswalker(self) -> bool:
        return "Planeswalker" in self.regular_types

    @property
    def is_sorcery(self) -> bool:
        return "Sorcery" in self.regular_types

    @property
    def subtypes(self) -> list[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.subtypes})
        return self.parse_types().subtypes

    @property
    def races(self) -> list[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.races})
        return self.parse_types().races

    @property
    def classes(self) -> list[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.classes})
        return self.parse_types().classes

    @property
    def is_permanent(self) -> bool:
        if self.is_multipart:
            return all(face.parse_types().is_permanent for face in self.card_faces)
        return self.parse_types().is_permanent

    @property
    def is_nonpermanent(self) -> bool:
        if self.is_multipart:
            return all(face.parse_types().is_nonpermanent for face in self.card_faces)
        return self.parse_types().is_nonpermanent

    @property
    def is_alchemy_rebalance(self) -> bool:
        return self.name.startswith(ALCHEMY_REBALANCE_INDICATOR)

    @cached_property
    def alchemy_rebalance(self) -> Optional["Card"]:
        """Find Alchemy rebalanced version of this card and return it, or 'None' if there's no
        such card.
        """
        return find_by_name(f"{ALCHEMY_REBALANCE_INDICATOR}{self.name}")

    @property
    def alchemy_rebalance_original(self) -> Optional["Card"]:
        """If this card is Alchemy rebalance, return the original card. Return 'None' otherwise.
        """
        if not self.is_alchemy_rebalance:
            return None
        if not self.is_multipart:
            return find_by_name(self.name[2:])
        # is multipart
        first_part_name, *_ = self.name.split(MULTIPART_SEPARATOR)
        original_name = first_part_name[2:]
        original = from_iterable(
            self.json["all_parts"],
            lambda p: original_name in p["name"] and not p["name"].startswith(
                ALCHEMY_REBALANCE_INDICATOR)
        )
        if original:
            return find_by_name(original["name"])
        return None

    @property
    def has_alchemy_rebalance(self) -> bool:
        return self.alchemy_rebalance is not None

    @staticmethod
    def parse_lord_sentences(oracle_text: str) -> list[LordSentence]:
        if not oracle_text:
            return []
        lord_sentences = []
        for sentence in oracle_text.split("."):
            lord_sentence = LordSentence(sentence)
            if lord_sentence.is_valid:
                lord_sentences.append(lord_sentence)
        return lord_sentences

    @cached_property
    def lord_sentences(self) -> list[LordSentence]:
        sentences = []
        if self.is_multipart:
            for face in self.card_faces:
                sentences += face.lord_sentences
            return sentences
        return self.parse_lord_sentences(self.oracle_text)

    @property
    def allowed_multiples(self) -> int | EllipsisType | None:
        if not self.oracle_text:
            return None
        if "deck can have any number of cards named" in self.oracle_text:
            return Ellipsis
        if "deck can have up to one" in self.oracle_text:
            return 1
        if "deck can have up to two" in self.oracle_text:
            return 2
        if "deck can have up to three" in self.oracle_text:
            return 3
        if "deck can have up to four" in self.oracle_text:
            return 4
        if "deck can have up to five" in self.oracle_text:
            return 5
        if "deck can have up to six" in self.oracle_text:
            return 6
        if "deck can have up to seven" in self.oracle_text:  # Seven Dwarves
            return 7
        if "deck can have up to eight" in self.oracle_text:
            return 8
        if "deck can have up to nine" in self.oracle_text:  # Nazgul
            return 9
        if "deck can have up to ten" in self.oracle_text:
            return 10
        if "deck can have up to eleven" in self.oracle_text:
            return 11
        if "deck can have up to twelve" in self.oracle_text:
            return 12
        return None


@lru_cache
def bulk_data() -> set[Card]:
    """Return Scryfall JSON data as set of Card objects.
    """
    source = getdir(DATADIR) / FILENAME
    if not source.exists():
        download_scryfall_bulk_data()

    with source.open() as f:
        data = json.load(f)

    return {Card(card_data) for card_data in data}


def games(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of string designations for games that can be played with cards in Scryfall data.
    """
    data = data if data else bulk_data()
    result = set()
    for card in data:
        result.update(card.games)

    return sorted(result)


def colors(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of string designations for MtG colors in Scryfall data.
    """
    data = data if data else bulk_data()
    result = set()
    for card in data:
        result.update(card.colors)
    return sorted(result)


def sets(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of string codes for MtG sets in Scryfall data (e.g. 'bro' for The Brothers'
    War).
    """
    data = data if data else bulk_data()
    return sorted({card.set for card in data})


def formats() -> list[str]:
    """Return list of string designations for MtG formats in Scryfall data.
    """
    return next(iter(bulk_data())).formats


def layouts(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of Scryfall string designations for card layouts in ``data``.
    """
    data = data if data else bulk_data()
    return sorted({card.layout for card in data})


def set_names(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of MtG set names in Scryfall data.
    """
    data = data if data else bulk_data()
    return sorted({card.set_name for card in data})


def rarities(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of MtG card rarities in Scryfall data.
    """
    data = data if data else bulk_data()
    return sorted({card.rarity.value for card in data})


def keywords(data: Iterable[Card] | None = None) -> list[str]:
    """Return list of MtG card keywords in Scryfall data.
    """
    data = data if data else bulk_data()
    result = set()
    for card in data:
        result.update(card.keywords)
    return sorted(result)


def find_cards(
        predicate: Callable[[Card], bool], data: Iterable[Card] | None = None) -> set[Card]:
    """Return list of cards from ``data`` that satisfy ``predicate``.
    """
    data = data if data else bulk_data()
    return {card for card in data if predicate(card)}


def set_cards(*set_codes: str, data: Iterable[Card] | None = None) -> set[Card]:
    """Return card data for sets designated by ``set_codes``.

    Run sets() to see available set codes.
    """
    return find_cards(lambda c: c.set in [code.lower() for code in set_codes], data)


@lru_cache
def arena_cards() -> set[Card]:
    """Return Scryfall bulk data filtered for only cards available on Arena.
    """
    return find_cards(lambda c: "arena" in c.games)


@lru_cache
def format_cards(fmt: str, data: Iterable[Card] | None = None) -> set[Card]:
    """Return card data for MtG format designated by ``fmt``.

    Run formats() to see available format designations.
    """
    return find_cards(lambda c: c.is_legal_in(fmt), data)


def find_card(
        predicate: Callable[[Card], bool], data: Iterable[Card] | None = None,
        narrow_by_collector_number=False) -> Card | None:
    """Return card data from ``data`` that satisfies ``predicate`` or `None`.
    """
    data = data if data else bulk_data()
    if not narrow_by_collector_number:
        return from_iterable(data, predicate)

    cards = find_cards(predicate, data)
    cards = [card for card in cards if card.collector_number_int]
    cards = sorted(cards, key=lambda c: c.collector_number_int)
    # return card with the smallest collector number
    return cards[0] if cards else None


def find_by_name(card_name: str, data: Iterable[Card] | None = None) -> Card | None:
    """Return a Scryfall card data of provided name or `None`.
    """
    if "Mountain" in card_name:
        pass
    data = data if data else bulk_data()
    card = find_card(lambda c: c.name == card_name, data, narrow_by_collector_number=True)
    if card:
        return card
    card = find_card(lambda c: c.main_name == card_name, data, narrow_by_collector_number=True)
    if card:
        return card


def find_by_parts(
        name_parts: Iterable[str], data: Iterable[Card] | None = None) -> Card | None:
    """Return a Scryfall card data designated by provided ``name_parts`` or `None`.
    """
    if isinstance(name_parts, str):
        name_parts = name_parts.split()
    data = data if data else bulk_data()
    return find_card(lambda c: all(part.lower() in c.name.lower() for part in name_parts), data)


def find_by_collector_number(
        collector_number: int, data: Iterable[Card] | None = None) -> Card | None:
    """Return a Scryfall card data designated by provided ``collector_number`` from ``data`` or
    `None`.
    """
    data = data if data else bulk_data()
    data = [card for card in data if card.collector_number_int]
    return find_card(lambda c: c.collector_number == collector_number, data)


def find_by_id(scryfall_id: str, data: Iterable[Card] | None = None) -> Card | None:
    """Return a Scryfall card data of provided ``scryfall_id`` or `None`.
    """
    data = data if data else bulk_data()
    return from_iterable(data, lambda c: c.id == scryfall_id)


class ColorIdentityDistribution:
    """Distribution of `color_identity` in card data.
    """

    @property
    def colorsmap(self) -> defaultdict[Color, list[Card]]:
        """Return mapping of cards to colors.
        """
        return self._colorsmap

    @property
    def colors(self) -> list[tuple[Color, list[Card]]]:
        """Return list of (color, cards) tuples sorted by color.
        """
        return self._colors

    def __init__(self, data: Iterable[Card] | None = None) -> None:
        self._data = bulk_data() if not data else data
        self._colorsmap = defaultdict(list)
        # for card in self._data:
        #     self._colorsmap[Color(tuple(card.color_identity))].append(card)
        for card in self._data:
            self._colorsmap[card.color_identity].append(card)
        self._colors = sorted(
            [(k, v) for k, v in self._colorsmap.items()],
            key=lambda p: (len(p[0].value), p[0].value))
        Triple = namedtuple("Triple", "color quantity percentage")
        self._triples = [
            Triple(c[0], len(c[1]), len(c[1]) / len(bulk_data())) for c in self.colors]
        self._triples.sort(key=lambda t: t[1], reverse=True)

    def print(self) -> None:
        """Print this color distribution.
        """
        triples_str = [
            (str(t.color), f"quantity={t.quantity}", f"percentage={t.percentage:.4f}%")
            for t in self._triples]
        pprint(triples_str)

    def color(self, color: Color) -> tuple[Color, list[Card]] | None:
        return from_iterable(self.colors, lambda c: c[0] is color)


def print_color_identity_distribution(data: Iterable[Card] | None = None) -> None:
    dist = ColorIdentityDistribution(data)
    dist.print()


