"""

    mtg.deck.scrapers.scryfall.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Scryfall decklists.

    @author: z33k

"""
import logging
from datetime import date

from bs4 import Tag

from mtg.deck.scrapers import UrlDeckScraper
from mtg.scryfall import Card
from mtg.utils import extract_int, sanitize_whitespace
from mtg.utils.scrape import ScrapingError, getsoup, strip_url_params

_log = logging.getLogger(__name__)


@UrlDeckScraper.registered
class ScryfallScraper(UrlDeckScraper):
    """Scraper of Scryfall decklist page.
    """
    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "scryfall.com/@" in url.lower() and "/decks/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url)
        return f"{url}?as=list&with=usd"

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
        *_, author_part = self.url.split("@")
        author, *_ = author_part.split("/")
        self._metadata["author"] = author
        if name_tag := self._soup.find("h1", class_="deck-details-title"):
            self._metadata["name"] = sanitize_whitespace(name_tag.text.strip())
        info_tag = self._soup.find("p", class_="deck-details-subtitle")
        if fmt_tag := info_tag.find("strong"):
            self._update_fmt(sanitize_whitespace(fmt_tag.text.strip()))
        date_text = info_tag.find("abbr").attrs["title"]
        date_text, _ = date_text.split(" ", maxsplit=1)
        self._metadata["date"] = date.fromisoformat(date_text)
        if desc_tag := self._soup.find("div", class_="deck-details-description"):
            self._metadata["description"] = sanitize_whitespace(desc_tag.text.strip())

    @classmethod
    def _parse_section(cls, section_tag: Tag) -> list[Card]:
        cards = []
        for li_tag in section_tag.find_all("li"):
            quantity = extract_int(li_tag.find("span", class_="deck-list-entry-count").text)
            name_tag = li_tag.find("span", class_="deck-list-entry-name")
            name = name_tag.text.strip()
            if name.endswith("✶"):
                name = name.removesuffix("✶").strip()
            link = name_tag.find("a").attrs["href"]
            text = link.removeprefix("https://scryfall.com/card/")
            set_code, collector_number, *_ = text.split("/")
            card = cls.find_card(name, (set_code, collector_number))
            cards += cls.get_playset(card, quantity)
        return cards

    def _parse_decklist(self) -> None:  # override
        for section_tag in self._soup.find_all("div", class_="deck-list-section"):
            title = section_tag.find("h6").text
            cards = self._parse_section(section_tag)

            if "Commander" in title:
                for card in cards:
                    self._set_commander(card)
            elif "Sideboard" in title:
                self._sideboard = cards
            else:
                self._maindeck += cards
