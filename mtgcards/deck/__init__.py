"""

    mtgcards.deck.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse decklist URL/text for deck data.

    @author: z33k

"""
import itertools
import json
import logging
from abc import ABC, abstractmethod
from collections import Counter
from enum import Enum, auto
from functools import cached_property, lru_cache
from operator import attrgetter
from typing import Any, Iterable, Iterator

from mtgcards.const import Json, OUTPUT_DIR, PathLike
from mtgcards.scryfall import (
    Card, Color, MULTIFACE_SEPARATOR as SCRYFALL_MULTIFACE_SEPARATOR, aggregate, all_formats,
    find_by_cardmarket_id, find_by_collector_number, find_by_mtgo_id, find_by_oracle_id,
    find_by_scryfall_id,
    find_by_name,
    find_by_tcgplayer_id, find_sets,
    format_cards as scryfall_fmt_cards, set_cards as
    scryfall_set_cards)
from mtgcards.utils import ParsingError, extract_int, from_iterable, getrepr, serialize_dates
from mtgcards.utils.files import getdir, getfile

_log = logging.getLogger(__name__)


ARENA_MULTIFACE_SEPARATOR = "///"  # this is different from Scryfall data where they use: '//'


# based on https://draftsim.com/mtg-archetypes/
# this listing omits combo-control as it's too long a name to be efficiently used as a component
# of a catchy deck name
# in those scenarios usually a deck's theme (sub-archetype) is used (e.g. "stax" or "prison")
class Archetype(Enum):
    AGGRO = "aggro"
    MIDRANGE = "midrange"
    CONTROL = "control"
    COMBO = "combo"
    TEMPO = "tempo"
    RAMP = "ramp"


# this is needed when scraping meta-decks from sites that subdivide meta based on the mode of
# play (e.g. Aetherhub)
class Mode(Enum):
    BO1 = "Bo1"
    BO3 = "Bo3"


# themes compiled from:
# https://edhrec.com/themes
# https://edhrec.com/typal
# https://draftsim.com/mtg-deck-themes/
# https://cardgamebase.com/commander-precons/
# https://www.mtgsalvation.com/forums/the-game/commander-edh/806251-all-the-commander-edh-deck-archetypes-and-themes
# https://www.mtggoldfish.com/metagame/
# https://mtgdecks.net/Modern/staples/
THEMES = {
    "Affinity",  # mechanic
    "Aggression",
    "Allies",  # tribal
    "Angels",  # tribal
    "Apes",  # tribal
    "Apostles",  # (Shadowborn Apostles)
    "Approach",  # (Dragon's Approach)
    "Arcane,"
    "Archers",  # tribal
    "Aristocrats",
    "Artifact",
    "Artifacts",
    "Artificers",  # tribal
    "Assassins",  # tribal
    "Atogs",  # tribal
    "Auras",
    "Avatars",  # tribal
    "Backup",  # mechanic
    "Barbarians",  # tribal
    "Bears",  # tribal
    "Beasts",  # tribal
    "Berserkers",  # tribal
    "Big-Mana",
    "Birds",  # tribal
    "Blink",
    "Blitz",  # mechanic
    "Blood",
    "Bogles",
    "Bounce",
    "Bully",
    "Burn",
    "Cantrips",
    "Card-Draw",
    "Cascade",  # mechanic
    "Casualty",  # mechanic
    "Cats",  # tribal
    "Cephalids",  # tribal
    "Chaos",
    "Cheerios",
    "Clerics",  # tribal
    "Clones",
    "Clues",
    "Connive",  # mechanic
    "Constructs",  # tribal
    "Convoke",  # mechanic
    "Counters",
    "Counterspells",
    "Coven",  # mechanic
    "Crabs",  # tribal
    "Curses",
    "Cycling",  # mechanic
    "Deathtouch",  # mechanic
    "Defenders",  # mechanic
    "Deflection",
    "Demons",  # tribal
    "Deserts",
    "Detectives",  # tribal
    "Devils",  # tribal
    "Devotion",  # mechanic
    "Dinosaurs",  # tribal
    "Discard",
    "Doctors",  # tribal
    "Dogs",  # tribal
    "Domain",  # mechanic
    "Dragons",  # tribal
    "Drakes",  # tribal
    "Draw-Go",
    "Dredge",
    "Druids",  # tribal
    "Dungeons",  # mechanic
    "Dwarves",  # tribal
    "Eggs",
    "Elders",  # tribal
    "Eldrazi",  # tribal
    "Elementals",  # tribal
    "Elephants",  # tribal
    "Elves",  # tribal
    "Enchantments",
    "Enchantress",
    "Energy",  # mechanic
    "Enrage",  # mechanic
    "Equipment",
    "Equipments",
    "Evasion",
    "Exile",
    "Explore",  # mechanic
    "Extra-Combat",
    "Extra-Combats",
    "Extra-Turns",
    "Face-Down",
    "Faeries",  # tribal
    "Fight",
    "Flash",  # mechanic
    "Flashback",  # mechanic
    "Flicker",
    "Fliers",
    "Flying",  # mechanic
    "Food",
    "Forced-Combat",
    "Foretell",  # mechanic
    "Foxes",  # tribal
    "Frogs",  # tribal
    "Fungi",  # tribal
    "Giants",  # tribal
    "Go-Wide",
    "Goad",  # mechanic
    "Goblins",  # tribal
    "Gods",  # tribal
    "Golems",  # tribal
    "Gorgons",  # tribal
    "Graveyard",
    "Griffins",  # tribal
    "Halflings",  # tribal
    "Hate-Bears",
    "Hatebears",
    "Heroic",
    "Historic",  # mechanic
    "Horrors",  # tribal
    "Horses",  # tribal
    "Hug",  # (Group Hug)
    "Humans",  # tribal
    "Hydras",  # tribal
    "Illusions",  # tribal
    "Incubate",  # mechanic
    "Indestructible"  # mechanic
    "Infect",  # mechanic
    "Insects",  # tribal
    "Instants",
    "Jegantha",  # (Jegantha Companion)
    "Judo",
    "Kaheera",  # (Kaheera Companion)
    "Kavu",  # tribal
    "Keruga",  # (Keruga Companion)
    "Keywords",
    "Kithkin",  # tribal
    "Knights",  # tribal
    "Krakens",  # tribal
    "Land",
    "Land-Destruction",
    "Landfall",  # mechanic
    "Lands",
    "Lands",
    "Legends",
    "Life-Drain",
    "Life-Gain",
    "Life-Loss",
    "Lifedrain",
    "Lifegain",
    "Lifeloss",
    "Lords",  # tribal
    "Madness",  # mechanic
    "Mana-Rock",
    "Merfolk",  # tribal
    "Mill",  # mechanic
    "Minotaurs",  # tribal
    "Miracle",
    "Modify",  # mechanic
    "Monarch",  # mechanic
    "Monks",  # tribal
    "Moonfolk",  # tribal
    "Morph",  # mechanic
    "Mutants",  # tribal
    "Mutate",  # mechanic
    "Myr",  # tribal
    "Necrons",  # tribal
    "Ninjas",  # tribal
    "Ninjutsu",  # mechanic
    "One-Shot",
    "Oozes",  # tribal
    "Orcs",  # tribal
    "Outlaws",  # tribal
    "Overrun",
    "Party",  # mechanic
    "Permission",
    "Petitioners",  # (Persistent Petitioners)
    "Phoenixes",  # tribal
    "Phyrexians",  # tribal
    "Pillow-Fort",
    "Pingers",
    "Pirates",  # tribal
    "Planeswalkers",
    "Plants",  # tribal
    "Pod",
    "Poison",
    "Politics",
    "Polymorph",
    "Ponza",
    "Populate",
    "Power",
    "Praetors",  # tribal
    "Prison",
    "Prowess",  # mechanic
    "Rat-Colony",
    "Rats",  # tribal
    "Reanimator",
    "Rebels",  # tribal
    "Removal",
    "Rituals",
    "Robots",  # tribal
    "Rock",
    "Rogues",  # tribal
    "Sacrifice",
    "Sagas",
    "Samurai",  # tribal
    "Saprolings",  # (Saproling Tokens), tribal
    "Satyrs",  # tribal
    "Scam",
    "Scarecrows",  # tribal
    "Scry",
    "Sea-Creatures",
    "Self-Mill",
    "Shamans",  # tribal
    "Shapeshifters",  # tribal
    "Skeletons",  # tribal
    "Slivers",  # tribal
    "Slug",  # (Group Slug)
    "Snakes",  # tribal
    "Sneak-and-Tell",
    "Snow",
    "Soldiers",  # tribal
    "Sorceries",
    "Specters",  # tribal
    "Spell-Copy",
    "Spellslinger",
    "Sphinxes",  # tribal
    "Spiders",  # tribal
    "Spirits",  # tribal
    "Stax",
    "Stompy",
    "Storm",
    "Suicide",
    "Sunforger",
    "Superfriends",
    "Surge",  # (Primal Surge)
    "Surveil",  # mechanic
    "Suspend",
    "Swarm",
    "Taxes",
    "The-Rock",
    "Theft",
    "Thopters",  # tribal
    "Tokens",
    "Toolbox",
    "Top-Deck",
    "Topdeck",
    "Toughness",
    "Toxic",
    "Treasure",
    "Treasures",
    "Treefolk",  # tribal
    "Tribal",
    "Tron",
    "Turtles",  # tribal
    "Tutor",
    "Tutors",
    "Typal",
    "Tyranids",  # tribal
    "Umori",
    "Unicorns",  # tribal
    "Unnatural",
    "Value",
    "Vampires",  # tribal
    "Vehicles",
    "Venture",
    "Voltron",
    "Voting",
    "Walls",  # tribal
    "Warriors",  # tribal
    "Weenie",
    "Weird",
    "Werewolves",  # tribal
    "Wheels",
    "Wizards",  # tribal
    "Wolves",  # tribal
    "Wraiths",  # tribal
    "Wurms",  # tribal
    "X",
    "X-Creatures",
    "X-Spells",
    "Zombies",  # tribal
    "Zoo",
}


class InvalidDeck(ValueError):
    """Raised on invalid deck.
    """


class Deck:
    """A deck of cards suitable for Constructed formats.
    """
    MIN_MAINBOARD_SIZE = 60
    MAX_SIDEBOARD_SIZE = 15
    MIN_AGGRO_CMC = 2.3
    MAX_CONTROL_CREATURES_COUNT = 10

    @cached_property
    def mainboard(self) -> list[Card]:
        return [*itertools.chain(*self._playsets.values())]

    @cached_property
    def sideboard(self) -> list[Card]:
        return [*itertools.chain(
            *self._sideboard_playsets.values())] if self._sideboard_playsets else []

    @property
    def has_sideboard(self) -> bool:
        return bool(self.sideboard)

    @property
    def commander(self) -> Card | None:
        return self._commander

    @property
    def companion(self) -> Card | None:
        return self._companion

    @property
    def max_playset_count(self) -> int:
        return self._max_playset_count

    @property
    def cards(self) -> list[Card]:
        return [*self.mainboard, *self.sideboard]

    @property
    def color(self) -> Color:
        return Color.from_cards(*self.cards)

    @property
    def color_identity(self) -> Color:
        return Color.from_cards(*self.cards, identity=True)

    @property
    def artifacts(self) -> list[Card]:
        return [card for card in self.cards if card.is_artifact]

    @property
    def battles(self) -> list[Card]:
        return [card for card in self.cards if card.is_battle]

    @property
    def creatures(self) -> list[Card]:
        return [card for card in self.cards if card.is_creature]

    @property
    def enchantments(self) -> list[Card]:
        return [card for card in self.cards if card.is_enchantment]

    @property
    def instants(self) -> list[Card]:
        return [card for card in self.cards if card.is_instant]

    @property
    def lands(self) -> list[Card]:
        return [card for card in self.cards if card.is_land]

    @property
    def planeswalkers(self) -> list[Card]:
        return [card for card in self.cards if card.is_planeswalker]

    @property
    def sorceries(self) -> list[Card]:
        return [card for card in self.cards if card.is_sorcery]

    @property
    def commons(self) -> list[Card]:
        return [card for card in self.cards if card.is_common]

    @property
    def uncommons(self) -> list[Card]:
        return [card for card in self.cards if card.is_uncommon]

    @property
    def rares(self) -> list[Card]:
        return [card for card in self.cards if card.is_rare]

    @property
    def mythics(self) -> list[Card]:
        return [card for card in self.cards if card.is_mythic]

    @property
    def total_rarity_weight(self) -> float:
        return sum(card.rarity.weight for card in self.cards)

    @property
    def avg_rarity_weight(self):
        return self.total_rarity_weight / len(self.cards)

    @property
    def avg_cmc(self) -> float:
        manas = [card.cmc for card in self.cards if card.cmc]
        return sum(manas) / len(manas)

    @property
    def total_price(self) -> float:
        return sum(c.price for c in self.cards if c.price)

    @property
    def avg_price(self) -> float:
        cards = [card for card in self.cards if card.price]
        return self.total_price / len(cards)

    @property
    def total_price_tix(self) -> float:
        return sum(c.price_tix for c in self.cards if c.price_tix)

    @property
    def avg_price_tix(self) -> float:
        cards = [card for card in self.cards if card.price_tix]
        return self.total_price_tix / len(cards)

    @property
    def sets(self) -> list[str]:
        return sorted({c.set for c in self.cards if not c.is_basic_land})

    @property
    def races(self) -> Counter:
        return Counter(itertools.chain(*[c.races for c in self.cards]))

    @property
    def classes(self) -> Counter:
        return Counter(itertools.chain(*[c.classes for c in self.cards]))

    @property
    def is_bo3(self) -> bool:
        return self.has_sideboard and len(self.sideboard) > 7

    @property
    def is_bo1(self) -> bool:
        return not self.is_bo3

    @property
    def theme(self) -> str | None:
        if theme := self.metadata.get("theme"):
            return theme

        if not self.name:
            return None
        nameparts = [
            p for p in self.name.split() if not p.title() in [c.name.title() for c in Color]]
        return from_iterable(
                THEMES, lambda th: any(p.title() == th.title() for p in nameparts))

    @property
    def archetype(self) -> Archetype:
        if arch := self.metadata.get("archetype"):
            try:
                return Archetype(arch.lower())
            except ValueError:
                pass

        if self.name:
            nameparts = [
                p for p in self.name.split() if not p.title()
                in [c.name.title() for c in Color]]
            arch = from_iterable(
                Archetype, lambda a: any(p.title() == a.name.title() for p in nameparts))
            if arch:
                return arch
            # combo
            card_parts = {p for card in self.mainboard for p in card.name_parts}
            if any(p.title() in THEMES for p in nameparts):  # a themed deck is not a combo deck
                pass
            elif nameparts and any(p.lower() in card_parts for p in nameparts):
                return Archetype.COMBO
        if self.avg_cmc < self.MIN_AGGRO_CMC:
            return Archetype.AGGRO
        else:
            if len(self.creatures) < self.MAX_CONTROL_CREATURES_COUNT:
                return Archetype.CONTROL
            return Archetype.MIDRANGE

    @property
    def metadata(self) -> Json:
        return self._metadata

    @property
    def name(self) -> str | None:
        return self.metadata.get("name")

    @property
    def source(self) -> str | None:
        return self.metadata.get("source")

    @property
    def format(self) -> str | None:
        return self.metadata.get("format")

    @property
    def is_meta_deck(self) -> bool:
        return self._metadata.get("meta") is not None

    @property
    def is_event_deck(self) -> bool:
        return self._metadata.get("event") is not None

    @property
    def latest_set(self) -> str | None:
        set_codes = {c.set for c in self.cards if not c.is_basic_land}
        sets = find_sets(lambda s: s.code in set_codes and s.is_expansion)
        if not sets:
            return None
        sets = sorted(sets, key=attrgetter("released_at"))
        return [s.code for s in sets][-1]

    def __init__(
            self, mainboard: Iterable[Card], sideboard: Iterable[Card] | None = None,
            commander: Card | None = None, companion: Card | None = None,
            metadata: Json | None = None) -> None:
        # TODO: support two commanders (Partner keyword)
        if commander:
            if not commander.is_legendary or (
                    not commander.is_creature and not commander.is_planeswalker):
                raise InvalidDeck(
                    f"Commander must be a legendary creature/planeswalker. '{commander}' is not")
        if companion:
            if not companion.is_companion:
                raise InvalidDeck(f"Not a companion card: '{commander}'")

        sideboard = [*sideboard] if sideboard else []
        self._companion = companion
        sideboard = [
            companion, *sideboard] if companion and companion not in sideboard else sideboard
        self._metadata = metadata or {}

        self._commander = commander
        if commander:
            for card in [*mainboard, *sideboard]:
                if any(letter not in commander.color_identity.value
                       for letter in card.color_identity.value):
                    raise InvalidDeck(
                        f"Color identity of '{card}' ({card.color_identity}) doesn't match "
                        f"commander's color identity ({commander.color_identity})")

        self._max_playset_count = 1 if commander is not None else 4
        self._playsets = aggregate(*mainboard)
        self._validate_mainboard()
        self._sideboard_playsets = None
        if sideboard:
            self._sideboard_playsets = aggregate(*sideboard)
            self._validate_sideboard()
            if not self.companion:
                comp = from_iterable(sideboard, lambda c: c.is_companion)
                if comp:
                    self._companion = comp

    def _validate_playset(self, playset: list[Card]) -> None:
        card = playset[0]
        if card.is_basic_land or card.allowed_multiples is Ellipsis:
            pass
        else:
            max_playset = self.max_playset_count if card.allowed_multiples is None \
                else card.allowed_multiples
            if len(playset) > max_playset:
                raise InvalidDeck(
                    f"Too many occurrences of {card.name!r}: "
                    f"{len(playset)} > {max_playset}")

    def _validate_mainboard(self) -> None:
        for playset in self._playsets.values():
            self._validate_playset(playset)
        length = len(self.mainboard) + (1 if self.commander else 0)
        if length < self.MIN_MAINBOARD_SIZE:
            raise InvalidDeck(
                f"Invalid deck size: {length} < {self.MIN_MAINBOARD_SIZE}")

    def _validate_sideboard(self) -> None:
        temp_playsets = aggregate(*self.cards)
        for playset in temp_playsets.values():
            self._validate_playset(playset)
        if len(self.sideboard) > self.MAX_SIDEBOARD_SIZE:
            raise InvalidDeck(
                f"Invalid sideboard size: {len(self.sideboard)} > {self.MAX_SIDEBOARD_SIZE}")

    def __repr__(self) -> str:
        reprs = [("name", self.name)] if self.name else []
        if self.format:
            reprs += [("format", self.format)]
        reprs += [
            ("color", self.color.name),
            ("mode", f"{Mode.BO3.value if self.is_bo3 else Mode.BO1.value}"),
            ("avg_cmc", f"{self.avg_cmc:.2f}"),
            ("avg_rarity_weight", f"{self.avg_rarity_weight:.1f}"),
            ("avg_price", f"${self.avg_price:.2f}"),
            ("artifacts", len(self.artifacts)),
            ("battles", len(self.battles)),
            ("creatures", len(self.creatures)),
            ("enchantments", len(self.enchantments)),
            ("instants", len(self.instants)),
            ("lands", len(self.lands)),
            ("planeswalkers", len(self.planeswalkers)),
            ("sorceries", len(self.sorceries)),
        ]
        if self.commander:
            reprs.append(("commander", str(self.commander)))
        if self.companion:
            reprs.append(("companion", str(self.companion)))
        return getrepr(self.__class__, *reprs)

    def __eq__(self, other: "Deck") -> bool:
        if not isinstance(other, Deck):
            return False
        playsets = frozenset((card, len(cards)) for card, cards in aggregate(*self.cards).items())
        other_playsets = frozenset(
            (card, len(cards)) for card, cards in aggregate(*other.cards).items())
        return playsets == other_playsets

    def __hash__(self) -> int:
        return hash(frozenset((card, len(cards)) for card, cards in aggregate(
            *self.cards).items()))

    def __lt__(self, other: "Deck") -> bool:
        if not isinstance(other, Deck):
            return NotImplemented
        return self.avg_cmc < other.avg_cmc

    def __iter__(self) -> Iterator[Card]:
        return iter(self.cards)

    def update_metadata(self, **data: Any) -> None:
        self._metadata.update(data)

    def to_forge(self, dstdir: PathLike = "", name="") -> None:
        """Export to a Forge MTG deckfile format (.dck).

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            name: optionally, a custom name for the exported deck (if not provided a name based on this deck's data and metadata is constructed)
        """
        Exporter(self, name).to_forge(dstdir)

    def to_arena(self, dstdir: PathLike = "", name="") -> None:
        """Export to a MTGA deckfile text format (as a .txt file).

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            name: optionally, a custom name for the exported deck (if not provided a name based on this deck's data and metadata is constructed)
        """
        Exporter(self, name).to_arena(dstdir)

    @classmethod
    def from_forge(cls, path: PathLike) -> "Deck":
        """Import a deck from a Forge MTG deckfile format (.dck).

        Args:
            path: path to a .dck file
        """
        return Exporter.from_forge(path)

    @classmethod
    def from_arena(cls, path: PathLike) -> "Deck":
        """Import a deck from a MTG Arena deckfile format (.txt).

        Args:
            path: path to an Arena deck file
        """
        return Exporter.from_arena(path)

    @property
    def json(self) -> str:
        """Return a JSON representation of this deck.
        """
        return Exporter(self).json

    def to_json(self, dstdir: PathLike = "", name="") -> None:
        """Export to a .json file.

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            name: optionally, a custom name for the exported deck (if not provided a name based on this deck's data and metadata is constructed)
        """
        Exporter(self, name).to_json(dstdir)


class Exporter:
    """Export a deck to Forge MTG .dck file or Arena deck file. Also, import a deck from those
    formats.
    """
    DCK_TEMPLATE = """[metadata]
Name={}
[Commander]
{}
[Main]
{}
[Sideboard]
{}
"""
    NAME_SEP = "_"

    SOURCE_NICKNAMES = {
        "www.mtggoldfish.com": "Goldfish",
        "aetherhub.com": "Aetherhub",
        "www.moxfield.com": "Moxfield",
        "www.streamdecker.com": "Streamdecker",
        "mtga.untapped.gg": "Untapped",
        "mtgazone.com": "MGTAZone",
        "www.tcgplayer.com": "TCGPlayer",
        "www.cardhoarder.com": "Cardhoarder",
        "tappedout.net": "TappedOut",
    }

    FMT_NICKNAMES = {
        'alchemy': "Alch",
        'brawl': "Brwl",
        'commander': "Cmdr",
        'duel': "Duel",
        'explorer': "Expl",
        'future': "Ftr",
        'gladiator': "Gld",
        'historic': "Hst",
        'legacy': "Lgc",
        'modern': "Mdn",
        'oathbreaker': "Obr",
        'oldschool': "Old",
        'pauper': "Ppr",
        'paupercommander': "PprCmd",
        'penny': "Pnn",
        'pioneer': "Pnr",
        'predh': "Pdh",
        'premodern': "PreMdn",
        'standard': "Std",
        'standardbrawl': "StdBrl",
        'timeless': "Tml",
        'vintage': "Vnt",
    }

    def __init__(self, deck: Deck, name="") -> None:
        self._deck = deck
        self._name = name or self._build_name()

    @classmethod
    def _normalize(cls, name: str) -> str:
        name = name.replace(" ", cls.NAME_SEP).replace("-", cls.NAME_SEP)
        name = cls.NAME_SEP.join([p.title() for p in name.split(cls.NAME_SEP)])
        name = name.replace(f"5c{cls.NAME_SEP}", f"5C{cls.NAME_SEP}").replace(
            f"4c{cls.NAME_SEP}", f"4C{cls.NAME_SEP}")
        name = name.replace(f"Five{cls.NAME_SEP}Color{cls.NAME_SEP}", f"5C{cls.NAME_SEP}").replace(
            f"Four{cls.NAME_SEP}Color{cls.NAME_SEP}", f"4C{cls.NAME_SEP}")
        return name

    def _build_core_name(self) -> str:
        core = ""
        # color
        if len(self._deck.color.value) == 1:
            core += f"Mono{self.NAME_SEP}{self._deck.color.name.title()}{self.NAME_SEP}"
        elif len(self._deck.color.value) == 4:
            core += f"4C{self.NAME_SEP}"
        elif len(self._deck.color.value) == 5:
            core += f"5C{self.NAME_SEP}"
        else:
            core += f"{self._deck.color.name.title()}{self.NAME_SEP}"
        # theme
        if self._deck.theme:
            core += f"{self._deck.theme}{self.NAME_SEP}"
        # archetype
        core += f"{self._deck.archetype.name.title()}{self.NAME_SEP}"
        return core

    def _build_name(self) -> str:
        # prefix (source/author)
        source = self.SOURCE_NICKNAMES.get(self._deck.source) or ""
        prefix = source if self._deck.is_meta_deck and source else self._deck.metadata.get("author", "")
        name = f"{prefix}{self.NAME_SEP}" if prefix else ""
        # format
        if self._deck.format:
            name += f"{self.FMT_NICKNAMES[self._deck.format.lower()]}{self.NAME_SEP}"
        # mode
        if mode := self._deck.metadata.get("mode"):
            if mode in {m.value for m in Mode}:
                name += f"{mode}{self.NAME_SEP}"
        # meta
        if self._deck.is_meta_deck:
            name += f"Meta{self.NAME_SEP}"
            meta = self._deck.metadata["meta"]
            if meta_place := meta.get("place"):
                name += f"#{str(meta_place).zfill(2)}{self.NAME_SEP}"
        if self._deck.name:
            name += f"{self._normalize(self._deck.name)}{self.NAME_SEP}"
        else:
            name += self._build_core_name()
        # set
        if set_code := self._deck.latest_set:
            name += set_code.upper()
        return name

    @staticmethod
    def _to_forge_line(playset: list[Card]) -> str:
        card = playset[0]
        return f"{len(playset)} {card.main_name}|{card.set.upper()}|1"

    def _build_forge(self) -> str:
        commander = [
            self._to_forge_line(playset) for playset in
            aggregate(self._deck.commander).values()] if self._deck.commander else []
        mainboard = [
            self._to_forge_line(playset) for playset in aggregate(*self._deck.mainboard).values()]
        sideboard = [
            self._to_forge_line(playset) for playset in
            aggregate(*self._deck.sideboard).values()] if self._deck.sideboard else []
        return self.DCK_TEMPLATE.format(
            self._name, "\n".join(commander), "\n".join(mainboard), "\n".join(sideboard))

    def to_forge(self, dstdir: PathLike = "") -> None:
        dstdir = dstdir or OUTPUT_DIR / "dck"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._name}.dck"
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(self._build_forge(), encoding="utf-8")

    @classmethod
    def _parse_name(cls, name: str) -> Json:
        metadata = {}
        nameparts = name.split(cls.NAME_SEP)
        if src := from_iterable(
                cls.SOURCE_NICKNAMES,
                lambda s: any(np == cls.SOURCE_NICKNAMES[s] for np in nameparts)):
            metadata["source"] = src
            nameparts.remove(cls.SOURCE_NICKNAMES[src])
        if fmt := from_iterable(
                cls.FMT_NICKNAMES,
                lambda f: any(np == cls.FMT_NICKNAMES[f] for np in nameparts)):
            metadata["format"] = fmt
            nameparts.remove(cls.FMT_NICKNAMES[fmt])
        if mode := from_iterable(
                {m.value for m in Mode}, lambda mode: any(np == mode for np in nameparts)):
            metadata["mode"] = mode
            nameparts.remove(mode)
        try:
            idx = nameparts.index(f"Meta")
        except ValueError:
            idx = -1
        if idx != -1:
            idx += 1
            metadata["meta"] = {}
            metadata["meta"]["place"] = extract_int(nameparts[idx])
            del nameparts[idx]
            nameparts.remove(f"Meta")
        metadata["name"] = " ".join(nameparts[:-1])
        return metadata

    @staticmethod
    def _parse_forge_line(line: str) -> list[Card]:
        quantity, rest = line.split(maxsplit=1)
        name, _, _ = rest.split("|")
        return DeckParser.get_playset(DeckParser.find_card(name), int(quantity))

    @classmethod
    def from_forge(cls, path: PathLike) -> Deck:
        file = getfile(path, ext=".dck")
        commander, mainboard, sideboard, metadata = None, [], [], {}
        commander_on, mainboard_on, sideboard_on = False, False, False
        for line in file.read_text(encoding="utf-8").splitlines():
            if line.startswith("Name="):
                metadata = cls._parse_name(line.removeprefix("Name="))
            elif line == "[Commander]":
                commander_on = True
                continue
            elif line == "[Main]":
                commander_on, mainboard_on = False, True
                continue
            elif line == "[Sideboard]":
                mainboard_on, sideboard_on = False, True
                continue
            elif not line:
                continue

            if commander_on:
                commander = cls._parse_forge_line(line)[0]
            elif mainboard_on:
                mainboard += cls._parse_forge_line(line)
            elif sideboard_on:
                sideboard += cls._parse_forge_line(line)

        deck = Deck(mainboard, sideboard, commander, metadata=metadata)
        if not deck:
            raise ParsingError(f"Unable to parse '{path}' into a deck")
        return deck

    @staticmethod
    def _to_arena_line(playset: list[Card]) -> str:
        card = playset[0]
        card_name = card.name.replace(
            SCRYFALL_MULTIFACE_SEPARATOR,
            ARENA_MULTIFACE_SEPARATOR) if card.is_multiface else card.name
        line = f"{len(playset)} {card_name}"
        line += f" ({card.set.upper()}) {card.collector_number}"
        return line

    def _build_arena(self) -> str:
        lines = []
        if self._deck.commander:
            playset = aggregate(self._deck.commander)[self._deck.commander]
            lines += ["Commander", self._to_arena_line(playset), ""]
        if self._deck.companion:
            playset = aggregate(self._deck.companion)[self._deck.companion]
            lines += ["Companion", self._to_arena_line(playset), ""]
        lines += [
            "Deck",
            *[self._to_arena_line(playset) for playset
              in aggregate(*self._deck.mainboard).values()]
        ]
        if self._deck.sideboard:
            lines += [
                "",
                "Sideboard",
                *[self._to_arena_line(playset) for playset
                  in aggregate(*self._deck.sideboard).values()]
            ]
        return "\n".join(lines)

    def to_arena(self, dstdir: PathLike = "") -> None:
        dstdir = dstdir or OUTPUT_DIR / "arena"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._name}.txt"
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(self._build_arena(), encoding="utf-8")

    @classmethod
    def from_arena(cls, path: PathLike) -> Deck:
        from mtgcards.deck.arena import ArenaParser, is_arena_line, is_empty
        file = getfile(path, ext=".txt")
        lines = file.read_text(encoding="utf-8").splitlines()
        if not all(is_arena_line(l) or is_empty(l) for l in lines):
            raise ValueError(f"Not an MTG Arena deck file: '{file}'")
        metadata = cls._parse_name(file.name)
        deck = ArenaParser(lines, metadata).deck
        if not deck:
            raise ParsingError(f"Unable to parse '{path}' into a deck")
        return deck

    @property
    def json(self) -> str:
        data = {
            "metadata": self._deck.metadata,
            "arena_decklist": self._build_arena(),
        }
        return json.dumps(data, indent=4, ensure_ascii=False, default=serialize_dates)

    def to_json(self, dstdir: PathLike = "") -> None:
        dstdir = dstdir or OUTPUT_DIR / "json"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._name}.json"
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(self.json, encoding="utf-8")


class ParsingState(Enum):
    """State machine for deck parsing.
    """
    IDLE = auto()
    MAINBOARD = auto()
    SIDEBOARD = auto()
    COMMANDER = auto()
    COMPANION = auto()


class DeckParser(ABC):
    """Abstract base deck parser.
    """
    @property
    def deck(self) -> Deck | None:
        return self._deck

    @property
    def fmt(self) -> str:
        return self._metadata.get("format", "")

    @property
    def author(self) -> str | None:
        return self._metadata.get("author")

    def __init__(self, metadata: Json | None = None) -> None:
        self._metadata = metadata or {}
        self._state = ParsingState.IDLE
        self._mainboard, self._sideboard, self._commander, self._companion = [], [], None, None
        self._deck = None

    def _update_fmt(self, fmt: str) -> None:
        if fmt != self.fmt and fmt in all_formats():
            if self.fmt:
                _log.warning(
                    f"Earlier specified format: {self.fmt!r} overwritten with a scraped "
                    f"one: {fmt!r}")
            self._metadata["format"] = fmt

    def _shift_to_mainboard(self) -> None:
        if self._state is ParsingState.MAINBOARD:
            raise ParsingError(f"Invalid transition to MAINBOARD from: {self._state.name}")
        self._state = ParsingState.MAINBOARD

    def _shift_to_sideboard(self) -> None:
        if self._state is ParsingState.SIDEBOARD:
            raise ParsingError(f"Invalid transition to SIDEBOARD from: {self._state.name}")
        self._state = ParsingState.SIDEBOARD

    def _shift_to_commander(self) -> None:
        if self._state is ParsingState.COMMANDER:
            raise ParsingError(f"Invalid transition to COMMANDER from: {self._state.name}")
        self._state = ParsingState.COMMANDER

    def _shift_to_companion(self) -> None:
        if self._state is ParsingState.COMPANION:
            raise ParsingError(f"Invalid transition to COMPANION from: {self._state.name}")
        self._state = ParsingState.COMPANION

    @classmethod
    def find_card(
            cls, name: str,
            set_and_collector_number: tuple[str, str] | None = None,
            scryfall_id="",
            oracle_id="",
            tcgplayer_id: int | None = None,
            cardmarket_id: int | None = None,
            mtgo_id: int | None = None) -> Card:
        if set_and_collector_number:
            if card := find_by_collector_number(*set_and_collector_number):
                return card
        if scryfall_id:
            if card := find_by_scryfall_id(scryfall_id):
                return card
        if oracle_id:
            if card := find_by_oracle_id(oracle_id):
                return card
        if tcgplayer_id is not None:
            if card := find_by_tcgplayer_id(tcgplayer_id):
                return card
        if cardmarket_id is not None:
            if card := find_by_cardmarket_id(cardmarket_id):
                return card
        if mtgo_id is not None:
            if card := find_by_mtgo_id(mtgo_id):
                return card
        name = cls.sanitize_card_name(name)
        card = find_by_name(name)
        if not card:
            raise ParsingError(f"Unable to find card {name!r}")
        return card

    @staticmethod
    def get_playset(card: Card, quantity: int) -> list[Card]:
        return [card] * quantity

    @staticmethod
    def sanitize_card_name(text: str) -> str:
        return text.replace("’", "'")
