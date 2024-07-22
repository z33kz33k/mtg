"""

    mtgcards.decks.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse decklist URL/text for decks data.

    @author: z33k

"""
import itertools
from abc import ABC, abstractmethod
from collections import defaultdict
from functools import cached_property, lru_cache
from typing import Iterable

from bs4 import BeautifulSoup

from mtgcards.const import Json
from mtgcards.scryfall import Card, Color, find_by_name, format_cards as scryfall_fmt_cards, \
    set_cards as scryfall_set_cards
from mtgcards.utils import getrepr, timed_request


# based on https://draftsim.com/mtg-archetypes/
# this listing omits combo-control as it's too long a name to be efficiently used as a component
# of a catchy deck name
# in those scenarios usually a deck's theme (sub-archetype) is used (e.g. "stax" or "prison")
ARCHETYPES = {
    "aggro",
    "midrange",
    "control",
    "combo",
    "tempo",
    "ramp"
}

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

    @cached_property
    def mainboard(self) -> list[Card]:
        return [*itertools.chain(*self._playsets.values())]

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
    def metadata(self) -> Json:
        return self._metadata

    @property
    def name(self) -> str | None:
        return self.metadata.get("name")

    @property
    def author(self) -> str | None:
        return self.metadata.get("author")

    def __init__(
            self, mainboard: Iterable[Card], sideboard: Iterable[Card] | None = None,
            commander: Card | None = None, companion: Card | None = None,
            metadata: Json | None = None) -> None:
        self._sideboard = [*sideboard] if sideboard else []
        self._companion = companion
        self._sideboard = [companion, *self.sideboard] if companion else self.sideboard
        self._metadata = metadata or {}

        self._commander = commander
        if commander:
            for card in [*mainboard, *self.sideboard]:
                if any(letter not in commander.colors for letter in card.colors):
                    raise InvalidDeckError(
                        f"Color of {card} doesn't match commander color: "
                        f"{card.colors}!={commander.colors}")
            mainboard = [commander, *mainboard]

        self._max_playset_count = 1 if commander is not None else 4
        self._playsets = to_playsets(*mainboard)
        self._validate_mainboard()
        if self.sideboard:
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
        if len(self.mainboard) < self.MIN_MAINBOARD_SIZE:
            raise InvalidDeckError(
                f"Invalid deck size: {len(self.mainboard)} < {self.MIN_MAINBOARD_SIZE}")

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


class DckExporter:
    """Export a deck to a Forge MTG's .dck file.
    """
    TEMPLATE = """
[metadata]
Name={}
[Commander]
{}
[Main]
{}
[Sideboard]
{}
"""
    def __init__(self, deck: Deck) -> None:
        self._deck = deck


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


