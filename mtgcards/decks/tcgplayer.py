"""

    mtgcards.decks.tcgplayer.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Parse TCG Player decklist page.

    @author: z33k

"""
import logging
import dateutil.parser
from datetime import datetime

from bs4 import Tag

from mtgcards.const import Json
from mtgcards.decks import Deck, DeckScraper, InvalidDeck, find_card_by_name, get_playset
from mtgcards.scryfall import Card
from mtgcards.utils import extract_int
from mtgcards.utils.scrape import ScrapingError, get_dynamic_soup_by_xpath, getsoup

_log = logging.getLogger(__name__)


class OldPageTcgPlayerScraper(DeckScraper):
    """Scraper of TCG Player old-style decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(url)
        self._scrape_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "decks.tcgplayer.com/" in url

    def _scrape_metadata(self) -> None:  # override
        info_tag = self._soup.find("div", class_="viewDeckHeader")
        h1_tag = info_tag.find("h1")
        self._metadata["name"] = h1_tag.find("a").text.strip()
        if not self.author:
            h3_tag = info_tag.find("h3")
            self._metadata["author"] = h3_tag.text.strip().removeprefix("by ")
        fmt_tag, _, date_tag, *_ = info_tag.find_all("div")[3:]
        fmt = fmt_tag.find("a").text.strip().lower()
        self._update_fmt(fmt)
        _, date_text = date_tag.text.strip().split("On: ", maxsplit=1)
        self._metadata["date"] = datetime.strptime(date_text, "%d/%m/%Y").date()

    def _process_deck_tag(self, deck_tag: Tag) -> list[Card]:
        cards = []
        card_tags = deck_tag.find_all("a", class_="subdeck-group__card")
        for card_tag in card_tags:
            quantity_tag, name_tag = card_tag.find_all("span")
            quantity = extract_int(quantity_tag.text)
            cards += get_playset(find_card_by_name(name_tag.text.strip(), fmt=self.fmt), quantity)
        return cards

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander = [], [], None
        deck_tags = self._soup.find_all("div", class_="subdeck")
        for deck_tag in deck_tags:
            if deck_tag.find("h3").text.lower().startswith("command"):
                cards = self._process_deck_tag(deck_tag)
                if not len(cards) == 1:
                    raise ScrapingError("Commander must have exactly one card")
                commander = cards[0]
            elif deck_tag.find("h3").text.lower().startswith("sideboard"):
                sideboard = self._process_deck_tag(deck_tag)
            else:
                mainboard = self._process_deck_tag(deck_tag)

        try:
            return Deck(mainboard, sideboard, commander, metadata=self._metadata)
        except InvalidDeck as err:
            _log.warning(f"Scraping failed with: {err}")
            return None


class NewPageTcgPlayerScraper(DeckScraper):
    """Scraper of TCG Player new-style decklist page.
    """
    _XPATH = "//span[contains(@class, 'list__item--wrapper')]"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup, _, _ = get_dynamic_soup_by_xpath(url, self._XPATH)
        self._scrape_metadata()
        self._deck = self._get_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "infinite.tcgplayer.com/magic-the-gathering/deck/" in url

    def _scrape_metadata(self) -> None:  # override
        name_tag = self._soup.find(
            "h2", class_=lambda c: c and "martech-heading" in c and "martech-inter" in c)
        self._metadata["name"] = name_tag.text.strip()
        fmt_tag = self._soup.find(
            "a", class_="martech-base-link", href=lambda h: h and "/format/" in h)
        if fmt_tag:
            self._update_fmt(fmt_tag.text.strip().lower())
        if not self.author:
            author_tag = self._soup.find(
                "a", class_="martech-base-link", href=lambda h: h and "/player/" in h)
            self._metadata["author"] = author_tag.text.strip()
        date_tag = self._soup.find("p", class_="event-name martech-text-sm")
        if date_tag:
            self._metadata["date"] = dateutil.parser.parse(date_tag.text.strip()).date()

    def _process_deck_tag(self, deck_tag: Tag) -> list[Card]:
        cards = []
        # card_tags = deck_tag.find_all("a", class_="subdeck-group__card")
        # for card_tag in card_tags:
        #     quantity_tag, name_tag = card_tag.find_all("span")
        #     quantity = extract_int(quantity_tag.text)
        #     cards += get_playset(name_tag.text.strip(), quantity, fmt=self.fmt)
        return cards

    def _get_deck(self) -> Deck | None:  # override
        mainboard, sideboard, commander = [], [], None
        card_tags = self._soup.find_all("span", class_="list__item--wrapper")
        # deck_tags = self._soup.find_all("div", class_="subdeck")
        # for deck_tag in deck_tags:
        #     if deck_tag.find("h3").text.lower().startswith("command"):
        #         cards = self._process_deck_tag(deck_tag)
        #         if not len(cards) == 1:
        #             raise ScrapingError("Commander must have exactly one card")
        #         commander = cards[0]
        #     elif deck_tag.find("h3").text.lower().startswith("sideboard"):
        #         sideboard = self._process_deck_tag(deck_tag)
        #     else:
        #         mainboard = self._process_deck_tag(deck_tag)

        try:
            return Deck(mainboard, sideboard, commander, metadata=self._metadata)
        except InvalidDeck as err:
            _log.warning(f"Scraping failed with: {err}")
            return None
