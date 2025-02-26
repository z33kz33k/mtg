"""

    mtg.deck.scrapers.edhrec.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape EDHREC decklists.

    @author: z33k

"""
import json
import logging
from datetime import datetime

from bs4 import BeautifulSoup

from mtg import Json
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)


def _get_deck_data(url: str) -> tuple[Json, BeautifulSoup]:
    soup = getsoup(url)
    if not soup:
        raise ScrapingError("Page not available")
    script_tag = soup.find("script", id="__NEXT_DATA__")
    try:
        data = json.loads(script_tag.text)
        deck_data = data["props"]["pageProps"]["data"]
    except (AttributeError, KeyError):
        raise ScrapingError("Deck data not available")
    return deck_data, soup


@DeckScraper.registered
class EdhRecPreviewDeckScraper(DeckScraper):
    """Scraper of EDHREC preview decklist page.
    """
    COLORS_TO_BASIC_LANDS = {
        "W": "Plains",
        "U": "Island",
        "B": "Swamp",
        "R": "Mountain",
        "G": "Forest",
    }

    @property
    def cards(self) -> list[Card]:
        cards = []
        if self._commander:
            cards.append(self._commander)
        if self._partner_commander:
            cards.append(self._partner_commander)
        cards += self._maindeck
        return cards

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "edhrec.com/" in url.lower() and "/deckpreview/" in url.lower()

    def _pre_parse(self) -> None:  # override
        self._deck_data, self._soup = _get_deck_data(self.url)

    def _parse_metadata(self) -> None:  # override
        self._update_fmt("commander")
        self._metadata["date"] = datetime.fromisoformat(self._deck_data["savedate"]).date()
        if header := self._deck_data.get("header"):
            self._metadata["name"] = header
        self._metadata["is_cedh"] = self._deck_data["cedh"]
        if edhrec_tags := self._deck_data.get("edhrec_tags"):
            self._metadata["edhrec_tags"] = edhrec_tags
        if tags := self._deck_data.get("tags"):
            self._metadata["tags"] = tags
        if salt := self._deck_data.get("salt"):
            self._metadata["salt"] = salt
        if theme := self._deck_data.get("theme"):
            self._metadata["theme"] = theme
        if tribe := self._deck_data.get("tribe"):
            self._metadata["tribe"] = tribe

    def _add_basic_lands(self) -> None:
        lands = [self.COLORS_TO_BASIC_LANDS[c] for c in self._deck_data["coloridentity"]]
        pool = [self.find_card(l) for l in lands]
        cursor = 0
        while len(self.cards) < 100:
            self._maindeck.append(pool[cursor])
            cursor += 1
            if cursor == len(pool):
                cursor = 0

    def _parse_decklist(self) -> None:  # override
        for card_name in self._deck_data["cards"]:
            self._maindeck += self.get_playset(self.find_card(card_name), 1)

        for card_name in [c for c in self._deck_data["commanders"] if c]:
            card = self.find_card(card_name)
            self._set_commander(card)

        self._add_basic_lands()


# @DeckScraper.registered
# class EdhRecAverageDeckScraper(DeckScraper):
#     """Scraper of EDHREC average decklist page.
#     """
#     @staticmethod
#     def is_deck_url(url: str) -> bool:  # override
#         return "edhrec.com/" in url.lower() and "/average-decks/" in url.lower()
#
#     def _pre_parse(self) -> None:  # override
#         self._deck_data, self._soup = _get_deck_data(self.url)
#
#     def _parse_metadata(self) -> None:  # override
#         self._update_fmt("commander")
#         self._metadata["date"] = datetime.fromisoformat(self._deck_data["savedate"]).date()
#         if header := self._deck_data.get("header"):
#             self._metadata["name"] = header
#         self._metadata["is_cedh"] = self._deck_data["cedh"]
#         if edhrec_tags := self._deck_data.get("edhrec_tags"):
#             self._metadata["edhrec_tags"] = edhrec_tags
#         if tags := self._deck_data.get("tags"):
#             self._metadata["tags"] = tags
#         if salt := self._deck_data.get("salt"):
#             self._metadata["salt"] = salt
#         if theme := self._deck_data.get("theme"):
#             self._metadata["theme"] = theme
#         if tribe := self._deck_data.get("tribe"):
#             self._metadata["tribe"] = tribe
#
#     def _parse_decklist(self) -> None:  # override
#         for card_name in self._deck_data["cards"]:
#             self._maindeck += self.get_playset(self.find_card(card_name), 1)
#
#         for card_name in [c for c in self._deck_data["commanders"] if c]:
#             card = self.find_card(card_name)
#             self._set_commander(card)


