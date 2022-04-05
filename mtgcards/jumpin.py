"""

    mtgcards.jumpin.py
    ~~~~~~~~~~~~~~~~~~
    Scrape official WotC JumpIn! page for decks data.

    @author: z33k

"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from bs4.element import ResultSet, Tag
from mtgcards.utils import timed_request

from mtgcards.goldfish.cards import Card as GoldfishCard, find_card, Price

URL = "https://magic.wizards.com/en/articles/archive/magic-digital/innistrad-crimson-vow-jump-" \
      "event-details-and-packets-2021-11-10"


@dataclass
class Card:
    name: str
    number: int
    set_code: str
    gatherer_link: str
    quantity: int
    goldfish_data: Optional[GoldfishCard]


@dataclass
class ReplaceableCard(Card):
    appear_chance: int  # percents
    replacement: Optional["Card"] = None  # injected post-initialization

    @staticmethod
    def from_card(card: Card, appear_chance: int) -> "ReplaceableCard":
        return ReplaceableCard(
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
        # TODO: more elaborate approach that factors in replacements
        total = sum(card.goldfish_data.price.value * card.quantity for card in self.cards)
        return Price(total, self.cards[0].goldfish_data.price.unit)


class Parser:
    def __init__(self) -> None:
        self._decklists, self._tables = self._parse_page()
        self.decks = self._get_decks(self._decklists, self._tables)

    @staticmethod
    def _parse_page() -> Tuple[ResultSet, ResultSet]:
        markup = timed_request(URL)
        soup = BeautifulSoup(markup, "lxml")
        decklists = soup.find_all("div", class_="page-width bean_block bean_block_deck_list bean--"
                                                "wiz-content-deck-list clearfix")
        tables = soup.find_all("table", cellspacing="0", cellpadding="0", border="0")
        return decklists, tables

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
        name = info.text
        set_code = info.attrs["data-cardexpansion"]
        number = int(info.attrs["data-cardnumber"])
        link = info.attrs["href"]
        goldfish = find_card(name)
        return Card(name, number, set_code, link, quantity, goldfish)

    def _get_decks(self, decklists, tables) -> List[Deck]:
        if len(decklists) != len(tables):
            raise ValueError(f"Invalid input. Decklists and tables have different lengths "
                             f"({len(decklists)} != {len(tables)}).")
        decks = []
        for decklist, table in zip(decklists, tables):
            deckname, rows = self._parse_decklist(decklist)
            cards = [self._parse_row(row) for row in rows]
            deck = Deck(deckname, cards)
            # TODO: parse table for replacements


