"""

    mtg.deck.scrapers.manastack.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape ManaStack decklists.

    @author: z33k

"""
import logging

from selenium.common.exceptions import TimeoutException

from mtg.deck import ParsingState
from mtg.deck.scrapers import DeckScraper
from mtg.utils import get_date_from_ago_text
from mtg.utils.scrape import ScrapingError
from mtg.utils.scrape import get_dynamic_soup_by_xpath

_log = logging.getLogger(__name__)


@DeckScraper.registered
class ManaStackScraper(DeckScraper):
    """Scraper of ManaStack decklist page.
    """
    _XPATH = "//div[@class='deck-list-container']"

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "manastack.com/deck/" in url.lower()

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, _ = get_dynamic_soup_by_xpath(self.url, self._XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._soup.find("h3", class_="deck-name").text.strip()
        self._update_fmt(self._soup.find("div", class_="format-listing").text.strip().lower())
        if desc_tag := self._soup.select_one("div.deck-description.text"):
            self._metadata["description"] = desc_tag.text.strip()
        author_tag =  self._soup.find("div", class_="deck-meta-user")
        self._metadata["author"] = author_tag.find("a").text.strip()
        *_, date_text = author_tag.text.strip().split("Last updated")
        self._metadata["date"] = get_date_from_ago_text(date_text.strip())

    def _parse_deck(self) -> None:  # override
        deck_tag = self._soup.find("div", class_="deck-list-container")
        for tag in deck_tag.descendants:
            if tag.name == "h4":
                if "Sideboard" in tag.text:
                    self._shift_to_sideboard()
                elif "Commander" in tag.text:
                    self._shift_to_commander()
                elif "Companion" in tag.text:
                    self._shift_to_companion()
                elif self._state is not ParsingState.MAINDECK:
                    self._shift_to_maindeck()
            elif tag.name == "div":
                class_ = tag.attrs.get("class")
                if "deck-list-item" in class_:
                    name = tag.find("a").text.strip()
                    quantity = int(tag.text.strip().removesuffix(name).strip())
                    cards = self.get_playset(self.find_card(name), quantity)
                    if self._state is ParsingState.MAINDECK:
                        self._maindeck += cards
                    elif self._state is ParsingState.SIDEBOARD:
                        self._sideboard += cards
                    elif self._state is ParsingState.COMMANDER:
                        self._set_commander(cards[0])
                    elif self._state is ParsingState.COMPANION:
                        self._companion = cards[0]
