"""

    mtgcards.decks.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse decklist URL/text for decks data.

    @author: z33k

"""
from abc import ABC, abstractmethod
from functools import lru_cache

from bs4 import BeautifulSoup

from mtgcards.scryfall import Card, Deck, find_by_name, format_cards as scryfall_fmt_cards, \
    set_cards
from mtgcards.utils import timed_request


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

THEMES = {
    # https://edhrec.com/themes
    "Apostles",  # Shadowborn Apostles
    "Approach",  # Dragon's Approach
    "Aristocrats",
    "Artifact",
    "Artifacts",
    "Auras",
    "Big Mana",
    "Blink",
    "Bounce",
    "Burn",
    "Cantrips",
    "Card Draw",
    "Cascade",
    "Chaos",
    "Cheerios",
    "Clones",
    "Clues",
    "Convoke",
    "Counters",
    "Counterspells",
    "Curses",
    "Cycling",
    "Deathtouch",
    "Devotion",
    "Discard",
    "Eldrazi",  # Eldrazi Tokens
    "Enchantments",
    "Energy",
    "Equipment",
    "Exile",
    "Extra Combats",
    "Extra Turns",
    "Fight",
    "Flash",
    "Flying",
    "Forced Combat",
    "Foretell",
    "Goblins",  # Goblin Tokens
    "Graveyard",
    "Hatebears",
    "Hate Bears",
    "Historic",
    "Hug",  # Group Hug
    "Infect",
    "Jegantha",  # Jegantha Companion
    "Kaheera",  # Kaheera Companion
    "Keruga",  # Keruga Companion
    "Keywords",
    "Land Destruction",
    "Landfall",
    "Land",
    "Lands",
    "Legends",
    "Life Gain",
    "Lifegain",
    "Madness",
    "Mill",
    "Monarch",
    "Morph",
    "Mutate",
    "Ninjutsu",
    "Party",
    "Petitioners",  # Persistent Petitioners
    "Pingers",
    "Planeswalkers",
    "Pod",
    "Politics",
    "Polymorph",
    "Populate",
    "Power",
    "Prowess",
    "Ramp",
    "Rat Colony",
    "Rats",  # Relentless Rats
    "Reanimator",
    "Sacrifice",
    "Sagas",
    "Saprolings",  # Saproling Tokens
    "Sea Creatures",
    "Self Mill",
    "Self-Mill",
    "Slug",  # Group Slug
    "Snow",
    "Soldiers",  # Soldier Tokens
    "Spell Copy",
    "Spellslinger",
    "Spirits",  # Spirit Tokens
    "Stax",
    "Stompy",
    "Storm",
    "Sunforger",
    "Surge",  # Primal Surge
    "Theft",
    "Tokens",
    "Topdeck",
    "Top-Deck",
    "Toughness",
    "Treasure",
    "Treasures",
    "Umori",
    "Unnatural",
    "Vehicles",
    "Voltron",
    "Wheels",
    "X Spells",
    "X",
    "Zombies",  # Zombie Tokens
    # https://draftsim.com/mtg-deck-themes/
    "Affinity",
    "Draw Go",
    "Draw-Go",
    "Fliers",
    "Go Wide",
    "Go-Wide",
    "Rock",
    "The Rock",
    "Tribal",
    "Typal",
    "Weenie",
    # https://cardgamebase.com/commander-precons/
    "Aggression",
    "All-Color",
    "All-Colors",
    "Angels",
    "Backup",
    "Beasts",
    "Blitz",
    "Blood",
    "Casualty",
    "Cats",
    "Colorless",
    "Connive",
    "Coven",
    "Demons",
    "Deserts",
    "Dinosaurs",
    "Domain",
    "Dragons",
    "Dungeons",
    "Elves",
    "Enrage",
    "Evasion",
    "Explore",
    "Face-Down",
    "Faeries",
    "Five-Color",
    "Five-Colors",
    "Flashback",
    "Food",
    "Four-Color",
    "Four-Colors",
    "Goad",
    "Horrors",
    "Humans",
    "Incubate",
    "Instants",
    "Knights",
    "Life Loss",
    "Lifeloss",
    "Merfolk",
    "Modify",
    "Outlaws",
    "Phyrexians",
    "Pirates",
    "Poison",
    "Rogues",
    "Scry",
    "Slivers",
    "Surveil",
    "Suspend",
    "Time",
    "Value",
    "Vampires",
    "Venture",
    "Voting",
    "Wizards",
    # https://www.mtgsalvation.com/forums/the-game/commander-edh/806251-all-the-commander-edh-deck-archetypes-and-themes
    "Defenders",
    "Deflection",
    "Eggs",
    "Enchantress",
    "Flicker",
    "Judo",
    "Life Drain",
    "Lifedrain",
    "Miracle",
    "Miracle",
    "One-Shot",
    "Overrun",
    "Permission",
    "Pillow Fort",
    "Prison",
    "Rituals",
    "Sneak and Tell",
    "Suicide",
    "Superfriends",
    "Swarm",
    "Taxes",
    "Toolbox",
    "Tutors",
    "Weird",
    "X Creatures",
    # https://www.mtggoldfish.com/metagame/
    "Bogles",
    "Bully",
    "Dredge",
    "Heroic",
    "Ponza",
    "Scam",
    "Thopters",
    "Tron",
    "Zoo",
    # TODO: more
}

@lru_cache
def format_cards(fmt: str) -> set[Card]:
    return scryfall_fmt_cards(fmt)


class ParsingError(ValueError):
    """Raised on unexpected states of parsed data.
    """


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
        self._url, self._format_cards = url, format_cards(fmt)
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
        card = find_by_name(name, self._format_cards)
        return [card] * quantity if card else []
