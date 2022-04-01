"""

    mtgcards
    ~~~~~~~~
    Root package.

    @author: z33k

"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from bs4.element import Tag

from mtgcards.utils import timed_request


__version__ = "0.1.0"


class MtgSet(Enum):
    ALCHEMY = "Y22"
    ZENDIKAR_RISING = "ZNR"
    KALDHEIM = "KHM"
    STRIXHAVEN_MYSTICAL_ARCHIVE = "STA"
    STRIXHAVEN_SCHOOL_OF_MAGES = "STX"
    ADVENTURES_IN_THE_FORGOTTEN_REALMS = "AFR"
    INNISTRAD_MIDNIGHT_HUNT = "MID"
    INNISTRAD_CRIMSON_VOW = "VOW"
    KAMIGAWA_NEON_DYNASTY = "NEO"


SET_URL_MAP = {
    MtgSet.ZENDIKAR_RISING: "Zendikar+Rising",
    MtgSet.KALDHEIM: "Kaldheim",
    MtgSet.STRIXHAVEN_MYSTICAL_ARCHIVE: "Strixhaven+Mystical+Archive",
    MtgSet.STRIXHAVEN_SCHOOL_OF_MAGES: "Strixhaven+School+of+Mages",
    MtgSet.ADVENTURES_IN_THE_FORGOTTEN_REALMS: "Adventures+in+the+Forgotten+Realms",
    MtgSet.INNISTRAD_MIDNIGHT_HUNT: "Innistrad+Midnight+Hunt",
    MtgSet.INNISTRAD_CRIMSON_VOW: "Innistrad+Crimson+Vow",
    MtgSet.KAMIGAWA_NEON_DYNASTY: "Kamigawa+Neon+Dynasty",
    MtgSet.ALCHEMY: "Alchemy",
}
DOMAIN = "www.mtggoldfish.com"
URL_PREFIX = f"https://{DOMAIN}/sets/"
URL_TEMPLATE = URL_PREFIX + "{}#online"


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


class Rarity(Enum):
    COMMON = "Common"
    UNCOMMON = "Uncommon"
    RARE = "Rare"
    MYTHIC = "Mythic"


@dataclass
class Card:
    number: int
    name: str
    link: str
    mana: Tuple[Mana, ...]
    rarity: Rarity
    price: Optional[float]

    @property
    def cmc(self) -> int:
        """Return the converted mana cost of this card.
        """
        return len([m for m in self.mana if m is not Mana.X])


@dataclass
class SetData:
    cards: List[Card]


def _get_table(mtg_set: MtgSet) -> Optional[Tag]:
    url = URL_TEMPLATE.format(SET_URL_MAP[mtg_set])
    markup = timed_request(url)
    soup = BeautifulSoup(markup, "lxml")
    return soup.find("table", class_="card-container-table table table-striped table-sm")


def _get_rows(table: Tag) -> List[Tag]:
    body = table.find("tbody")
    return [el for el in body.children][1:]


def _parse_row(row: Tag) -> Card:
    number, link, mana, rarity, price = [td for td in row.children][:5]
    number = int(number.text)
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
            price = float(price.text[2:])
        elif "tix" in price.text:
            price = float(price.text[:-4])
        else:
            raise ValueError(f"Unexpected card price string format {price.text!r}.")
    else:
        price = None

    return Card(number, name, link, mana, rarity, price)


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
    rows = _get_rows(tbl)
    cards = [_parse_row(row) for row in rows]
    return SetData(cards)

