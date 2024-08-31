"""

    mtgcards.deck.scrapers.manastack.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape ManaStack decklists.

    @author: z33k

"""
import logging

from selenium.common.exceptions import TimeoutException

from mtgcards import Json
from mtgcards.deck import ParsingState
from mtgcards.deck.scrapers import DeckScraper
from utils import get_ago_date
from utils.scrape import get_dynamic_soup_by_xpath

_log = logging.getLogger(__name__)


class ManaStackScraper(DeckScraper):
    """Scraper of ManaStack decklist page.
    """
    _XPATH = "//div[@class='deck-list-container']"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        try:
            self._soup, _, _ = get_dynamic_soup_by_xpath(self.url, self._XPATH)
            self._scrape_metadata()
            self._scrape_deck()
        except TimeoutException:
            _log.warning(f"Scraping failed due to Selenium timing out")

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "manastack.com/deck/" in url

    def _scrape_metadata(self) -> None:  # override
        self._metadata["name"] = self._soup.find("h3", class_="deck-name").text.strip()
        self._update_fmt(self._soup.find("div", class_="format-listing").text.strip().lower())
        if desc_tag := self._soup.select_one("div.deck-description.text"):
            self._metadata["description"] = desc_tag.text.strip()
        author_tag =  self._soup.find("div", class_="deck-meta-user")
        self._metadata["author"] = author_tag.find("a").text.strip()
        *_, date_text = author_tag.text.strip().split("Last updated")
        self._metadata["date"] = get_ago_date(date_text.strip())

    def _scrape_deck(self) -> None:  # override
        deck_tag = self._soup.find("div", class_="deck-list-container")
        for tag in deck_tag.descendants:
            if tag.name == "h4":
                if "Sideboard" in tag.text:
                    self._shift_to_sideboard()
                elif "Commander" in tag.text:
                    self._shift_to_commander()
                elif "Companion" in tag.text:
                    self._shift_to_companion()
                elif self._state is not ParsingState.MAINBOARD:
                    self._shift_to_mainboard()
            elif tag.name == "div":
                class_ = tag.attrs.get("class")
                if "deck-list-item" in class_:
                    name = tag.find("a").text.strip()
                    quantity = int(tag.text.strip().removesuffix(name).strip())
                    cards = self.get_playset(self.find_card(name), quantity)
                    if self._state is ParsingState.MAINBOARD:
                        self._mainboard += cards
                    elif self._state is ParsingState.SIDEBOARD:
                        self._sideboard += cards
                    elif self._state is ParsingState.COMMANDER:
                        self._set_commander(cards[0])
                    elif self._state is ParsingState.COMPANION:
                        self._companion = cards[0]

        self._build_deck()
