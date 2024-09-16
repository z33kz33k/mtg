"""

    mtgcards.deck.scrapers.tcgplayer.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TCG Player decklists.

    @author: z33k

"""
import logging
from datetime import datetime

import dateutil.parser
from bs4 import Tag
from selenium.common.exceptions import TimeoutException

from mtgcards import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.scryfall import Card
from mtgcards.utils import extract_int
from mtgcards.utils.scrape import ScrapingError, get_dynamic_soup_by_xpath, getsoup

_log = logging.getLogger(__name__)


@DeckScraper.registered
class OldPageTcgPlayerScraper(DeckScraper):
    """Scraper of TCG Player old-style decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "decks.tcgplayer.com/" in url and "/search" not in url

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
        info_tag = self._soup.find("div", class_="viewDeckHeader")
        h1_tag = info_tag.find("h1")
        self._metadata["name"] = h1_tag.find("a").text.strip()
        h3_tag = info_tag.find("h3")
        self._metadata["author"] = h3_tag.text.strip().removeprefix("by ")
        for sub_tag in info_tag.find_all("div"):
            if "Format:" in sub_tag.text:
                fmt = sub_tag.find("a").text.strip().lower()
                self._update_fmt(fmt)
            elif "Last Modified On:" in sub_tag.text:
                _, date_text = sub_tag.text.strip().split("On: ", maxsplit=1)
                self._metadata["date"] = datetime.strptime(date_text, "%m/%d/%Y").date()

    @classmethod
    def _process_deck_tag(cls, deck_tag: Tag) -> list[Card]:
        cards = []
        card_tags = deck_tag.find_all("a", class_="subdeck-group__card")
        for card_tag in card_tags:
            quantity_tag, name_tag = card_tag.find_all("span")
            quantity = extract_int(quantity_tag.text)
            cards += cls.get_playset(cls.find_card(name_tag.text.strip()), quantity)
        return cards

    def _parse_deck(self) -> None:  # override
        deck_tags = self._soup.find_all("div", class_="subdeck")
        for deck_tag in deck_tags:
            if deck_tag.find("h3").text.lower().startswith("command"):
                cards = self._process_deck_tag(deck_tag)
                for card in cards:
                    self._set_commander(card)
            elif deck_tag.find("h3").text.lower().startswith("sideboard"):
                self._sideboard = self._process_deck_tag(deck_tag)
            else:
                self._maindeck = self._process_deck_tag(deck_tag)


# TODO: there's actually a request to API for JSON I forgot to check:
#  https://infinite-api.tcgplayer.com/deck/magic/{DECK_ID}
#  /?source=infinite-content&subDecks=true&cards=true&stats=true - so this could probably be scraped
#  bypassing the soup (and Selenium)
@DeckScraper.registered
class NewPageTcgPlayerScraper(DeckScraper):
    """Scraper of TCG Player new-style decklist page.
    """
    _XPATH = "//span[contains(@class, 'list__item--wrapper')]"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "infinite.tcgplayer.com/magic-the-gathering/deck/" in url

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, _ = get_dynamic_soup_by_xpath(self.url, self._XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _parse_metadata(self) -> None:  # override
        name_tag = self._soup.find(
            "h2", class_=lambda c: c and "martech-heading" in c and "martech-inter" in c)
        self._metadata["name"] = name_tag.text.strip()
        fmt_tag = self._soup.find(
            "a", class_="martech-base-link", href=lambda h: h and "/format/" in h)
        if fmt_tag:
            self._update_fmt(fmt_tag.text.strip().lower())
        author_tag = self._soup.find(
            "a", class_="martech-base-link", href=lambda h: h and "/player/" in h)
        self._metadata["author"] = author_tag.text.strip()
        date_tag = self._soup.find("p", class_="event-name martech-text-sm")
        if date_tag:
            date_text = date_tag.text.strip()
            if "-" in date_text:
                *event_texts, date_text = date_text.split("-")
                self._metadata["event"] = "".join(event_texts).strip()
            self._metadata["date"] = dateutil.parser.parse(date_text.strip()).date()

    @classmethod
    def _to_playset(cls, card_tag: Tag) -> list[Card]:
        quantity = extract_int(card_tag.find("span", class_="list__item-quanity").text)
        name = card_tag.find("span", class_="list__item--wrapper").text.strip().removeprefix(
            str(quantity))
        return cls.get_playset(cls.find_card(name), quantity)

    def _parse_deck(self) -> None:  # override
        commander_tag = self._soup.find("div", class_="commandzone")
        if commander_tag:
            card_tags = commander_tag.find_all("li", class_="list__item")
            for card_tag in card_tags:
                self._set_commander(self._to_playset(card_tag)[0])

        main_tag = self._soup.find("div", class_="maindeck")
        card_tags = main_tag.find_all("li", class_="list__item")
        for card_tag in card_tags:
            self._maindeck += self._to_playset(card_tag)

        side_tag = self._soup.find("div", class_="sideboard")
        if side_tag:
            card_tags = side_tag.find_all("li", class_="list__item")
            for card_tag in card_tags:
                self._sideboard += self._to_playset(card_tag)
