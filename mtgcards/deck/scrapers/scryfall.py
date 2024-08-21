"""

    mtgcards.deck.scrapers.scryfall.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Scryfall decklists.

    @author: z33k

"""
import logging
from datetime import date

from bs4 import Tag

from mtgcards.const import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.scryfall import Card
from mtgcards.utils import extract_int
from mtgcards.utils.scrape import ScrapingError, getsoup

_log = logging.getLogger(__name__)


class ScryfallScraper(DeckScraper):
    """Scraper of Scryfall decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(self.url)
        self._scrape_metadata()
        self._scrape_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "scryfall.com/@" in url and "/decks/" in url

    @staticmethod
    def _sanitize_url(url: str) -> str:  # override
        if "?" in url:
            url, rest = url.split("?", maxsplit=1)
        return f"{url}?as=list&with=usd"

    def _scrape_metadata(self) -> None:  # override
        *_, author_part = self.url.split("@")
        author, *_ = author_part.split("/")
        self._metadata["author"] = author
        info_tag = self._soup.find("p", class_="deck-details-subtitle")
        fmt = info_tag.find("strong").text.strip().lower()
        self._update_fmt(fmt)
        date_text = info_tag.find("abbr").attrs["title"]
        date_text, _ = date_text.split(" ", maxsplit=1)
        self._metadata["date"] = date.fromisoformat(date_text)

    @classmethod
    def _parse_section(cls, section_tag: Tag) -> list[Card]:
        cards = []
        for li_tag in section_tag.find_all("li"):
            quantity = extract_int(li_tag.find("span", class_="deck-list-entry-count").text)
            name_tag = li_tag.find("span", class_="deck-list-entry-name")
            name = name_tag.text.strip()
            link = name_tag.find("a").attrs["href"]
            text = link.removeprefix("https://scryfall.com/card/")
            set_code, collector_number, *_ = text.split("/")
            card = cls.find_card(name, (set_code, collector_number))
            cards += cls.get_playset(card, quantity)
        return cards

    def _scrape_deck(self) -> None:  # override
        for section_tag in self._soup.find_all("div", class_="deck-list-section"):
            title = section_tag.find("h6").text
            cards = self._parse_section(section_tag)

            if "Commander" in title:
                for card in cards:
                    self._set_commander(card)
            elif "Sideboard" in title:
                self._sideboard = cards
            else:
                self._mainboard += cards

        self._build_deck()
