"""

    mtgcards.deck.scrapers.scryfall.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse Scryfall decklist page.

    @author: z33k

"""
import logging
from datetime import datetime

from bs4 import Tag

from mtgcards.const import Json
from mtgcards.deck import Deck, InvalidDeck
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.scryfall import Card
from mtgcards.utils import extract_int
from mtgcards.utils.scrape import ScrapingError, get_dynamic_soup_by_xpath, getsoup

_log = logging.getLogger(__name__)


class ScryfallScraper(DeckScraper):
    """Scraper of Scryfall decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(self.url)
        self._scrape_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "scryfall.com/@" in url and "/decks/" in url

    @staticmethod
    def _sanitize_url(url: str) -> str:  # override
        if "?" in url:
            url, rest = url.split("?", maxsplit=1)
        return f"{url}?as=list&with=usd"

    def _scrape_metadata(self) -> None:  # override
        pass

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
            card = cls.find_card(name, set_and_collector_number=(set_code, collector_number))
            cards += cls.get_playset(card, quantity)
        return cards

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander = [], [], None

        for section_tag in self._soup.find_all("div", class_="deck-list-section"):
            title_tag = section_tag.find("h6")
            cards = self._parse_section(section_tag)

            if "Commander" in title_tag.text:
                if len(cards) != 1:
                    raise ScrapingError("Multiple commander card tags")
                commander = cards[0]
            elif "Sideboard" in title_tag.text:
                sideboard = cards
            else:
                mainboard += cards

        try:
            return Deck(mainboard, sideboard, commander, metadata=self._metadata)
        except InvalidDeck as err:
            _log.warning(f"Scraping failed with: {err}")
            return None
