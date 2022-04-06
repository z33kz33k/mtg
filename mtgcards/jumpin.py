"""

    mtgcards.jumpin.py
    ~~~~~~~~~~~~~~~~~~
    Scrape official WotC JumpIn! page for decks data.

    @author: z33k

"""
from collections import namedtuple
from dataclasses import dataclass
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from bs4.element import ResultSet, Tag
from mtgcards.utils import from_iterable, timed_request

from mtgcards.goldfish.cards import Card as GoldfishCard, find_card, Price

URL = "https://magic.wizards.com/en/articles/archive/magic-digital/innistrad-crimson-vow-jump-" \
      "event-details-and-packets-2021-11-10"


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


@dataclass
class RotatedCard(Card):
    appear_chance: int  # percents
    alternative: Optional["Card"] = None  # injected post-initialization

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


@dataclass
class Deck:
    name: str
    cards: List[Card]

    @property
    def count(self) -> int:
        return sum(card.quantity for card in self.cards)

    @property
    def price(self) -> Optional[Price]:
        if not self.cards:
            return None
        # TODO: more elaborate approach that factors in alternatives
        total = sum(card.goldfish_data.price.value * card.quantity for card in self.cards
                    if card.goldfish_data.price is not None)
        return Price(total, self.cards[0].goldfish_data.price.unit)


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
        self._decklists, self._rotation_tables = self._parse_page()
        self.decks = self._get_decks(self._decklists, self._rotation_tables)

    @staticmethod
    def _parse_page() -> Tuple[ResultSet, ResultSet]:
        markup = timed_request(URL)
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
            name = info.text
            set_code = info.attrs["data-cardexpansion"]
            number = int(info.attrs["data-cardnumber"])
            link = info.attrs["href"]
        else:
            name = row.find("span", class_="card-name").text
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
                alt_card = Card(row.altcard.name, None, None, None, card.quantity, altgoldfish)
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
            cards = [self._parse_row(row) for row in rows]
            rotation_table = self._parse_rotation_table(table)
            new_cards = self._apply_rotations(cards, rotation_table)
            deck = Deck(deckname, new_cards)
            decks.append(deck)

        return decks


