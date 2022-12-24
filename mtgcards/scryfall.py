"""

    mtgcards.scryfall.py
    ~~~~~~~~~~~~~~~~~~~
    Handle Scryfall data.

    @author: z33k

"""
import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Callable, Dict, Iterable, List, Optional, Set

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
                     'transform']


class TypeLine:
    """Parser of type line in Scryfall data.
    """
    SEPARATOR = "—"

    @property
    def text(self) -> str:
        return self._text

    def __init__(self, text: str) -> None:
        self._text = text

    # TODO


@dataclass(frozen=True)
class CardFace:
    """Thin wrapper on card face data that lives inside Scryfall card data.

    Somewhat similar to regular card but much simpler.
    """
    json: Json

    @property
    def name(self) -> str:
        return self.json["name"]

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
    def colors(self) -> List[str]:
        return self.json["colors"]


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
    def color_identity(self) -> List[str]:
        return self.json["color_identity"]

    @property
    def colors(self) -> List[str]:
        colors = self.json.get("colors")
        return colors if colors else []

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
        elif self.legalities[fmt] == "not_legal":
            return False
        else:
            raise ScryfallError(f"Unexpected value for {fmt!r} legality: {self.legalities[fmt]!r}")

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
def bulk_data() -> Set[Card]:
    """Return Scryfall JSON data as list of Card objects.
    """
    source = getdir(DATADIR) / FILENAME
    if not source.exists():
        download_scryfall_bulk_data()

    with source.open() as f:
        data = json.load(f)

    return {Card(card_data) for card_data in data}


def arena_data() -> Set[Card]:
    """Return Scryfall bulk data filtered for only cards available on Arena.
    """
    return {card for card in bulk_data() if "arena" in card.games}


def games(data: Optional[Iterable[Card]] = None) -> List[str]:
    """Return list of string designations for games that can be played with cards in Scryfall data.
    """
    data = data if data else bulk_data()
    result = set()
    for card in data:
        result.update(card.games)

    return sorted(result)


def set_codes(data: Optional[Iterable[Card]] = None) -> List[str]:
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


def set_cards(set_code: str) -> Set[Card]:
    """Return card data for set designated by ``set_code``.

    Returns an empty set if set code is invalid.
    """
    return {card for card in bulk_data() if card.set == set_code.lower()}


def find_cards(predicate: Callable[[Card], bool],
               data: Optional[Iterable[Card]] = None) -> Set[Card]:
    """Return list of cards from ``data`` that satisfy ``predicate``.
    """
    data = data if data else bulk_data()
    return {card for card in data if predicate(card)}


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

