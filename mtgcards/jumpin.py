"""

    mtgcards.jumpin.py
    ~~~~~~~~~~~~~~~~~~
    Scrape official WotC JumpIn! page for decks data.

    @author: z33k

"""
import json
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from bs4.element import ResultSet, Tag

from mtgcards.const import Json
from mtgcards.utils import from_iterable, timed_request

from mtgcards.goldfish.cards import Card as GoldfishCard, PriceUnit, find_card, Price

URL = "https://magic.wizards.com/en/articles/archive/magic-digital/innistrad-crimson-vow-jump-" \
      "event-details-and-packets-2021-11-10"
NEO_URL = "https://magic.wizards.com/en/articles/archive/magic-digital/jump-packets-update-" \
          "kamigawa-neon-dynasty-2022-02-11"


@dataclass
class Card:
    # some cards listed in decklists are not linked and hence lack data other than name and
    # quantity (e.g. Sigarda's Imprisonment in DISTURBED)
    name: str
    number: Optional[int]
    set_code: Optional[str]
    gatherer_link: Optional[str]
    quantity: int
    goldfish_data: Optional[GoldfishCard]

    @property
    def as_json(self) -> Json:
        return {
            "name": self.name,
            "number": self.number,
            "set_code": self.set_code,
            "gatherer_link": self.gatherer_link,
            "quantity": self.quantity,
        }

    @staticmethod
    def from_json(data: Json) -> "Card":
        return Card(
            data["name"],
            data["number"],
            data["set_code"],
            data["gatherer_link"],
            data["quantity"],
            find_card(data["name"])
        )


@dataclass
class AltCard:  # TODO: look below
    name: str
    appear_chance: int


@dataclass
class RotatedCard(Card):
    appear_chance: int  # percents
    # TODO: make a separate dataclass for alternative card that doesn't hold unnecessary fields:
    #  number, set_code, gatherer_link, quantity, alternative (that not only clog up memory
    #  but end up serialized to json for no good reason)
    alternative: Optional["RotatedCard"] = None  # injected post-initialization

    @property
    def as_json(self) -> Json:
        result = super().as_json
        result.update({
            "appear_chance": self.appear_chance,
            "alternative": self.alternative.as_json if self.alternative else None,
        })
        return result

    @staticmethod
    def from_json(data: Json) -> "RotatedCard":
        return RotatedCard(
            data["name"],
            data["number"],
            data["set_code"],
            data["gatherer_link"],
            data["quantity"],
            find_card(data["name"]),
            data["appear_chance"],
            # TODO: look at the above todo
            RotatedCard.from_json(data["alternative"])
        )

    @staticmethod
    def from_card(card: Card, appear_chance: int) -> "RotatedCard":
        return RotatedCard(
            card.name,
            card.number,
            card.set_code,
            card.gatherer_link,
            card.quantity,
            card.goldfish_data,
            appear_chance,
        )

    @property
    def rotated_price(self) -> Optional[Price]:
        """Return price for this rotated card calculated as an average of both rotation cards'
        prices weighted by chance of appearance. If none of rotated cards have price, return
        ``None``.
        """
        if self.alternative is None:
            return None
        if self.goldfish_data is None or self.goldfish_data.price is None:
            return self.alternative.goldfish_data.price
        if self.alternative.goldfish_data is None or self.alternative.goldfish_data.price is None:
            return self.goldfish_data.price
        price = self.goldfish_data.price.value
        altprice = self.alternative.goldfish_data.price.value
        price *= self.appear_chance / 100
        altprice *= self.alternative.appear_chance / 100
        newprice = price + altprice
        unit = self.goldfish_data.price.unit if self.goldfish_data.price else \
            self.alternative.goldfish_data.price.unit
        return Price(newprice, unit)


@dataclass
class Deck:
    name: str
    cards: List[Card]

    @property
    def as_json(self) -> Json:
        return {
            "name": self.name,
            "cards": [card.as_json for card in self.cards],
        }

    @staticmethod
    def from_json(data: Json) -> "Deck":
        cards = []
        for card_data in data["cards"]:
            if "appear_chance" in card_data:
                cards.append(RotatedCard.from_json(card_data))
            else:
                cards.append(Card.from_json(card_data))
        return Deck(
            data["name"],
            cards
        )

    @property
    def count(self) -> int:
        return sum(card.quantity for card in self.cards)

    @property
    def price(self) -> Optional[Price]:
        if not self.cards:
            return None
        total = 0
        for card in self.cards:
            if isinstance(card, RotatedCard):
                if card.rotated_price:
                    total += card.rotated_price.value * card.quantity
            else:
                if card.goldfish_data and card.goldfish_data.price:
                    total += card.goldfish_data.price.value * card.quantity

        if self.cards[0].goldfish_data and self.cards[0].goldfish_data.price:
            unit = self.cards[0].goldfish_data.price.unit
        else:
            unit = PriceUnit.DOLLAR
        return Price(total, unit)


ChanceCard = namedtuple("ChanceCard", "name chance")


@dataclass
class RotationTableRow:
    basecard: ChanceCard
    altcard: ChanceCard


@dataclass
class RotationTable:
    rows: List[RotationTableRow]


class Parser:
    def __init__(self) -> None:
        self._decklists, self._rotation_tables = self._parse_page(URL)
        self.decks = self._get_decks(self._decklists, self._rotation_tables)
        self._neo_decklists, self._neo_rotation_tables = self._parse_page(NEO_URL)
        self.decks += self._get_decks(self._neo_decklists, self._neo_rotation_tables)

    @staticmethod
    def _parse_page(url: str) -> Tuple[ResultSet, ResultSet]:
        markup = timed_request(url)
        soup = BeautifulSoup(markup, "lxml")
        decklists = soup.find_all("div", class_="page-width bean_block bean_block_deck_list bean--"
                                                "wiz-content-deck-list clearfix")
        rotation_tables = soup.find_all("table", cellspacing="0", cellpadding="0", border="0")
        return decklists, rotation_tables

    @staticmethod
    def _parse_decklist(decklist: Tag) -> Tuple[str, ResultSet]:
        inner_decklist = decklist.find("div", class_="sorted-by-overview-container sortedContainer")
        rows = inner_decklist.find_all("span", class_="row")
        deckname = decklist.find("h4").text
        return deckname, rows

    @staticmethod
    def _parse_row(row: Tag) -> Card:
        quantity = int(row.find("span", class_="card-count").text)
        info = row.find("a")
        if info:
            name = info.text.replace("’", "'")
            set_code = info.attrs["data-cardexpansion"]
            number = int(info.attrs["data-cardnumber"])
            link = info.attrs["href"]
        else:
            name = row.find("span", class_="card-name").text.replace("’", "'")
            set_code, number, link = None, None, None
        goldfish = find_card(name)
        return Card(name, number, set_code, link, quantity, goldfish)

    @staticmethod
    def _parse_rotation_table(table: Tag) -> RotationTable:
        body = table.find("tbody")
        rows = body.find_all("tr")
        new_rows = []
        for row in rows:
            card1, percent1, card2, percent2, *_ = row.find_all("td")
            card1 = card1.find("a").text
            percent1 = int(percent1.text[:-1])  # trim trailing `%`
            card2 = card2.find("a").text
            percent2 = int(percent2.text[:-1])  # trim trailing `%`
            new_row = RotationTableRow(ChanceCard(card1, percent1), ChanceCard(card2, percent2))
            new_rows.append(new_row)

        return RotationTable(new_rows)

    @staticmethod
    def _apply_rotations(cards: List[Card], rotation_table: RotationTable) -> List[Card]:
        new_cards = []
        for card in cards:
            row = from_iterable(rotation_table.rows, lambda r: r.basecard.name == card.name)
            if row:
                rotated_card = RotatedCard.from_card(card, row.basecard.chance)
                altgoldfish = find_card(row.altcard.name)
                alt_card = RotatedCard(row.altcard.name, None, None, None, card.quantity,
                                       altgoldfish, row.altcard.chance)
                rotated_card.alternative = alt_card
                new_cards.append(rotated_card)
            else:
                new_cards.append(card)
        return new_cards

    def _get_decks(self, decklists, rotation_tables) -> List[Deck]:
        if len(decklists) != len(rotation_tables):
            raise ValueError(f"Invalid input. Decklists and rotation_tables have different lengths "
                             f"({len(decklists)} != {len(rotation_tables)}).")
        decks = []
        for decklist, table in zip(decklists, rotation_tables):
            deckname, rows = self._parse_decklist(decklist)
            names = [deck.name for deck in decks]
            if deckname in names:
                continue
            cards = [self._parse_row(row) for row in rows]
            rotation_table = self._parse_rotation_table(table)
            new_cards = self._apply_rotations(cards, rotation_table)
            deck = Deck(deckname, new_cards)
            decks.append(deck)

        return decks

    def dump_json(self) -> None:
        dest = Path("output/jumpin.json")
        data = [deck.as_json for deck in self.decks]
        with dest.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        if dest.exists():
            print(f"All data successfully dumped at {dest!r}.")
        else:
            print(f"WARNING! Nothing has been saved at {dest!r}.")

    def dump_pricelist(self) -> None:
        dest = Path("output/jumpin_priced.txt")
        lines = []
        maxlen = max(len(deck.name) for deck in self.decks)
        for i, deck in enumerate(sorted(self.decks, key=lambda d: d.price.value, reverse=True),
                                 start=1):
            deckname = f"`{deck.name}`"
            decknum = str(i).zfill(2)
            lines.append(f"#{decknum}: {deckname.ljust(maxlen + 2)}: {str(deck.price):>7}")

        dest.write_text("\n".join(lines))

        if dest.exists():
            print(f"Decks pricelist successfully dumped at {dest!r}.")
        else:
            print(f"WARNING! Nothing has been saved at {dest!r}.")

