"""

    mtgcards.decks.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse decklist URL/text for decks data.

    @author: z33k

"""
import itertools
import logging
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import date
from enum import Enum
from functools import cached_property, lru_cache
from operator import itemgetter
from typing import Iterable

from bs4 import BeautifulSoup

from mtgcards.const import Json
from mtgcards.scryfall import Card, Color, find_by_name, format_cards as scryfall_fmt_cards, \
    get_set, set_cards as scryfall_set_cards
from mtgcards.utils import from_iterable, getrepr, timed_request
from mtgcards.utils.files import getdir

_log = logging.getLogger(__name__)


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
    RAMP= "ramp"


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

class InvalidDeckError(ValueError):
    """Raised on invalid decks.
    """


def to_playsets(*cards: Card) -> defaultdict[Card, list[Card]]:
    playsets = defaultdict(list)
    for card in cards:
        if card.has_special_rarity:
            raise InvalidDeckError(f"Invalid rarity for {card.name!r}: {card.rarity.value!r}")
        playsets[card].append(card)
    return playsets


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
    def all_cards(self) -> list[Card]:
        return [*self.mainboard, *self.sideboard]

    @property
    def color_identity(self) -> Color:
        return Color.from_cards(self.all_cards)

    @property
    def artifacts(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_artifact]

    @property
    def battles(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_battle]

    @property
    def creatures(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_creature]

    @property
    def enchantments(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_enchantment]

    @property
    def instants(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_instant]

    @property
    def lands(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_land]

    @property
    def planeswalkers(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_planeswalker]

    @property
    def sorceries(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_sorcery]

    @property
    def commons(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_common]

    @property
    def uncommons(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_uncommon]

    @property
    def rares(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_rare]

    @property
    def mythics(self) -> list[Card]:
        return [card for card in self.mainboard if card.is_mythic]

    @property
    def total_rarity_weight(self) -> float:
        return sum(card.rarity.weight for card in self.mainboard)

    @property
    def avg_rarity_weight(self):
        return self.total_rarity_weight / len(self.mainboard)

    @property
    def avg_cmc(self) -> float:
        cards = [card.cmc for card in self.mainboard if card.cmc]
        return sum(cards) / len(cards)

    @property
    def price(self) -> float:
        return sum(c.price for c in self.mainboard if c.price)

    @property
    def price_tix(self) -> float:
        return sum(c.price_tix for c in self.mainboard if c.price_tix)

    @property
    def sets(self) -> list[str]:
        return sorted({c.set for c in self.all_cards if not c.is_basic_land})

    @property
    def color(self) -> Color:
        if self.name:
            return from_iterable(
                Color, lambda c: any(p.title() == c.name.title() for p in self.name.split()))
        return self.color_identity

    @property
    def theme(self) -> str | None:
        if not self.name:
            return None
        nameparts = [
            p for p in self.name.split() if not p.title() in [c.name.title() for c in Color]]
        return from_iterable(
                THEMES, lambda th: any(p.title() == th.title() for p in nameparts))

    @property
    def archetype(self) -> Archetype:
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

    def __init__(
            self, mainboard: Iterable[Card], sideboard: Iterable[Card] | None = None,
            commander: Card | None = None, companion: Card | None = None,
            metadata: Json | None = None) -> None:
        sideboard = [*sideboard] if sideboard else []
        self._companion = companion
        sideboard = [companion, *sideboard] if companion else sideboard
        self._metadata = metadata or {}

        self._commander = commander
        if commander:
            for card in [*mainboard, *sideboard]:
                if any(letter not in commander.colors for letter in card.colors):
                    raise InvalidDeckError(
                        f"Color of {card} doesn't match commander color: "
                        f"{card.colors}!={commander.colors}")

        self._max_playset_count = 1 if commander is not None else 4
        self._playsets = to_playsets(*mainboard)
        self._validate_mainboard()
        self._sideboard_playsets = None
        if sideboard:
            self._sideboard_playsets = to_playsets(*sideboard)
            self._validate_sideboard()

    def _validate_playset(self, playset: list[Card]) -> None:
        card = playset[0]
        if card.is_basic_land or card.allowed_multiples is Ellipsis:
            pass
        else:
            max_playset = self.max_playset_count if card.allowed_multiples is None \
                else card.allowed_multiples
            if len(playset) > max_playset:
                raise InvalidDeckError(
                    f"Too many occurrences of {card.name!r}: "
                    f"{len(playset)} > {max_playset}")

    def _validate_mainboard(self) -> None:
        for playset in self._playsets.values():
            self._validate_playset(playset)
        length = len(self.mainboard) + (1 if self.commander else 0)
        if length < self.MIN_MAINBOARD_SIZE:
            raise InvalidDeckError(
                f"Invalid deck size: {length} < {self.MIN_MAINBOARD_SIZE}")

    def _validate_sideboard(self) -> None:
        temp_playsets = to_playsets(*self.all_cards)
        for playset in temp_playsets.values():
            self._validate_playset(playset)
        if len(self.sideboard) > self.MAX_SIDEBOARD_SIZE:
            raise InvalidDeckError(
                f"Invalid sideboard size: {len(self.sideboard)} > {self.MAX_SIDEBOARD_SIZE}")

    def __repr__(self) -> str:
        reprs = [("name", self.name)] if self.name else []
        reprs += [
            ("avg_cmc", f"{self.avg_cmc:.2f}"),
            ("avg_rarity_weight", f"{self.avg_rarity_weight:.1f}"),
            ("color_identity", self.color_identity.name),
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
        reprs.append(("sideboard", self.has_sideboard))
        return getrepr(self.__class__, *reprs)

    def export(self, dstdir: str = os.getcwd(), name="") -> None:
        """Export to a Forge MTG deckfile format (.dck).

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            name: optionally, a custom name for the exported deck (if not provided a name based on this deck's data and metadata is constructed)
        """
        exp = DckExporter(self, name)
        dstdir = getdir(dstdir)
        dst = dstdir / exp.filename
        _log.info(f"Exporting deck to: '{dst}'...")
        dst.write_text(exp.export(), encoding="utf-8")

    def update_metadata(self, **data: Json) -> None:
        self._metadata.update(data)


class DckExporter:
    """Export a deck to a Forge MTG's .dck file.
    """
    TEMPLATE = """[metadata]
Name={}
[Commander]
{}
[Main]
{}
[Sideboard]
{}
"""
    SOURCE_NICKNAMES = {
        "www.mtggoldfish.com": "Goldfish"
    }

    FMT_NICKNAMES = {
        'alchemy': "Alc",
        'brawl': "Brl",
        'commander': "Cmd",
        'explorer': "Exp",
        'historic': "Hst",
        'modern': "Mdn",
        'pauper': "Ppr",
        'pioneer': "Pnr",
        'standard': "Std",
        'standardbrawl': "StdBrl",
        'timeless': "Tml"
    }
    @property
    def filename(self) -> str:
        return f"{self._name}.dck"

    def __init__(self, deck: Deck, name="") -> None:
        self._deck = deck
        self._name = name or self._build_name()

    # takes a few seconds to complete (due to using get_set())
    def _derive_most_recent_set(self) -> str | None:
        set_codes = {c.set for c in self._deck.mainboard if not c.is_basic_land}
        sets = [get_set(s) for s in set_codes]
        sets = [s for s in sets if s is not None and s.set_type() == "expansion"]
        sets = [(s, date.fromisoformat(s.released_at())) for s in sets]
        if not sets:
            return None
        sets.sort(key=itemgetter(1))
        return [s[0].code() for s in sets][-1]

    def _build_name(self) -> str:
        # source
        source = self.SOURCE_NICKNAMES.get(self._deck.source) or ""
        name = f"{source}_" if source else ""
        # color
        name += f"Mono_{self._deck.color.name.title()}_" if len(
            self._deck.color.value) == 1 else f"{self._deck.color.name.title()}_"
        # theme
        if self._deck.theme:
            name += f"{self._deck.theme}_"
        # archetype
        name += f"{self._deck.archetype.name.title()}_"
        # meta
        if any("meta" in k for k in self._deck.metadata):
            name += "Meta_"
            meta_place = self._deck.metadata.get("meta_place")
            if meta_place:
                name += f"#{meta_place}_"
        # format
        if self._deck.format:
            set_code = self._derive_most_recent_set()
            if set_code:
                name += f"{set_code.upper()}_{self.FMT_NICKNAMES[self._deck.format.lower()]}"
            else:
                name += self.FMT_NICKNAMES[self._deck.format.lower()]
        return name

    @staticmethod
    def _to_line(playset: list[Card]) -> str:
        card = playset[0]
        return f"{len(playset)} {card.main_name}|{card.set.upper()}|1"

    def export(self) -> str:
        commander = [
            self._to_line(playset) for playset in
            to_playsets(self._deck.commander).values()] if self._deck.commander else []
        mainboard = [
            self._to_line(playset) for playset in to_playsets(*self._deck.mainboard).values()]
        sideboard = [
            self._to_line(playset) for playset in
            to_playsets(*self._deck.sideboard).values()] if self._deck.sideboard else []
        return self.TEMPLATE.format(
            self._name, "\n".join(commander), "\n".join(mainboard), "\n".join(sideboard))


@lru_cache
def format_cards(fmt: str) -> set[Card]:
    return scryfall_fmt_cards(fmt)


@lru_cache
def set_cards(set_code: str) -> set[Card]:
    return scryfall_set_cards(set_code)


class UrlParser(ABC):
    """Abstract base parser of URLs pointing to decklists.
    """
    @property
    def url(self) -> str:
        return self._url

    @property
    def deck(self) -> Deck | None:
        return self._deck

    def __init__(self, url: str, fmt="standard") -> None:
        self._url, self._fmt = url, fmt
        self._deck = None

    def _get_soup(self, **requests_kwargs) -> BeautifulSoup:
        self._markup = timed_request(self._url, **requests_kwargs)
        return BeautifulSoup(self._markup, "lxml")

    @abstractmethod
    def _get_deck(self) -> Deck | None:
        raise NotImplementedError

    def _get_playset(self, name: str, quantity: int, set_code="") -> list[Card]:
        if set_code:
            cards = set_cards(set_code)
            card = find_by_name(name, cards)
            if card:
                return [card] * quantity
        card = find_by_name(name, format_cards(self._fmt))
        return [card] * quantity if card else []


