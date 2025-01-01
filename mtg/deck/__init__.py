"""

    mtg.deck.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse decklist URL/text for deck data.

    @author: z33k

"""
import contextlib
import itertools
import json
import logging
import re
from abc import ABC, abstractmethod
from collections import Counter, OrderedDict
from enum import Enum, auto
from functools import cached_property
from operator import attrgetter
from typing import Any, Iterable, Iterator

from mtg import Json, OUTPUT_DIR, PathLike
from mtg.scryfall import (
    COMMANDER_FORMATS, Card, Color,
    MULTIFACE_SEPARATOR as SCRYFALL_MULTIFACE_SEPARATOR, aggregate,
    all_formats, find_by_cardmarket_id, find_by_collector_number,
    find_by_mtgo_id, find_by_name, find_by_oracle_id,
    find_by_scryfall_id, find_by_tcgplayer_id, find_sets,
    query_api_for_card)
from mtg.utils import ParsingError, extract_int, from_iterable, getid, getrepr, serialize_dates, \
    type_checker
from mtg.utils.files import getdir, getfile

_log = logging.getLogger(__name__)


ARENA_MULTIFACE_SEPARATOR = "///"  # this is different from Scryfall data where they use: '//'

# TODO: look here: https://pennydreadfulmagic.com/archetypes/
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


# this class tries to be as generic as possible and still support multiple Constructed formats
# this means some more complicated formats like Oathbreaker are not fully supported (e.g a Deck
# knows nothing about signature spells) to not over-complicate things (by either going into an
# inheritance hierarchy or bloating the generic API beyond comprehension)
class Deck:
    """A deck of cards suitable for Constructed formats.
    """
    MIN_MAINDECK_SIZE = 60
    MAX_SIDEBOARD_SIZE = 15
    MIN_AGGRO_CMC = 2.3  # arbitrary
    MAX_CONTROL_CREATURES_COUNT = 10  # arbitrary

    @property
    def maindeck(self) -> list[Card]:
        return self._maindeck

    @property
    def sideboard(self) -> list[Card]:
        return self._sideboard

    @property
    def has_sideboard(self) -> bool:
        return bool(self.sideboard)

    @property
    def commander(self) -> Card | None:
        return self._commander

    @property
    def partner_commander(self) -> Card | None:
        return self._partner_commander

    @property
    def companion(self) -> Card | None:
        return self._companion

    @property
    def cards(self) -> list[Card]:
        commanders = [self.commander] if self.commander else []
        if self.partner_commander:
            commanders.append(self.partner_commander)
        return [*commanders, *self.maindeck, *self.sideboard]

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
    def avg_price(self) -> float | None:
        cards = [card for card in self.cards if card.price]
        return self.total_price / len(cards) if cards else None

    @property
    def total_price_tix(self) -> float:
        return sum(c.price_tix for c in self.cards if c.price_tix)

    @property
    def avg_price_tix(self) -> float | None:
        cards = [card for card in self.cards if card.price_tix]
        return self.total_price_tix / len(cards) if cards else None

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

    @cached_property
    def theme(self) -> str | None:
        if theme := self.metadata.get("theme"):
            return theme

        if not self.name:
            return None
        nameparts = [
            p for p in self.name.split() if not p.title() in [c.name.title() for c in Color]]
        return from_iterable(
                THEMES, lambda th: any(p.title() == th.title() for p in nameparts))

    @cached_property
    def archetype(self) -> Archetype:
        if arch := self.metadata.get("archetype"):
            with contextlib.suppress(ValueError):
                return Archetype(arch)

        if self.name:
            nameparts = [
                p for p in self.name.split() if not p.title()
                in [c.name.title() for c in Color]]
            arch = from_iterable(
                Archetype, lambda a: any(p.title() == a.name.title() for p in nameparts))
            if arch:
                return arch
            # combo
            card_parts = {p for card in self.cards for p in card.name_parts}
            if any(p.title() in THEMES for p in nameparts):  # a themed deck is not a combo deck
                pass
            elif identified := from_iterable(nameparts, lambda n: n.lower() in card_parts):
                if self.commander and identified in self.commander.name_parts:
                    pass  # don't flag commander part in name as combo
                else:
                    return Archetype.COMBO
        if self.avg_cmc < self.MIN_AGGRO_CMC:
            return Archetype.AGGRO
        else:
            if len(self.creatures) < self.MAX_CONTROL_CREATURES_COUNT:
                return Archetype.CONTROL
            return Archetype.MIDRANGE

    @property
    def metadata(self) -> Json:
        return OrderedDict(sorted((k, v) for k, v in self._metadata.items()))

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
    def url(self) -> str | None:
        return self.metadata.get("url")

    @property
    def is_meta_deck(self) -> bool:
        return any(k.startswith("meta") for k in self.metadata)

    @property
    def is_event_deck(self) -> bool:
        return any(k.startswith("event") for k in self.metadata)

    @cached_property
    def latest_set(self) -> str | None:
        set_codes = {c.set for c in self.cards if not c.is_basic_land}
        sets = find_sets(lambda s: s.code in set_codes and s.is_expansion)
        if not sets:
            return None
        sets = sorted(sets, key=attrgetter("released_at"))
        return [s.code for s in sets][-1]

    def __init__(
            self, maindeck: Iterable[Card], sideboard: Iterable[Card] | None = None,
            commander: Card | None = None, partner_commander: Card | None = None,
            companion: Card | None = None, metadata: Json | None = None) -> None:
        commanders = [c for c in [commander, partner_commander] if c]
        maindeck, sideboard = [*maindeck], [*sideboard] if sideboard else []
        if commanders and sideboard:
            sideboard = []
            _log.warning("Disregarding sideboard for a commander-enabled deck")
        if partner_commander:
            if not commander:
                raise InvalidDeck("Partner commander without commander")
        if commanders:
            for cmd in commanders:
                if cmd in maindeck:
                    maindeck.remove(cmd)
                if cmd in sideboard:
                    sideboard.remove(cmd)
            cards = {*maindeck, *sideboard}
            if any(cmd in cards for cmd in commanders):
                raise InvalidDeck(f"Redundant commander maindeck/sideboard inclusion")
            identity = {clr for c in commanders for clr in c.color_identity.value}
            for card in [*maindeck, *sideboard]:
                if any(letter not in identity for letter in card.color_identity.value):
                    _log.warning(
                        f"Color identity of '{card}' ({card.color_identity}) doesn't match "
                        f"commander's color identity ({Color.from_letters(*identity)})")
        self._commander, self._partner_commander = commander, partner_commander

        if companion:
            if not companion.is_companion:
                raise InvalidDeck(f"Not a companion card: '{companion}'")
        self._companion = companion

        sideboard = [*sideboard] if sideboard else []
        sideboard = [
            companion, *sideboard] if companion and companion not in sideboard else sideboard
        self._metadata = metadata or {}

        self._max_playset_count = 1 if commander is not None else 4
        playsets = aggregate(*maindeck)
        for playset in playsets.values():
            self._validate_playset(playset)
        self._maindeck = [*itertools.chain(
            *sorted(playsets.values(), key=lambda l: l[0].name))]

        if (len(self.maindeck) + len(commanders)) < self.MIN_MAINDECK_SIZE:
            raise InvalidDeck(
                f"Invalid deck size: {len(self.maindeck) + len(commanders)} "
                f"< {self.MIN_MAINDECK_SIZE}")

        self._sideboard = []
        if sideboard:
            if not self.companion:
                if comp := from_iterable(sideboard, lambda c: c.is_companion):
                    self._companion = comp
            sideboard_playsets = aggregate(*sideboard)
            self._sideboard = [*itertools.chain(
                *sorted(sideboard_playsets.values(), key=lambda l: l[0].name))]
            if len(self.sideboard) > self.MAX_SIDEBOARD_SIZE:
                self._cut_sideboard(sideboard)
            temp_playsets = aggregate(*self.cards)
            for playset in temp_playsets.values():
                self._validate_playset(playset)

    def _cut_sideboard(self, input_sideboard: list[Card]) -> None:
        _log.warning(
            f"Oversized sideboard ({len(self.sideboard)}) cut down to regular size "
            f"({self.MAX_SIDEBOARD_SIZE})")
        sideboard = input_sideboard[:self.MAX_SIDEBOARD_SIZE]
        if self.companion and self.companion not in sideboard:
            sideboard[-1] = self.companion
        sideboard_playsets = aggregate(*sideboard)
        self._sideboard = [*itertools.chain(
            *sorted(sideboard_playsets.values(), key=lambda l: l[0].name))]

    def _validate_playset(self, playset: list[Card]) -> None:
        card = playset[0]
        if card.is_basic_land or card.allowed_multiples is Ellipsis:
            pass
        else:
            max_playset = self._max_playset_count if card.allowed_multiples is None \
                else card.allowed_multiples
            if len(playset) > max_playset:
                raise InvalidDeck(
                    f"Too many occurrences of {card.name!r}: "
                    f"{len(playset)} > {max_playset}")

    def __repr__(self) -> str:
        reprs = [("name", self.name)] if self.name else []
        if self.format:
            reprs += [("format", self.format)]
        reprs += [
            ("color", self.color.name),
            ("mode", f"{Mode.BO3.value if self.is_bo3 else Mode.BO1.value}"),
            ("avg_cmc", f"{self.avg_cmc:.2f}"),
            ("avg_rarity_weight", f"{self.avg_rarity_weight:.1f}")
        ]
        if self.avg_price:
            reprs += [("avg_price", f"${self.avg_price:.2f}")]
        reprs += [
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
        return self.json == other.json

    def __hash__(self) -> int:
        return hash(self.json)

    def __lt__(self, other: "Deck") -> bool:
        if not isinstance(other, Deck):
            return NotImplemented
        return self.avg_cmc < other.avg_cmc

    def __iter__(self) -> Iterator[Card]:
        return iter(self.cards)

    def update_metadata(self, **data: Any) -> None:
        self._metadata.update(data)

    def to_forge(self, dstdir: PathLike = "", filename="") -> None:
        """Export to a Forge MTG deckfile format (.dck).

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            filename: optionally, a custom filename (if not provided a name based on this deck's data and metadata is constructed)
        """
        Exporter(self, filename).to_forge(dstdir)

    def to_arena(self, dstdir: PathLike = "", filename="") -> None:
        """Export to a MTGA deckfile text format (as a .txt file).

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            filename: optionally, a custom filename (if not provided a name based on this deck's data and metadata is constructed)
        """
        Exporter(self, filename).to_arena(dstdir)

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

    @cached_property
    def decklist(self) -> str:
        return Exporter(self).build_decklist(extended=False, about=False)

    @property
    def decklist_id(self) -> str:
        return getid(self.decklist)

    @cached_property
    def decklist_extended(self) -> str:
        return Exporter(self).build_decklist(extended=True, about=False)

    @property
    def decklist_extended_id(self) -> str:
        return getid(self.decklist_extended)

    @property
    def json(self) -> str:
        """Return a JSON representation of this deck.
        """
        data = {
            "metadata": self.metadata,
            "decklist_id": self.decklist_id,
            "decklist_extended_id": self.decklist_extended_id,
        }
        return json.dumps(data, indent=4, ensure_ascii=False, default=serialize_dates)

    def to_json(self, dstdir: PathLike = "", filename="") -> None:
        """Export to a .json file.

        JSON exported to file holds the whole decklist (in extended format) on not only IDs.

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            filename: optionally, a custom filename for the exported deck (if not provided a name based on this deck's data and metadata is constructed)
        """
        Exporter(self, filename).to_json(dstdir)


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
        "aetherhub.com": "Aetherhub",
        "archidekt.com": "Archidekt",
        'decks.tcgplayer.com': "TCGplayer",
        'deckstats.net': "Deckstats",
        'flexslot.gg': "Flexslot",
        'infinite.tcgplayer.com': "TCGplayer",
        'manastack.com': "Manastack",
        "melee.gg": "MeleeGG",
        'moxfield.com': "Moxfield",
        "mtg.cardsrealm.com": "Cardsrealm",
        "mtga.untapped.gg": "Untapped",
        "mtgarena.pro": "MGTArenaPro",
        "mtgazone.com": "MGTAZone",
        'mtgdecks.net': "MTGDecks",
        'mtgmelee.com': "MeleeGG",
        'mtgtop8.com': "MTGTop8",
        'old.starcitygames.com': "Starcity",
        'pennydreadfulmagic.com': "PDMagic",
        'scryfall.com': "Scryfall",
        "tappedout.net": "TappedOut",
        'www.archidekt.com': "Archidekt",
        "www.cardhoarder.com": "Cardhoarder",
        "www.hareruya.com": "Hareruya",
        'www.manatraders.com': "Manatraders",
        'www.moxfield.com': "Moxfield",
        'www.mtggoldfish.com': "Goldfish",
        'www.mtgotraders.com': "MTGOTraders",
        'www.mtgtop8.com': "MTGTop8",
        'www.streamdecker.com': "Streamdecker",
        'www.topdecked.com': "TopDecked",
    }

    FMT_NICKNAMES = {
        'alchemy': "Alh",
        'brawl': "Bwl",
        'commander': "Cmd",
        'duel': "Dl",
        'explorer': "Exp",
        'future': "Ftr",
        'gladiator': "Gld",
        'historic': "Hst",
        'legacy': "Lgc",
        'modern': "Mdn",
        'oathbreaker': "Oth",
        'oldschool': "Old",
        'pauper': "Ppr",
        'paupercommander': "PprCmd",
        'penny': "Pnn",
        'pioneer': "Pnr",
        'predh': "Pdh",
        'premodern': "PreMdn",
        'standard': "Std",
        'standardbrawl': "StdBwl",
        'timeless': "Tml",
        'vintage': "Vnt",
    }

    def __init__(self, deck: Deck, filename="") -> None:
        self._deck = deck
        self._filename = filename or self._build_filename()

    @classmethod
    def _normalize(cls, name: str) -> str:
        name = name.replace(" ", cls.NAME_SEP).replace("-", cls.NAME_SEP)
        name = cls.NAME_SEP.join([p.title() for p in name.split(cls.NAME_SEP)])
        name = name.replace(f"5c{cls.NAME_SEP}", f"5C{cls.NAME_SEP}").replace(
            f"4c{cls.NAME_SEP}", f"4C{cls.NAME_SEP}")
        name = name.replace(f"Five{cls.NAME_SEP}Color{cls.NAME_SEP}", f"5C{cls.NAME_SEP}").replace(
            f"Four{cls.NAME_SEP}Color{cls.NAME_SEP}", f"4C{cls.NAME_SEP}")
        return name

    def _build_filename_core(self) -> str:
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

    def _build_filename(self) -> str:
        # prefix (source/author)
        source = self.SOURCE_NICKNAMES.get(self._deck.source) or ""
        prefix = source if self._deck.is_meta_deck and source else self._deck.metadata.get(
            "author", "")
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
            name += self._build_filename_core()
        # set
        if set_code := self._deck.latest_set:
            name += set_code.upper()
        return name

    @staticmethod
    def _to_forge_line(playset: list[Card]) -> str:
        card = playset[0]
        return f"{len(playset)} {card.first_face_name}|{card.set.upper()}|1"

    # TODO: stop using filename to encode deck metadata (see use of self._parse_filename())
    def _build_forge(self) -> str:
        commander = [
            self._to_forge_line(playset) for playset in
            aggregate(self._deck.commander).values()] if self._deck.commander else []
        if self._deck.partner_commander:
            commander += [self._to_forge_line(playset) for playset in aggregate(
                self._deck.partner_commander).values()]
        maindeck = [
            self._to_forge_line(playset) for playset in aggregate(*self._deck.maindeck).values()]
        sideboard = [
            self._to_forge_line(playset) for playset in
            aggregate(*self._deck.sideboard).values()] if self._deck.sideboard else []
        return self.DCK_TEMPLATE.format(
            self._filename, "\n".join(commander), "\n".join(maindeck), "\n".join(sideboard))

    def to_forge(self, dstdir: PathLike = "") -> None:
        dstdir = dstdir or OUTPUT_DIR / "dck"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._filename}.dck"
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(self._build_forge(), encoding="utf-8")

    @classmethod
    def _parse_filename(cls, name: str) -> Json:
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
        commander, maindeck, sideboard, metadata = None, [], [], {}
        commander_on, maindeck_on, sideboard_on = False, False, False
        for line in file.read_text(encoding="utf-8").splitlines():
            if line.startswith("Name="):
                # TODO: stop using filename to encode deck metadata
                metadata = cls._parse_filename(line.removeprefix("Name="))
            elif line == "[Commander]":
                commander_on = True
                continue
            elif line == "[Main]":
                commander_on, maindeck_on = False, True
                continue
            elif line == "[Sideboard]":
                maindeck_on, sideboard_on = False, True
                continue
            elif not line:
                continue

            if commander_on:
                commander = cls._parse_forge_line(line)[0]
            elif maindeck_on:
                maindeck += cls._parse_forge_line(line)
            elif sideboard_on:
                sideboard += cls._parse_forge_line(line)

        deck = Deck(maindeck, sideboard, commander, metadata=metadata)
        if not deck:
            raise ParsingError(f"Unable to parse '{path}' into a deck")
        return deck

    @staticmethod
    def _to_playset_line(playset: list[Card], extended=False) -> str:
        card = playset[0]
        card_name = card.name.replace(
            SCRYFALL_MULTIFACE_SEPARATOR,
            ARENA_MULTIFACE_SEPARATOR) if card.is_multifaced else card.name
        line = f"{len(playset)} {card_name}"
        if extended:
            line += f" ({card.set.upper()}) {card.collector_number}"
        return line

    def build_decklist(self, extended=True, about=True) -> str:
        lines = []
        if about and self._deck.metadata.get("name"):
            lines += ["About", f'Name {self._deck.metadata["name"]}', ""]
        if self._deck.commander:
            playset = aggregate(self._deck.commander)[self._deck.commander]
            lines += ["Commander", self._to_playset_line(playset, extended=extended)]
            if self._deck.partner_commander:
                playset = aggregate(self._deck.partner_commander)[self._deck.partner_commander]
                lines += [self._to_playset_line(playset, extended=extended)]
            lines += [""]
        if self._deck.companion:
            playset = aggregate(self._deck.companion)[self._deck.companion]
            lines += ["Companion", self._to_playset_line(playset, extended=extended), ""]
        deck_playsets = sorted(
            (playset for playset in aggregate(*self._deck.maindeck).values()),
            key=lambda l: l[0].name)
        lines += [
            "Deck",
            *[self._to_playset_line(playset, extended=extended) for playset
              in deck_playsets]
        ]
        if self._deck.sideboard:
            side_playsets = sorted(
                (playset for playset in aggregate(*self._deck.sideboard).values()),
                key=lambda l: l[0].name)
            lines += [
                "",
                "Sideboard",
                *[self._to_playset_line(playset, extended=extended) for playset
                  in side_playsets]
            ]
        return "\n".join(lines)

    def to_arena(self, dstdir: PathLike = "") -> None:
        dstdir = dstdir or OUTPUT_DIR / "arena"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._filename}.txt"
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(self.build_decklist(), encoding="utf-8")

    @classmethod
    def from_arena(cls, path: PathLike) -> Deck:
        # TODO: solve circular imports more elegantly
        from mtg.deck.arena import ArenaParser, is_arena_line, is_empty
        file = getfile(path, ext=".txt")
        lines = file.read_text(encoding="utf-8").splitlines()
        if not all(is_arena_line(l) or is_empty(l) for l in lines):
            raise ValueError(f"Not an MTG Arena deck file: '{file}'")
        metadata = cls._parse_filename(file.name)
        deck = ArenaParser(lines, metadata).parse(
            suppress_parsing_errors=False, suppress_invalid_deck=False)
        if not deck:
            raise ParsingError(f"Unable to parse '{path}' into a deck")
        return deck

    def to_json(self, dstdir: PathLike = "") -> None:
        data = {
            "metadata": self._deck.metadata,
            "decklist": self.build_decklist(),
        }
        data = json.dumps(data, indent=4, ensure_ascii=False, default=serialize_dates)
        dstdir = dstdir or OUTPUT_DIR / "json"
        dstdir = getdir(dstdir)
        dst = dstdir / f"{self._filename}.json"
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(data, encoding="utf-8")


class _ParsingStates(Enum):
    """Enumeration of parsing states.
    """
    IDLE = auto()
    MAINDECK = auto()
    SIDEBOARD = auto()
    COMMANDER = auto()
    COMPANION = auto()


class _ParsingState:
    """State machine for deck parsing.
    """
    @property
    def state(self) -> _ParsingStates:
        return self.__state

    @state.setter
    @type_checker(_ParsingStates, is_method=True)
    def state(self, value: _ParsingStates) -> None:
        if value is self.state:
            raise ParsingError(f"Invalid transition from {self.state.name!r} to {value.name!r}")
        self.__state = value

    @property
    def is_idle(self) -> bool:
        return self.state is _ParsingStates.IDLE

    @property
    def is_maindeck(self) -> bool:
        return self.state is _ParsingStates.MAINDECK

    @property
    def is_sideboard(self) -> bool:
        return self.state is _ParsingStates.SIDEBOARD

    @property
    def is_commander(self) -> bool:
        return self.state is _ParsingStates.COMMANDER

    @property
    def is_companion(self) -> bool:
        return self.state is _ParsingStates.COMPANION

    def __init__(self) -> None:
        self.__state = _ParsingStates.IDLE

    def shift_to_maindeck(self) -> None:
        self.state = _ParsingStates.MAINDECK

    def shift_to_sideboard(self) -> None:
        self.state = _ParsingStates.SIDEBOARD

    def shift_to_commander(self) -> None:
        self.state = _ParsingStates.COMMANDER

    def shift_to_companion(self) -> None:
        self.state = _ParsingStates.COMPANION

    def shift_to_idle(self) -> None:
        self.state = _ParsingStates.IDLE


class CardNotFound(ParsingError):
    """Raised on card not being found.
    """

SANITIZED_FORMATS = {
    "1v1 commander": "commander",
    "archon": "commander",
    "artisan historic": "historic",
    "artisanhistoric": "historic",
    "australian highlander": "commander",
    "australianhighlander": "commander",
    "canadian highlander": "commander",
    "canadianhighlander": "commander",
    "cedh": "commander",
    "centurion": "commander",
    "clegacy": "legacy",
    "cmodern": "modern",
    "commander / edh": "commander",
    "commander 1v1": "commander",
    "commander/edh": "commander",
    "commanderprecon": "commander",
    "commanderprecons": "commander",
    "cpauper": "pauper",
    "cpioneer": "pioneer",
    "cstandard": "standard",
    "cvintage": "vintage",
    "duel commander": "duel",
    "duel-commander": "duel",
    "duelcommander": "duel",
    "duelcommanderrussian": "duel",
    "edh": "commander",
    "european highlander": "commander",
    "europeanhighlander": "commander",
    "future standard": "future",
    "highlander australian": "commander",
    "highlander canadian": "commander",
    "highlander european": "commander",
    "highlander": "commander",
    "highlanderaustralian": "commander",
    "highlandercanadian": "commander",
    "highlandereuropean": "commander",
    "historic brawl": "brawl",
    "historic pauper": "historic",
    "historic-pauper": "historic",
    "historicbrawl": "brawl",
    "historicpauper": "historic",
    "no banned list modern": "modern",
    "old school": "oldschool",
    "old-school": "oldschool",
    "oldschool 93/94": "oldschool",
    "past standard": "standard",
    "pauper commander": "paupercommander",
    "pauper edh": "paupercommander",
    "pauperedh": "paupercommander",
    "penny dreadful": "penny",
    "standard brawl": "standardbrawl",
    "vintage old school": "oldschool",
}


class DeckParser(ABC):
    """Abstract base deck parser.
    """
    @property
    def fmt(self) -> str:
        return self._metadata.get("format", "")

    def __init__(self, metadata: Json | None = None) -> None:
        self._metadata = metadata or {}
        self._state = _ParsingState()
        self._maindeck, self._sideboard = [], []
        self._commander, self._partner_commander, self._companion = None, None, None

    def _set_commander(self, card: Card) -> None:
        if not card.commander_suitable:
            _log.warning(f"'{card}' is not suitable for a commander role as per regular rules")

        if self._commander:
            if self._partner_commander:
                _log.warning("Partner commander already set")
                self._maindeck.append(card)
            else:
                if non_partner := from_iterable((self._commander, card), lambda c: not c.is_partner):
                    _log.warning(
                        f"Each partner commander should have a 'Partner' or 'Friends forever' "
                        f"keyword, '{non_partner}' doesn't")
                self._partner_commander = card
        else:
            self._commander = card

    def _derive_commander_from_sideboard(self):
        if self.fmt in COMMANDER_FORMATS and len(self._sideboard) in (1, 2) and all(
                c.commander_suitable for c in self._sideboard):
            for c in self._sideboard:
                self._set_commander(c)
            self._sideboard = []


    @classmethod
    def find_card(
            cls, name: str,
            set_and_collector_number: tuple[str, str] | None = None,
            scryfall_id="",
            oracle_id="",
            tcgplayer_id: int | None = None,
            cardmarket_id: int | None = None,
            mtgo_id: int | None = None,
            foreign=False) -> Card:
        name = cls.sanitize_card_name(name)
        if set_and_collector_number:
            if card := find_by_collector_number(*set_and_collector_number):
                # don't assume set/collector number data is always correct in the input data
                if card.name == name:
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
        if foreign:
            card = query_api_for_card(name, foreign=True)
        else:
            card = find_by_name(name)
        if not card:
            raise CardNotFound(f"Unable to find card {name!r}")
        return card

    @staticmethod
    def get_playset(card: Card, quantity: int) -> list[Card]:
        return [card] * quantity

    @staticmethod
    def sanitize_card_name(text: str) -> str:
        text = text.replace("’", "'").replace("‑", "-").replace("꞉", ":")
        if "/" in text:
            text = text.replace(" / ", f" {SCRYFALL_MULTIFACE_SEPARATOR} ").replace(
                f" {ARENA_MULTIFACE_SEPARATOR} ", f" {SCRYFALL_MULTIFACE_SEPARATOR} ")
            # "Wear/Tear" ==> "Wear // Tear"
            # "Wear//Tear" ==> "Wear // Tear"
            # "Wear///Tear" ==> "Wear // Tear"
            text = re.sub(
                r'(?<=[a-zA-Z])/{1,3}(?=[a-zA-Z])', f' {SCRYFALL_MULTIFACE_SEPARATOR} ', text)
        return text

    @abstractmethod
    def _pre_parse(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _parse_metadata(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _parse_decklist(self) -> None:
        raise NotImplementedError

    def parse(
            self, suppress_parsing_errors=True,
            suppress_invalid_deck=True) -> Deck | None:  # override
        try:
            self._pre_parse()
            self._parse_metadata()
            self._parse_decklist()
        except ParsingError as pe:
            if not suppress_parsing_errors:
                _log.error(f"Parsing failed with: {pe}")
                raise pe
            _log.warning(f"Parsing failed with: {pe}")
            return None
        try:
            return self._build_deck()
        except InvalidDeck as err:
            if not suppress_invalid_deck:
                _log.error(f"Parsing failed with: {err}")
                raise err
            _log.warning(f"Parsing failed with: {err}")
            return None

    def _update_fmt(self, fmt: str) -> None:
        fmt = fmt.strip().lower()
        fmt = SANITIZED_FORMATS.get(fmt, fmt)
        if fmt != self.fmt:
            if fmt in all_formats():
                self._metadata["format"] = fmt
            else:
                _log.warning(f"Irregular format: {fmt!r}")
                if self._metadata.get("format"):
                    del self._metadata["format"]
                self._metadata["irregular_format"] = fmt

    def _update_custom_theme(self, prefix: str, custom_theme: str) -> None:
        self._metadata[f"{prefix}_theme"] = custom_theme
        if theme := from_iterable(THEMES, lambda t: t in custom_theme):
            self._metadata["theme"] = theme

    def _build_deck(self) -> Deck:
        return Deck(
            self._maindeck, self._sideboard, self._commander, self._partner_commander,
            self._companion, self._metadata)
