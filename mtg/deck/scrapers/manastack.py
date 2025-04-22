"""

    mtg.deck.scrapers.manastack.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape ManaStack decklists.

    @author: z33k

"""
import logging
from typing import override

from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.utils import get_date_from_ago_text
from mtg.utils.scrape import strip_url_query

_log = logging.getLogger(__name__)


@DeckScraper.registered
class ManaStackDeckScraper(DeckScraper):
    """Scraper of ManaStack decklist page.
    """
    SELENIUM_PARAMS = {  # override
        "xpath": "//div[@class='deck-list-container']"
    }

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "manastack.com/deck/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _parse_metadata(self) -> None:
        self._metadata["name"] = self._soup.find("h3", class_="deck-name").text.strip()
        self._update_fmt(self._soup.find("div", class_="format-listing").text.strip().lower())
        if desc_tag := self._soup.select_one("div.deck-description.text"):
            self._metadata["description"] = desc_tag.text.strip()
        author_tag =  self._soup.find("div", class_="deck-meta-user")
        self._metadata["author"] = author_tag.find("a").text.strip()
        *_, date_text = author_tag.text.strip().split("Last updated")
        self._metadata["date"] = get_date_from_ago_text(date_text.strip())

    @override
    def _parse_decklist(self) -> None:
        deck_tag = self._soup.find("div", class_="deck-list-container")
        for tag in deck_tag.descendants:
            if tag.name == "h4":
                if "Sideboard" in tag.text:
                    self._state.shift_to_sideboard()
                elif "Commander" in tag.text:
                    self._state.shift_to_commander()
                elif "Companion" in tag.text:
                    self._state.shift_to_companion()
                elif not self._state.is_maindeck:
                    self._state.shift_to_maindeck()
            elif tag.name == "div":
                class_ = tag.attrs.get("class")
                if "deck-list-item" in class_:
                    name = tag.find("a").text.strip()
                    quantity = int(tag.text.strip().removesuffix(name).strip())
                    cards = self.get_playset(self.find_card(name), quantity)
                    if self._state.is_maindeck:
                        self._maindeck += cards
                    elif self._state.is_sideboard:
                        self._sideboard += cards
                    elif self._state.is_commander:
                        self._set_commander(cards[0])
                    elif self._state.is_companion:
                        self._companion = cards[0]


@DeckUrlsContainerScraper.registered
class ManaStackUserScraper(DeckUrlsContainerScraper):
    """Scraper of ManaStack user page.
    """
    SELENIUM_PARAMS = {  # override
        "xpath": '//div[@class="deck-listing-container"]'
    }
    CONTAINER_NAME = "ManaStack user"  # override
    DECK_SCRAPERS = ManaStackDeckScraper,  # override
    DECK_URL_PREFIX = "https://manastack.com"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "manastack.com/user/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _collect(self) -> list[str]:
        rows = self._soup.find_all("div", class_="deck-listing-container")
        deck_tags = [
            tag for tag in
            [row.find("a", href=lambda h: h and h.lower().startswith("/deck/")) for row in rows]
            if tag is not None]
        return [deck_tag["href"] for deck_tag in deck_tags]
