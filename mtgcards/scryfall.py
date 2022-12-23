"""

    mtgcards.scryfall.py
    ~~~~~~~~~~~~~~~~~~~
    Handle Scryfall data.

    @author: z33k

"""
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, List, Optional

import scrython

from mtgcards.utils import from_iterable
from mtgcards.utils.files import download_file, getdir
from mtgcards.const import DATADIR, Json

FILENAME = "scryfall.json"


def download_scryfall_bulk_data() -> None:
    """Download Scryfall 'Oracle Cards' bulk data JSON.
    """
    bd = scrython.BulkData()
    data = bd.data()[0]  # retrieve 'Oracle Cards' data dict
    url = data["download_uri"]
    download_file(url, file_name=FILENAME, dst_dir=DATADIR)


@dataclass
class Card:
    """Thin wrapper on Scryfall JSON data for an MtG card.

    Provides convenience access to most important data pieces.
    """
    json: Json

    @property
    def formats(self) -> List[str]:
        return sorted(fmt for fmt in self.legalities)

    @property
    def games(self) -> List[str]:
        return self.json["games"]

    @property
    def legalities(self) -> Dict[str, str]:
        return self.json["legalities"]

    @property
    def name(self) -> str:
        return self.json["name"]

    @property
    def set(self) -> str:
        return self.json["set"]

    @property
    def set_name(self) -> str:
        return self.json["set_name"]


@lru_cache
def bulk_data() -> List[Card]:
    """Return Scryfall JSON data as list of Card objects.
    """
    source = getdir(DATADIR) / FILENAME
    if not source.exists():
        download_scryfall_bulk_data()

    with source.open() as f:
        data = json.load(f)

    return [Card(card_data) for card_data in data]


def arena_data() -> List[Card]:
    """Return Scryfall bulk data filtered for only cards available on Arena.
    """
    return [card for card in bulk_data() if "arena" in card.games]


def game_designations(data: Optional[List[Card]] = None) -> List[str]:
    """Return list of string designations for games that can be played with cards in Scryfall data.
    """
    data = data if data else bulk_data()
    games = set()
    for card in data:
        games.update(card.games)

    return sorted(games)


def set_designations(data: Optional[List[Card]] = None) -> List[str]:
    """Return list of string designations for MtG sets in Scryfall data.
    """
    data = data if data else bulk_data()
    return sorted({card.set for card in data})


def format_designations() -> List[str]:
    return bulk_data()[0].formats


def set_names(data: Optional[List[Card]] = None) -> List[str]:
    """Return list of MtG set names in Scryfall data.
    """
    data = data if data else bulk_data()
    return sorted({card.set_name for card in data})


def find_cards(predicate: Callable[[Card], bool], data: Optional[List[Card]] = None) -> List[Card]:
    """Return list of cards from ``data`` that satisfies ``predicate``.
    """
    data = data if data else bulk_data()
    return [card for card in data if predicate(card)]
