"""

    mtgcards.scryfall.py
    ~~~~~~~~~~~~~~~~~~~
    Handle Scryfall data.

    @author: z33k

"""
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

import scrython

from mtgcards.utils import from_iterable
from mtgcards.utils.files import download_file, getdir
from mtgcards.const import DATADIR, Json

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
MULTIPART_LAYOUTS = ['adventure', 'art_series', 'double_faced_token', 'flip', 'modal_dfc', 'split',
                     'transform']\

# all cards that got Alchemy rebalance treatment have their rebalanced counterparts with names
# prefixed by 'A-'
ALCHEMY_REBALANCE_INDICATOR = "A-"


class Color(Enum):
    WHITE = "W"
    BLUE = "U"
    BLACK = "B"
    RED = "R"
    GREEN = "G"
    # allied pairs
    AZORIUS = ("W", "U")
    DIMIR = ("U", "B")
    RAKDOS = ("B", "R")
    GRUUL = ("R", "G")
    SELESNYA = ("G", "W")
    # enemy pairs
    ORZHOV = ("W", "B")
    IZZET = ("U", "R")
    GOLGARI = ("B", "G")
    BOROS = ("R", "W")
    SIMIC = ("G", "U")
    # shard triples
    BANT = ("G", "W", "U")
    ESPER = ("W", "U", "B")
    GRIXIS = ("U", "B", "R")
    JUND = ("B", "R", "G")
    NAYA = ("R", "G", "W")
    # wedge triples
    ABZAN = ("W", "B", "G")
    JESKAI = ("U", "R", "W")
    SULTAI = ("B", "G", "U")
    MARDU = ("R", "W", "B")
    TEMUR = ("G", "U", "R")
    # quadruples
    ARTIFICE = ("W", "U", "B", "R")
    CHAOS = ("U", "B", "R", "B")
    AGGRESSION = ("B", "R", "G", "W")
    ALTRUISM = ("R", "G", "W", "U")
    GROWTH = ("G", "W", "U", "B")
    # other
    ALL = ("W", "U", "B", "R", "G")
    COLORLESS = "L"


class TypeLine:
    """Parser of type line in Scryfall data.
    """
    SEPARATOR = "—"

    # according to MtG Wiki
    SUPERTYPES = {"Basic", "Elite", "Host", "Legendary", "Ongoing", "Snow", "Token", "World"}
    PERMAMENT_TYPES = {"Artifact", "Creature", "Enchantment", "Land", "Planeswalker"}
    NONPERMAMENT_TYPES = {"Sorcery", "Instant"}

    # creature types
    # race types
    ICONIC_RACES = {
        Color.WHITE: "Angel",
        Color.BLUE: "Sphinx",
        Color.BLACK: "Demon",
        Color.RED: "Dragon",
        Color.GREEN: "Hydra",
    }
    CHARACTERISTIC_RACES = {
        Color.WHITE: {"Human"},
        Color.BLUE: {"Merfolk"},
        Color.BLACK: {"Vampire", "Zombie"},
        Color.RED: {"Goblin"},
        Color.GREEN: {"Elf"},
    }
    MECHANICALLY_THEMED_RACES = {"Atog", "Bringer", "Demigod", "God", "Incarnation", "Licid",
                                 "Lhurgoyf", "Nephilim", "Phelddagrif", "Shapeshifter", "Slith",
                                 "Sliver", "Spike", "Volver", "Wall", "Weird", "Werewolf", "Zubera"}
    TOKEN_SPECIFIC_RACES = {"Balloon", "Camarid", "Caribou", "Fractal", "Germ", "Graveborn",
                            "Hamster", "Inkling", "Mite", "Orb", "Pentavite", "Pincher", "Prism",
                            "Sand", "Saproling", "Sculpture", "Servo", "Splinter", "Tetravite",
                            "Triskelavite"}
    MAJORITY_RACES = {
        Color.WHITE: {"Archon", "Camel", "Cat", "Fox", "Griffin", "Hippogriff", "Kirin",
                      "Kithkin", "Kor", "Lammasu", "Mouse", "Pegasus", "Soltari", "Unicorn"},
        Color.BLUE: {"Beeble", "Cephalid", "Crab", "Djinn", "Drake", "Faerie", "Fish", "Homarid",
                     "Homunculus", "Illusion", "Jellyfish", "Kraken", "Leviathan", "Metathran",
                     "Moonfolk", "Nautilus", "Octopus", "Otter", "Oyster", "Serpent", "Shark",
                     "Siren", "Sponge", "Squid", "Starfish", "Thalakos", "Trilobite", "Turtle",
                     "Vedalken", "Whale"},
        Color.BLACK: {"Aetherborn", "Azra", "Bat", "Carrier", "Dauthi", "Eye",
                      "Gorgon", "Hag", "Harpy", "Horror", "Imp", "Lamia", "Leech",  "Nightmare",
                      "Nightstalker", "Phyrexian", "Rat", "Scorpion", "Shade", "Skeleton", "Slug",
                      "Specter", "Thrull", "Worm", "Wraith"},
        Color.RED: {"Cyclops", "Devil", "Dwarf", "Efreet", "Giant", "Goat", "Gremlin", "Hellion",
                    "Jackal", "Kobold", "Manticore", "Minotaur", "Ogre", "Orc", "Orgg", "Phoenix",
                    "Viashino", "Wolverine", "Yeti"},
        Color.GREEN: {"Antelope", "Ape", "Aurochs", "Badger", "Basilisk", "Bear", "Beast", "Boar",
                      "Brushwagg", "Centaur", "Crocodile", "Dryad", "Elk", "Ferret", "Fungus",
                      "Hippo", "Hyena", "Mole", "Mongoose", "Monkey", "Ooze", "Ouphe", "Plant",
                      "Rabbit", "Raccoon", "Rhino", "Snake", "Spider", "Squirrel", "Treefolk",
                      "Troll", "Wolf", "Wombat", "Wurm"},
        Color.COLORLESS: {"Eldrazi"},
    }
    ARTIFACT_RACES = {"Assembly-Worker", "Blinkmoth", "Construct", "Dreadnought", "Juggernaut",
                      "Gnome", "Golem", "Masticore", "Myr", "Robot", "Sable", "Scarecrow",
                      "Thopter", "Walrus"}
    MULTICOLORED_RACES = {"Alien", "Avatar", "Bird", "Chimera", "Mutant", "Naga", "Cockatrice",
                          "Dinosaur", "Dog", "Elemental", "Elephant", "Sheep", "Frog",
                          "Gargoyle", "Horse", "Insect", "Nymph", "Ox", "Pangolin", "Pest",
                          "Kavu", "Lizard", "Satyr", "Noggle", "Reflection", "Salamander",
                          "Spirit", "Surrakar"}
    CROSSOVER_RACES = {
        "Dungeons & Dragons": {"Beholder", "Gith", "Gnoll", "Halfling", "Tiefling"},
        "Universes Beyond": {"Astartes", "C'tan", "Custodes", "Necron", "Primarch", "Tyranid"},
    }
    RACES = {*ICONIC_RACES.values(), *{race for v in CHARACTERISTIC_RACES.values() for race in v},
             *MECHANICALLY_THEMED_RACES, *TOKEN_SPECIFIC_RACES,
             *{race for v in MAJORITY_RACES.values() for race in v}, *ARTIFACT_RACES,
             *MULTICOLORED_RACES, *{race for v in CROSSOVER_RACES.values() for race in v}}

    # class types
    SPELLCASTERS = {
        Color.WHITE: "Cleric",
        Color.BLUE: "Wizard",
        Color.BLACK: "Warlock",
        Color.RED: "Shaman",
        Color.GREEN: "Druid",
    }
    MECHANICALLY_THEMED_CLASSES = {"Ally", "Coward", "Egg", "Flagbearer", "Mercenary", "Monger",
                                   "Ninja", "Pilot", "Processor", "Rebel", "Samurai", "Spellshaper"}
    TOKEN_SPECIFIC_CLASSES = {"Army", "Deserter", "Scion", "Serf", "Survivor", "Tentacle"}
    GENERAL_CLASSES = {"Advisor", "Archer", "Artificer", "Assassin", "Barbarian", "Bard",
                       "Berserker", "Child", "Citizen", "Clown", "Drone", "Elder", "Employee",
                       "Gamer", "Guest", "Knight", "Minion", "Monk", "Mystic", "Noble", "Nomad",
                       "Peasant", "Performer", "Pirate", "Praetor", "Ranger", "Rigger", "Rogue",
                       "Scout", "Soldier", "Spawn", "Warrior"}
    CROSSOVER_CLASSES = {"Universes Beyond": "Inquisitor"}
    CLASSES = {*SPELLCASTERS.values(), *MECHANICALLY_THEMED_CLASSES, *TOKEN_SPECIFIC_CLASSES,
               *GENERAL_CLASSES, *CROSSOVER_CLASSES.values()}

    @property
    def text(self) -> str:
        return self._text

    @property
    def supertypes(self) -> List[str]:
        return [t for t in self._types if t in self.SUPERTYPES]

    @property
    def regular_types(self) -> List[str]:
        return [t for t in self._types if t not in self.SUPERTYPES]

    @property
    def subtypes(self) -> List[str]:
        return self._subtypes

    @property
    def is_permanent(self) -> bool:
        return all(p in self.PERMAMENT_TYPES for p in self.regular_types)

    @property
    def is_nonpermanent(self) -> bool:
        # type not being permanent doesn't mean it's 'non-permanent', e.g. 'dungeon' is neither
        return all(p in self.NONPERMAMENT_TYPES for p in self.regular_types)

    @property
    def races(self) -> List[str]:
        return [t for t in self.subtypes if t in self.RACES]

    @property
    def classes(self) -> List[str]:
        return [t for t in self.subtypes if t in self.CLASSES]

    def __init__(self, text: str) -> None:
        if MULTIPART_SEPARATOR in text:
            raise ValueError("Multipart type line")
        self._text = text
        self._types, self._subtypes = self._parse()

    def _parse(self) -> Tuple[List[str], List[str]]:
        """Parse text into types and subtypes.
        """
        if self.SEPARATOR in self.text:
            types, subtypes = self.text.split(f" {self.SEPARATOR} ", maxsplit=1)
            return types.split(), subtypes.split()
        return self.text.split(), []


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

    @property
    def name(self) -> str:
        return self.json["name"]

    @property
    def name_parts(self) -> Set[str]:
        return {*self.name.split()}

    @property
    def mana_cost(self) -> str:
        return self.json["mana_cost"]

    @property
    def type_line(self) -> str:
        return self.json["type_line"]

    @property
    def oracle_text(self) -> str:
        return self.json["oracle_text"]

    @property
    def colors(self) -> List[Color]:
        result = self.json.get("colors")
        return result if result else []

    @lru_cache
    def parse_types(self) -> TypeLine:
        return TypeLine(self.type_line)

    @property
    def supertypes(self) -> List[str]:
        return self.parse_types().supertypes

    @property
    def regular_types(self) -> List[str]:
        return self.parse_types().regular_types

    @property
    def subtypes(self) -> List[str]:
        return self.parse_types().subtypes

    @property
    def races(self) -> List[str]:
        return self.parse_types().races

    @property
    def classes(self) -> List[str]:
        return self.parse_types().classes


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

    def __post_init__(self) -> None:
        if self.is_multipart and self.card_faces is None:
            raise ScryfallError(f"Card faces data missing for multipart card {self.name!r}")
        if self.is_multipart and self.layout not in MULTIPART_LAYOUTS:
            raise ScryfallError(f"Invalid layout {self.layout!r} for multipart card {self.name!r}")

    @property
    def card_faces(self) -> Optional[List[CardFace]]:
        data = self.json.get("card_faces")
        if data is None:
            return None
        return [CardFace(item) for item in data]

    @property
    def cmc(self) -> float:
        return self.json["cmc"]

    @property
    def color_identity(self) -> List[Color]:
        # 'color_identity' is a wider term than 'colors' (that only take mana cost into account)
        # more on this here: https://mtg.fandom.com/wiki/Color_identity
        return self.json["color_identity"]

    @property
    def colors(self) -> List[str]:
        result = self.json.get("colors")
        return result if result else []

    @property
    def formats(self) -> List[str]:
        """Return list of all Scryfall string format designations (e.g. `bro` for The Brothers'
        War).
        """
        return sorted(fmt for fmt in self.legalities)

    @property
    def games(self) -> List[str]:
        return self.json["games"]

    @property
    def id(self) -> str:
        return self.json["id"]

    @property
    def keywords(self) -> List[str]:
        return self.json["keywords"]

    @property
    def layout(self) -> str:
        return self.json["layout"]

    @property
    def legalities(self) -> Dict[str, str]:
        return self.json["legalities"]

    @property
    def loyalty(self) -> Optional[str]:
        return self.json.get("loyalty")

    @property
    def loyalty_int(self) -> Optional[int]:
        return self._int(self.loyalty)

    @property
    def has_special_loyalty(self) -> bool:
        return self.loyalty is not None and self.loyalty_int is None

    @property
    def mana_cost(self) -> Optional[str]:
        return self.json.get("mana_cost")

    @property
    def oracle_text(self) -> Optional[str]:
        return self.json.get("oracle_text")

    @property
    def name(self) -> str:
        return self.json["name"]

    @property
    def name_parts(self) -> Set[str]:
        if not self.is_multipart:
            return {*self.name.split()}
        return {part for face in self.card_faces for part in face.name_parts}

    @property
    def power(self) -> Optional[int]:
        return self.json.get("power")

    @property
    def power_int(self) -> Optional[int]:
        return self._int(self.power)

    @property
    def has_special_power(self) -> bool:
        return self.power is not None and self.power_int is None

    @property
    def price(self) -> Optional[float]:
        """Return price in USD or `None` if unavailable.
        """
        return self.json["prices"].get("usd")

    @property
    def rarity(self) -> str:
        return self.json["rarity"]

    @property
    def released_at(self) -> datetime:
        return datetime.strptime(self.json["released_at"], "%Y-%m-%d")

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
    def toughness(self) -> Optional[str]:
        return self.json.get("toughness")

    @property
    def toughness_int(self) -> Optional[int]:
        return self._int(self.toughness)

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

        :param fmt: Scryfall format designation
        :raises: ValueError on invalid format designation
        """
        if fmt.lower() not in self.formats:
            raise ValueError(f"No such format: {fmt!r}")

        if self.legalities[fmt] == "restricted":
            return True
        return False

    @staticmethod
    def _int(text: Optional[str]) -> Optional[int]:
        if text is None:
            return None
        try:
            value = int(text)
        except ValueError:
            return None
        return value

    @lru_cache
    def parse_types(self) -> Optional[TypeLine]:
        if self.is_multipart:
            return None
        return TypeLine(self.type_line)

    @property
    def supertypes(self) -> List[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.supertypes})
        return self.parse_types().supertypes

    @property
    def regular_types(self) -> List[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.regular_types})
        return self.parse_types().regular_types

    @property
    def subtypes(self) -> List[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.subtypes})
        return self.parse_types().subtypes

    @property
    def races(self) -> List[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.races})
        return self.parse_types().races

    @property
    def classes(self) -> List[str]:
        if self.is_multipart:
            return sorted({t for face in self.card_faces for t in face.classes})
        return self.parse_types().classes

    @property
    def is_permanent(self) -> bool:
        if self.is_multipart:
            return all(face.is_permanent for face in self.card_faces)
        return self.parse_types().is_permanent

    @property
    def is_nonpermanent(self) -> bool:
        if self.is_multipart:
            return all(face.is_nonpermanent for face in self.card_faces)
        return self.parse_types().is_nonpermanent

    @property
    def is_alchemy_rebalance(self) -> bool:
        return self.name.startswith(ALCHEMY_REBALANCE_INDICATOR)

    @property
    @lru_cache
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
            return find_by_name(self.name[2:], exact=True)
        # is multipart
        first_part_name, *_ = self.name.split(MULTIPART_SEPARATOR)
        original_name = first_part_name[2:]
        original = from_iterable(
            self.json["all_parts"],
            lambda p: original_name in p["name"] and not p["name"].startswith(
                ALCHEMY_REBALANCE_INDICATOR)
        )
        if original:
            return find_by_name(original["name"], exact=True)
        return None

    @property
    def has_alchemy_rebalance(self) -> bool:
        return self.alchemy_rebalance is not None


@lru_cache
def bulk_data() -> Set[Card]:
    """Return Scryfall JSON data as list of Card objects.
    """
    source = getdir(DATADIR) / FILENAME
    if not source.exists():
        download_scryfall_bulk_data()

    with source.open() as f:
        data = json.load(f)

    return {Card(card_data) for card_data in data}


def games(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of string designations for games that can be played with cards in Scryfall data.
    """
    data = data if data else bulk_data()
    result = set()
    for card in data:
        result.update(card.games)

    return sorted(result)


def colors(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of string designations for MtG colors in Scryfall data.
    """
    data = data if data else bulk_data()
    result = set()
    for card in data:
        result.update(card.colors)
    return sorted(result)


def sets(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of string codes for MtG sets in Scryfall data (e.g. 'bro' for The Brothers'
    War).
    """
    data = data if data else bulk_data()
    return sorted({card.set for card in data})


def formats() -> List[str]:
    """Return list of string designations for MtG formats in Scryfall data.
    """
    return next(iter(bulk_data())).formats


def layouts(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of Scryfall string designations for card layouts in ``data``.
    """
    data = data if data else bulk_data()
    return sorted({card.layout for card in data})


def set_names(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of MtG set names in Scryfall data.
    """
    data = data if data else bulk_data()
    return sorted({card.set_name for card in data})


def rarities(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of MtG card rarities in Scryfall data.
    """
    data = data if data else bulk_data()
    return sorted({card.rarity for card in data})


def keywords(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of MtG card keywords in Scryfall data.
    """
    data = data if data else bulk_data()
    result = set()
    for card in data:
        result.update(card.keywords)
    return sorted(result)


def find_cards(predicate: Callable[[Card], bool],
               data: Optional[Iterable[Card]] = None) -> Set[Card]:
    """Return list of cards from ``data`` that satisfy ``predicate``.
    """
    data = data if data else bulk_data()
    return {card for card in data if predicate(card)}


def set_cards(*set_codes: str, data: Optional[Iterable[Card]] = None) -> Set[Card]:
    """Return card data for sets designated by ``set_codes``.
    """
    return find_cards(lambda c: c.set in [code.lower() for code in set_codes], data)


def arena_cards() -> Set[Card]:
    """Return Scryfall bulk data filtered for only cards available on Arena.
    """
    return find_cards(lambda c: "arena" in c.games)


def format_cards(fmt: str, data: Optional[Iterable[Card]] = None) -> Set[Card]:
    """Return card data for MtG format designated by ``fmt``.
    """
    return find_cards(lambda c: c.is_legal_in(fmt), data)


def find_card(predicate: Callable[[Card], bool],
              data: Optional[Iterable[Card]] = None) -> Optional[Card]:
    """Return card data from ``data`` that satisfies ``predicate`` or `None`.
    """
    data = data if data else bulk_data()
    return from_iterable(data, predicate)


def find_by_name(card_name: str, data: Optional[Iterable[Card]] = None,
                 exact=False) -> Optional[Card]:
    """Return a Scryfall card data of provided name or `None`.
    """
    data = data if data else bulk_data()
    if exact:
        return find_card(lambda c: c.name == card_name, data)
    return find_card(lambda c: card_name.lower() in c.name.lower(), data)


def find_by_parts(name_parts: Iterable[str],
                  data: Optional[Iterable[Card]] = None) -> Optional[Card]:
    """Return a Scryfall card data designated by provided ``name_parts`` or `None`.
    """
    data = data if data else bulk_data()
    return find_card(lambda c: all(part.lower() in c.name.lower() for part in name_parts), data)

