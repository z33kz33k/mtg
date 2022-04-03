"""

    mtgcards.goldfish.cards.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape www.mtggoldfish.com for MtG cards data.

    @author: z33k

"""
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from bs4.element import Tag

from mtgcards.utils import Json, timed_request, OUTPUTDIR
from mtgcards.goldfish.sets import URL as SETS_URL
from mtgcards.goldfish.sets import MtgSet, DOMAIN, STANDARD_META_SETS, PIONEER_META_SETS, \
    MODERN_META_SETS, SetFormat

URL_TEMPLATE = SETS_URL + "{}#online"


class Mana(Enum):
    X = "x"
    WHITE = "white"
    BLUE = "blue"
    BLACK = "black"
    RED = "red"
    GREEN = "green"
    COLORLESS = "colorless"
    # typo `hyrid` in the source HTML
    HYBRID_WHITE_BLUE = ("hyrid white blue", "hyrid blue white")
    HYBRID_WHITE_BLACK = ("hyrid white black", "hyrid black white")
    HYBRID_WHITE_RED = ("hyrid white red", "hyrid red white")
    HYBRID_WHITE_GREEN = ("hyrid white green", "hyrid green white")
    HYBRID_BLUE_BLACK = ("hyrid blue black", "hyrid black blue")
    HYBRID_BLUE_RED = ("hyrid blue red", "hyrid red blue")
    HYBRID_BLUE_GREEN = ("hyrid blue green", "hyrid green blue")
    HYBRID_BLACK_RED = ("hyrid black red", "hyrid red black")
    HYBRID_BLACK_GREEN = ("hyrid black green", "hyrid green black")
    HYBRID_RED_GREEN = ("hyrid red green", "hyrid green red")

    @staticmethod
    def parse_hybrid(text: str) -> "Mana":
        if text in Mana.HYBRID_WHITE_BLUE.value:
            return Mana.HYBRID_WHITE_BLUE
        elif text in Mana.HYBRID_WHITE_BLACK.value:
            return Mana.HYBRID_WHITE_BLACK
        elif text in Mana.HYBRID_WHITE_RED.value:
            return Mana.HYBRID_WHITE_RED
        elif text in Mana.HYBRID_WHITE_GREEN.value:
            return Mana.HYBRID_WHITE_GREEN
        elif text in Mana.HYBRID_BLUE_BLACK.value:
            return Mana.HYBRID_BLUE_BLACK
        elif text in Mana.HYBRID_BLUE_RED.value:
            return Mana.HYBRID_BLUE_RED
        elif text in Mana.HYBRID_BLUE_GREEN.value:
            return Mana.HYBRID_BLUE_GREEN
        elif text in Mana.HYBRID_BLACK_RED.value:
            return Mana.HYBRID_BLACK_RED
        elif text in Mana.HYBRID_BLACK_GREEN.value:
            return Mana.HYBRID_BLACK_GREEN
        elif text in Mana.HYBRID_RED_GREEN.value:
            return Mana.HYBRID_RED_GREEN
        else:
            raise ValueError(f"Unexpected hybrid mana string: {text!r}.")


HYBRID_MANA = [mana for mana in Mana if "HYBRID" in mana.name]


class Rarity(Enum):
    COMMON = "Common"
    UNCOMMON = "Uncommon"
    RARE = "Rare"
    MYTHIC = "Mythic"


class PriceUnit(Enum):
    DOLLAR = "$"
    TIX = "tix"


@dataclass
class Price:
    value: float
    unit: PriceUnit

    def __str__(self) -> str:  # override
        if self.unit is PriceUnit.DOLLAR:
            return f"{self.unit.value} {self.value:.2f}"
        else:
            return f"{self.value:.2f} {self.unit.value}"


@dataclass
class Card:
    number: Optional[int]  # some cards in Alchemy have no number
    name: str
    link: str
    mana: Tuple[Mana, ...]
    rarity: Rarity
    price: Optional[float]
    mtg_set: Optional[MtgSet] = None

    @property
    def cmc(self) -> int:
        """Return the converted mana cost of this card.
        """
        return sum(1 for m in self.mana if m is not Mana.X)

    @property
    def hybrid_mana_count(self) -> int:
        return sum(1 for mana in self.mana if mana in HYBRID_MANA)

    @property
    def has_hybrid_mana(self) -> bool:
        return self.hybrid_mana_count > 0

    @property
    def x_mana_count(self) -> int:
        return sum(1 for mana in self.mana if mana is Mana.X)

    @property
    def has_x_mana(self) -> bool:
        return self.x_mana_count > 0

    @property
    def colorless_mana_count(self) -> int:
        return sum(1 for mana in self.mana if mana is Mana.COLORLESS)

    @property
    def has_colorless_mana(self) -> bool:
        return self.colorless_mana_count > 0

    @property
    def colored_mana_count(self) -> int:
        return sum(1 for mana in self.mana if mana not in (Mana.COLORLESS, Mana.X))

    @property
    def has_colored_mana(self) -> bool:
        return self.colored_mana_count > 0

    @staticmethod
    def _json_mana_name(mana: Mana) -> str:
        if mana in HYBRID_MANA:
            return mana.name.lower()
        return mana.value

    def as_json(self, set_included=True) -> Json:
        result = {
                "name": self.name,
                "set": self.mtg_set.value.code,
                "number": self.number,
                "rarity": self.rarity.value,
                "mana": [self._json_mana_name(mana) for mana in self.mana],
                "price": str(self.price),
                "link": self.link,
            }
        if set_included:
            return result
        del result["set"]
        return result


@dataclass
class SetData:
    cards: List[Card]
    mtg_set: MtgSet

    @property
    def as_json(self) -> Json:
        return {
            self.mtg_set.value.code: [card.as_json(set_included=False) for card in self.cards]
        }


def _get_table(mtg_set: MtgSet) -> Optional[Tag]:
    link = mtg_set.value.link[6:]
    url = URL_TEMPLATE.format(link)
    markup = timed_request(url)
    soup = BeautifulSoup(markup, "lxml")
    return soup.find("table", class_="card-container-table table table-striped table-sm")


def _getrows(table: Tag) -> List[Tag]:
    body = table.find("tbody")
    return [el for el in body.children][1:]


def _parse_row(row: Tag, mtg_set: Optional[MtgSet] = None) -> Card:
    number, link, mana, rarity, price = [td for td in row.children][:5]
    number = int(number.text) if number.text else None
    link = link.find("a")
    # e.g. "Boseiju, Who Endures [NEO]" ==> "Boseiju, Who Endures"
    name = link.attrs["data-card-id"][:-6]
    link = DOMAIN + link.attrs["href"]
    mana = mana.find("span")
    if mana is None:
        mana = ()
    else:
        mana = mana.attrs["aria-label"]
        mana = _parse_mana(mana)
    rarity = Rarity(rarity.text)
    # e.g. "29.37 tix" ==> "29.37"
    if price.text:
        if "$" in price.text:
            # e.g. `$ 14.32`
            price = Price(float(price.text[2:]), PriceUnit(price.text[0]))
        elif "tix" in price.text:
            # e.g. `59.06 tix	`
            price = Price(float(price.text[:-4]), PriceUnit(price.text[-3:]))
        else:
            raise ValueError(f"Unexpected card price string format {price.text!r}.")
    else:
        price = None

    return Card(number, name, link, mana, rarity, price, mtg_set)


def _parse_mana(text: str) -> Tuple[Mana, ...]:
    text = text.replace("mana cost: ", "")
    tokens = text.split()
    manas, is_hybrid, hybrid_mana = [], False, []
    for token in tokens:
        if not is_hybrid:
            try:
                manas.append(Mana(token))
            except ValueError:
                if token == Mana.X.value:
                    manas.append(Mana.X)
                elif token.isdigit():
                    manas.extend([Mana.COLORLESS] * int(token))
                elif token == "hyrid":
                    is_hybrid = True
                    hybrid_mana.append(token)
                    continue
                else:
                    raise ValueError(f"Unexpected mana string format: {text!r}.")
        else:
            hybrid_mana.append(token)
            if len(hybrid_mana) == 3:
                manas.append(Mana.parse_hybrid(" ".join(hybrid_mana)))
                hybrid_mana = []
                is_hybrid = False

    return tuple(manas)


def getset(mtg_set: MtgSet) -> SetData:
    tbl = _get_table(mtg_set)
    rows = _getrows(tbl)
    cards = [_parse_row(row, mtg_set) for row in rows]
    return SetData(cards, mtg_set)


# TODO: use file utils here (getdir() and so on)
def json_dump(fmt: SetFormat = SetFormat.STANDARD, filename="cards.json") -> None:
    if fmt is SetFormat.STANDARD:
        metas = STANDARD_META_SETS
    elif fmt is SetFormat.PIONEER:
        metas = PIONEER_META_SETS
    else:
        metas = MODERN_META_SETS

    dest = OUTPUTDIR / filename

    sets = []
    for meta_set in metas:
        mtg_set = MtgSet(meta_set)
        time.sleep(0.2)
        data = getset(mtg_set)
        sets.append(data.as_json)

    with dest.open("w", encoding="utf-8") as f:
        json.dump({fmt.value: sets}, f, indent=2)

