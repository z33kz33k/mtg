"""

    mtg.deck.scrapers.cycles.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Cycles Gaming decklists.

    @author: z33k

"""
import logging

from bs4 import NavigableString, Tag
import dateutil.parser

from mtg import Json
from mtg.deck.scrapers import DeckTagsContainerScraper, TagBasedDeckParser
from mtg.utils.scrape import strip_url_query

_log = logging.getLogger(__name__)


class CyclesGamingDeckTagParser(TagBasedDeckParser):
    """Parser of Cycles Gaming decklist HTML tag.
    """

    def __init__(self, deck_tag: Tag, metadata: Json | None = None) -> None:
        super().__init__(deck_tag, metadata)
        self._parsed_multifaced = set()

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._deck_tag.text.strip().removeprefix("Decklist – ")

    @staticmethod
    def _parse_quantity(text: str) -> int:
        qty = 1
        if " " in text:
            qty_str, _ = text.split(maxsplit=1)
            if qty_str.isdigit():
                qty = int(qty_str)
        if "(" in text:
            _, qty_str = text.rsplit("(", maxsplit=1)
            qty_str = qty_str.removesuffix(")")
            if qty_str.isdigit():
                qty = int(qty_str)
        return qty

    def _parse_table(self, table: Tag) -> None:
        for row in table.find_all("tr"):
            td_tag, *_ = row.find_all("td")
            if not td_tag.text:
                continue
            a_tag = td_tag.find("a")
            name = a_tag.text.strip()
            qty = self._parse_quantity(td_tag.text.strip())
            card = self.find_card(name)
            if card.is_multifaced:
                if card in self._parsed_multifaced:
                    continue
                self._parsed_multifaced.add(card)
            playset = self.get_playset(card, qty)
            if self._state.is_commander:
                for card in playset:
                    self._set_commander(card)
            elif self._state.is_maindeck:
                self._maindeck += playset
            elif self._state.is_sideboard:
                self._sideboard += playset

    def _parse_decklist(self) -> None:  # override
        current = self._deck_tag.next_sibling
        while current:
            if current.name == "p" and "Format: " in current.text and current.text.strip(
                ).lower().startswith("by "):
                author, fmt = current.text.split("Format: ", maxsplit=1)
                self._metadata["author"] = author.strip().removeprefix("By ").removeprefix("by ")
                self._update_fmt(fmt.strip())
            elif current.name in ("p", "h3") and all(t in current.text for t in "()"):
                if "Sideboard" in current.text:
                    self._state.shift_to_sideboard()
                elif not self._state.is_maindeck:
                    self._state.shift_to_maindeck()
            elif current.name == "table":
                if self._state.is_idle:
                    self._state.shift_to_commander()
                self._parse_table(current)
            elif isinstance(current, NavigableString):
                pass
            else:
                break
            current = current.next_sibling

        if self._commander:
            self._update_fmt("commander")


@DeckTagsContainerScraper.registered
class CyclesGamingArticleScraper(DeckTagsContainerScraper):
    """Scraper of Cycles Gaming article page.
    """
    CONTAINER_NAME = "CyclesGaming article"
    DECK_PARSER = CyclesGamingDeckTagParser

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return f"cyclesgaming.com/" in url.lower() and "cyclesgaming.com/." not in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _parse_metadata(self) -> None:
        if info_tag := self._soup.find(
                "p", string=lambda s: s and "cycles" in s.lower() and ", " in s):
            author, date = info_tag.text.split(", ", maxsplit=1)
            self._metadata["author"] = author.strip().removeprefix("by ")
            try:
                self._metadata["date"] = dateutil.parser.parse(date.strip()).date()
            except dateutil.parser.ParserError:
                pass

    def _collect(self) -> list[Tag]:  # override
        self._parse_metadata()
        deck_tags = [tag for tag in self._soup.find_all("h2") if "list – " in tag.text.lower()]
        return deck_tags
