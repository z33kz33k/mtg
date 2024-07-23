"""

    mtgcards.goldfish.cards.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape www.mtggoldfish.com for MtG cards data.

    @author: z33k

"""
import json
import random
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import Tag

from mtgcards.const import INPUTDIR, Json, OUTPUTDIR
from mtgcards.goldfish.sets import DOMAIN, MODERN_META_SETS, MtgSet, PIONEER_META_SETS, \
    STANDARD_META_SETS, SetFormat
from mtgcards.goldfish.sets import URL as SETS_URL
from mtgcards.utils import from_iterable, timed_request
from mtgcards.utils.files import getdir, getfile

URL_TEMPLATE = SETS_URL + "{}#online"
INPUTDIR = f"{INPUTDIR}/goldfish"


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

    @staticmethod
    def to_json_name(mana: "Mana") -> str:
        if mana in HYBRID_MANA:
            return mana.name.lower()
        return mana.value

    @staticmethod
    def from_json_name(name: str) -> "Mana":
        if "hybrid" in name:
            return Mana[name.upper()]
        return Mana(name)


HYBRID_MANA = [mana for mana in Mana if "HYBRID" in mana.name]


class Rarity(Enum):
    BASIC_LAND = "Basic Land"
    COMMON = "Common"
    UNCOMMON = "Uncommon"
    RARE = "Rare"
    MYTHIC = "Mythic"
    SPECIAL = "Special"


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

    @staticmethod
    def from_str(text: str) -> "Price":
        if "$" in text:
            _, price = text.split()
            return Price(float(price), PriceUnit.DOLLAR)
        elif "tix" in text:
            price, _ = text.split()
            return Price(float(price), PriceUnit.TIX)
        else:
            raise ValueError(f"Invalid price string: {text}.")


@dataclass
class Card:
    number: int | None  # some cards in Alchemy have no number
    name: str
    link: str
    # phyrexian mana (e.g. in Modern Masters 2015:
    # https://gatherer.wizards.com/Pages/Card/Details.aspx?multiverseid=512288)
    # is not (easily) parseable on mtggoldfish
    mana: tuple[Mana, ...] | None
    rarity: Rarity | None
    price: Price | None
    mtg_set: MtgSet | None = None

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

    def as_json(self, set_included=True) -> Json:
        mana = [Mana.to_json_name(mana) for mana in self.mana] if self.mana is not None else None
        result = {
                "name": self.name,
                "set": self.mtg_set.value.code,
                "number": self.number,
                "rarity": self.rarity.value if self.rarity else None,
                "mana": mana,
                "price": str(self.price) if self.price else None,
                "link": self.link,
            }
        if set_included:
            return result
        del result["set"]
        return result

    @staticmethod
    def from_json(data: Json) -> "Card":
        if data["mana"] is None:
            mana = None
        else:
            mana = tuple([Mana.from_json_name(name) for name in data["mana"]])
        return Card(
            data["number"],
            data["name"],
            data["link"],
            mana,
            Rarity(data["rarity"]) if data["rarity"] is not None else None,
            Price.from_str(data["price"]) if data["price"] is not None else None,
        )


@dataclass
class SetData:
    cards: list[Card]
    mtg_set: MtgSet

    @property
    def as_json(self) -> Json:
        return {
            self.mtg_set.value.code: [card.as_json(set_included=False) for card in self.cards]
        }

    @staticmethod
    def from_json(cards_data: list[Json], mtg_set: MtgSet) -> "SetData":
        cards = [Card.from_json(card_data) for card_data in cards_data]
        for card in cards:
            card.mtg_set = mtg_set
        return SetData(cards, mtg_set)

    def find(self, name: str) -> Card | None:
        """Find a card by ``name`` provided. Return ``None`` if nothing has been found.
        """
        return from_iterable(self.cards, lambda c: c.name == name)

    def find_by_number(self, number: int) -> Card | None:
        """Find a card by ``number`` provided. Return ``None`` if nothing has been found.
        """
        return from_iterable(self.cards, lambda c: c.number == number)

    def find_all(
            self, *, rarity: Rarity | None = None, price: float | None = None,
            text: str | None = None, mana: Mana | None = None,
            cmc: int | None = None, has_hybrid_mana: bool | None = None,
            has_x_mana: bool | None = None, has_colorless_mana: bool | None = None,
            has_colored_mana: bool | None = None) -> list[Card]:
        """Find all cards that meet specified parameters.

        Args:
            rarity: matched card's rarity
            price: matched card's price
            text: a text in matched card's name
            mana: matched card's mana as tuple of Mana enumerations
            cmc: matched card's converted mana cost
            has_hybrid_mana: True, if matched card has hybrid mana
            has_x_mana: True, if matched card has X mana
            has_colorless_mana: True, if matched card has colorless mana
            has_colored_mana: True, if matched card has colored mana
        """
        mtgcards = self.cards[:]
        if rarity:
            mtgcards = [card for card in mtgcards if card.rarity is rarity]
        if price:
            mtgcards = [card for card in mtgcards if card.price.value == price]
        if text:
            mtgcards = [card for card in mtgcards if text in card.name]
        if mana is not None:
            mtgcards = [card for card in mtgcards if card.mana == mana]
        if cmc is not None:
            mtgcards = [card for card in mtgcards if card.cmc == cmc]
        if has_hybrid_mana is not None:
            mtgcards = [card for card in mtgcards if card.has_hybrid_mana]
        if has_x_mana is not None:
            mtgcards = [card for card in mtgcards if card.has_x_mana]
        if has_colorless_mana is not None:
            mtgcards = [card for card in mtgcards if card.has_colorless_mana]
        if has_colored_mana is not None:
            mtgcards = [card for card in mtgcards if card.has_colored_mana]
        return mtgcards


def _get_table(mtg_set: MtgSet) -> Tag | None:
    link = mtg_set.value.link[6:]
    url = URL_TEMPLATE.format(link)
    markup = timed_request(url)
    soup = BeautifulSoup(markup, "lxml")
    return soup.find("table", class_="card-container-table table table-striped table-sm")


def _getrows(table: Tag) -> list[Tag]:
    body = table.find("tbody")
    return [el for el in body.children][1:]


def _parse_row(row: Tag, mtg_set: MtgSet | None = None) -> Card:
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
        try:
            mana = _parse_mana(mana)
        except ValueError:
            print(f"WARNING: not parseable mana string: {mana!r}. Mana for {name!r} set to `None`")
            mana = None
    if not rarity.text:
        rarity = None
    else:
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


def _parse_mana(text: str) -> tuple[Mana, ...]:
    text = text.replace("mana cost: ", "")
    tokens = text.split()
    manas, is_hybrid, hybrid_mana = [], False, []
    for token in tokens:
        if not is_hybrid:
            if token == "phyrexian":
                break
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


def scrape(mtg_set: MtgSet) -> SetData:
    tbl = _get_table(mtg_set)
    rows = _getrows(tbl)
    cards = [_parse_row(row, mtg_set) for row in rows]
    return SetData(cards, mtg_set)


def json_dump(fmt: SetFormat = SetFormat.STANDARD, filename: str | None = None) -> None:
    if fmt is SetFormat.STANDARD:
        metas = STANDARD_META_SETS
    elif fmt is SetFormat.PIONEER:
        metas = PIONEER_META_SETS
    else:
        metas = MODERN_META_SETS

    if not filename:
        filename = fmt.name.lower() + ".json"
    dest = getdir(OUTPUTDIR) / filename

    setmap, total = {}, len(metas)
    for i, meta_set in enumerate(metas, start=1):
        mtg_set = MtgSet(meta_set)
        data = scrape(mtg_set)
        setmap.update(data.as_json)
        print(f"{i}/{total} set has been parsed.")
        time.sleep(random.uniform(0.15, 0.3))

    with dest.open("w", encoding="utf-8") as f:
        json.dump(setmap, f, indent=2)

    if dest.exists():
        print(f"All data successfully dumped at {dest!r}.")
    else:
        print(f"WARNING! Nothing has been saved at {dest!r}.")


STANDARD_JSON_FILE = getfile(str(Path(INPUTDIR) / "standard.json"))
PIONEER_JSON_FILE = getfile(str(Path(INPUTDIR) / "pioneer.json"))
MODERN_JSON_FILE = getfile(str(Path(INPUTDIR) / "modern.json"))
with STANDARD_JSON_FILE.open() as sf:
    STANDARD_JSON = json.load(sf)
with PIONEER_JSON_FILE.open() as pf:
    PIONEER_JSON = json.load(pf)
with MODERN_JSON_FILE.open() as mf:
    MODERN_JSON = json.load(mf)


def getset(mtg_set: MtgSet) -> SetData | None:
    """Return set specified by ``mtg_set`` enumeration or ``None`` if there's no such data.
    """
    allinput = {**STANDARD_JSON, **PIONEER_JSON, **MODERN_JSON}
    cards_data = allinput.get(mtg_set.value.code)
    if cards_data:
        return SetData.from_json(cards_data, mtg_set)
    return None


def getsets(*sets: MtgSet) -> list[SetData]:
    """Return sets' data specified by the enumerated ``sets``.
    """
    result = []
    for mtgset in sets:
        setdata = getset(mtgset)
        if setdata:
            result.append(setdata)
    return result


def get_sets_by_format(fmt: SetFormat = SetFormat.STANDARD) -> list[SetData]:
    """Return all sets belonging to the specified format.
    """
    def parse_json(data: Json) -> list[SetData]:
        result = []
        for code, card_data in data.items():
            mtgset = MtgSet.from_code(code)
            result.append(SetData.from_json(card_data, mtgset))
        return result

    if fmt is SetFormat.MODERN:
        return parse_json(MODERN_JSON)
    elif fmt is SetFormat.PIONEER:
        return parse_json(PIONEER_JSON)
    else:
        return parse_json(STANDARD_JSON)


def find_card(name: str, fmt: SetFormat = SetFormat.STANDARD) -> Card | None:
    """Find a card with ``name`` in all sets of format ``fmt``. Return ``None`` if nothing matches.
    """
    sets = get_sets_by_format(fmt)
    for s in sets:
        card = s.find(name)
        if card:
            return card
    return None


def find_cards(
        fmt: SetFormat = SetFormat.STANDARD, *, rarity: Rarity | None = None,
        price: float | None = None, text: str | None = None,
        mana: Mana | None = None, cmc: int | None = None,
        has_hybrid_mana: bool | None = None, has_x_mana: bool | None = None,
        has_colorless_mana: bool | None = None,
        has_colored_mana: bool | None = None) -> list[Card]:
    """Find all cards in the specified format that meet specified parameters.

    Args:
        fmt: format to match cards in
        rarity: matched card's rarity
        price: matched card's price
        text: a text in matched card's name
        mana: matched card's mana as tuple of Mana enumerations
        cmc: matched card's converted mana cost
        has_hybrid_mana: True, if matched card has hybrid mana
        has_x_mana: True, if matched card has X mana
        has_colorless_mana: True, if matched card has colorless mana
        has_colored_mana: True, if matched card has colored mana
    """
    sets = get_sets_by_format(fmt)
    mtgcards = [card for s in sets for card in s.cards]
    if rarity:
        mtgcards = [card for card in mtgcards if card.rarity is rarity]
    if price:
        mtgcards = [card for card in mtgcards if card.price.value == price]
    if text:
        mtgcards = [card for card in mtgcards if text in card.name]
    if mana is not None:
        mtgcards = [card for card in mtgcards if card.mana == mana]
    if cmc is not None:
        mtgcards = [card for card in mtgcards if card.cmc == cmc]
    if has_hybrid_mana is not None:
        mtgcards = [card for card in mtgcards if card.has_hybrid_mana]
    if has_x_mana is not None:
        mtgcards = [card for card in mtgcards if card.has_x_mana]
    if has_colorless_mana is not None:
        mtgcards = [card for card in mtgcards if card.has_colorless_mana]
    if has_colored_mana is not None:
        mtgcards = [card for card in mtgcards if card.has_colored_mana]
    return mtgcards

