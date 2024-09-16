"""

    mtgcards.deck.scrapers.penny.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape PennyDreadfulMagic decklists.

    @author: z33k

"""
import logging

from bs4 import Tag

from mtgcards import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.scryfall import Card
from mtgcards.utils.scrape import ScrapingError, getsoup
from mtgcards.utils import from_iterable, get_date_from_ago_text, get_date_from_month_text

_log = logging.getLogger(__name__)


@DeckScraper.registered
class PennyDreadfulMagicScraper(DeckScraper):
    """Scraper of Scryfall decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "pennydreadfulmagic.com/decks/" in url

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
        self._update_fmt("penny")
        self._metadata["name"] = self._soup.find("h1", class_="deck-name").text.strip()
        info_tag = self._soup.find("div", class_="title")
        archetype_tag = info_tag.find("a", href=lambda h: h and "/archetypes/" in h)
        self._metadata["penny_archetype"] = archetype_tag.text.strip()
        author_tag = info_tag.find("a", href=lambda h: h and "/people/id/" in h)
        self._metadata["author"] = author_tag.text.strip()
        if date_tag := from_iterable(
            info_tag.find_all("div", class_="subtitle"), lambda t: not t.find("a")):
            date_text = date_tag.text.strip()
            if "ago" in date_text:
                self._metadata["date"] = get_date_from_ago_text(date_text)
            else:
                self._metadata["date"] = get_date_from_month_text(date_tag.text.strip())
        if event_tag := info_tag.find("a", href=lambda h: h and "/competitions/" in h):
            self._metadata["event"] = event_tag.text.strip()

    @classmethod
    def _parse_card_tag(cls, card_tag: Tag) -> list[Card]:
        text = card_tag.text.strip()
        qty_text, name = text.split(maxsplit=1)
        quantity = int(qty_text)
        return cls.get_playset(cls.find_card(name), quantity)

    def _parse_deck(self) -> None:  # override
        for section_tag in self._soup.find_all("section"):
            if section_tag.find("section"):  # skip higher-order sections
                continue
            h2_tag = section_tag.find("h2")
            if not h2_tag:  # skip irrelevant sections
                continue
            else:
                section = h2_tag.text.strip()
                card_tags = section_tag.find_all("a", class_="card")
                for card_tag in card_tags:
                    cards = self._parse_card_tag(card_tag)

                    if "Sideboard" in section:
                        self._sideboard += cards
                    else:
                        self._maindeck += cards
