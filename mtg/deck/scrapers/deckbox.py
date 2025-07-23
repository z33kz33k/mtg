"""

    mtg.deck.scrapers.deckbox
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Deckbox decklists.

    @author: z33k

"""
import logging
from typing import override

from bs4 import Tag

from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.scryfall import COMMANDER_FORMATS, Card
from mtg.utils.scrape import ScrapingError, strip_url_query

_log = logging.getLogger(__name__)
URL_PREFIX = "https://deckbox.org"


@DeckScraper.registered
class DeckboxDeckScraper(DeckScraper):
    """Scraper of Deckbox decklist page.
    """
    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "deckbox.org/sets/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _parse_metadata(self) -> None:
        page_header_tag = self._soup.find("div", class_=lambda c: c and "page_header" in c)
        self._metadata["author"] = page_header_tag.find("a").text.strip()
        self._metadata["name"] = page_header_tag.find("span").text.strip()
        info_tag = self._soup.find("div", class_="deck_info_widget")
        if not info_tag:
            raise ScrapingError(
                "Info tag missing. Probably not a decklist page", scraper=type(self), url=self.url)
        likes_tag = info_tag.find("span", id="votes_count")
        self._metadata["likes"] = int(likes_tag.text)
        comments_tag = info_tag.find("a", string=lambda s: s and "Comments" in s)
        self._metadata["comments"] = int(comments_tag.text.removesuffix(" Comments"))
        for div in info_tag.find_all("div", class_="indented_content"):
            if div.find("span", string="Format"):
                fmt = [*div.strings][-1].strip()
                self._update_fmt(fmt)

    @classmethod
    def _parse_row(cls, row_tag: Tag) -> list[Card]:
        qty_tag = row_tag.find("td", class_="card_count")
        name_tag = row_tag.find("td", class_="card_name")
        if not qty_tag or not name_tag:
            return []
        quantity = int(qty_tag.text.strip())
        name = name_tag.text.strip()
        return cls.get_playset(cls.find_card(name), quantity)

    @override
    def _parse_deck(self) -> None:
        maindeck_table = self._soup.find("table", class_=lambda c: c and "main" in c)
        if not maindeck_table:
            raise ScrapingError(
                "Maindeck table tag missing. Probably not a Constructed decklist page",
                scraper=type(self), url=self.url)

        for row in maindeck_table.find_all("tr"):
            self._maindeck += self._parse_row(row)

        commander_tag = self._soup.find("div", id="commander_info")
        if commander_tag:
            if commander_subtag := commander_tag.find("a"):
                self._set_commander(self.find_card(commander_subtag.text.strip()))

        sideboard_table = self._soup.find("table", class_=lambda c: c and "sideboard" in c)
        if sideboard_table and not self._commander:  # parse sideboard only if there is no commander
            for row in sideboard_table.find_all("tr"):
                self._sideboard += self._parse_row(row)

        if not self._commander and len(self._sideboard) == 1 and self.fmt in COMMANDER_FORMATS:
            self._set_commander(self._sideboard.pop())


@DeckUrlsContainerScraper.registered
class DeckboxUserScraper(DeckUrlsContainerScraper):
    """Scraper of Deckbox user page.
    """
    CONTAINER_NAME = "Deckbox user"  # override
    DECK_SCRAPERS = DeckboxDeckScraper,  # override
    DECK_URL_PREFIX = URL_PREFIX  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "deckbox.org/users/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _collect(self) -> list[str]:
        deck_tags = [
            tag for tag in self._soup.find_all("a", href=lambda h: h and "/sets/" in h)]
        if not deck_tags:
            raise ScrapingError("Deck tags not found", scraper=type(self), url=self.url)
        return sorted({tag.attrs["href"] for tag in deck_tags})


@DeckUrlsContainerScraper.registered
class DeckboxEventScraper(DeckUrlsContainerScraper):
    """Scraper of Deckbox community event page.
    """
    CONTAINER_NAME = "Deckbox event"  # override
    DECK_SCRAPERS = DeckboxDeckScraper,  # override
    DECK_URL_PREFIX = URL_PREFIX  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "deckbox.org/communities/" in url.lower() and "/events/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _collect(self) -> list[str]:
        table_tag = self._soup.find("table", class_="simple_table")
        deck_tags = [
            tag for tag in table_tag.find_all("a", href=lambda h: h and "/sets/" in h)]
        if not deck_tags:
            raise ScrapingError("Deck tags not found", scraper=type(self), url=self.url)
        return [tag.attrs["href"] for tag in deck_tags]
