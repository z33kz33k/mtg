"""

    mtgcards.deck.scrapers.hareruya.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Hareruya decklists.

    @author: z33k

"""
import logging

from bs4 import NavigableString
import dateutil.parser

from mtgcards.deck import ParsingState
from mtgcards import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.deck.scrapers.goldfish import GoldfishScraper
from mtgcards.utils.scrape import ScrapingError, getsoup

_log = logging.getLogger(__name__)


class HareruyaScraper(DeckScraper):
    """Scraper of Hareruya decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "hareruyamtg.com" in url and "/deck/" in url

    def _pre_process(self) -> None:  # override
        self._soup = getsoup(self.url, headers=GoldfishScraper.HEADERS)
        if not self._soup:
            raise ScrapingError("Page not available")

    def _process_metadata(self) -> None:  # override
        info_tag = self._soup.find("div", class_="deckSearch-deckList__information__flex")
        for ul_tag in info_tag.find_all("ul"):
            li_tags = ul_tag.find_all("li")
            if len(li_tags) != 2:
                continue
            cat_tag, value_tag = li_tags
            if cat_tag.text.strip() == "Deck Name":
                self._metadata["name"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Tournament":
                self._metadata["event"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Format":
                self._update_fmt(value_tag.text.strip())
            elif cat_tag.text.strip() == "Archetype":
                self._metadata["hareruya_archetype"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Player":
                self._metadata["author"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Score":
                self._metadata["event_score"] = value_tag.text.strip()
            elif cat_tag.text.strip() == "Date":
                self._metadata["date"] = dateutil.parser.parse(value_tag.text.strip()).date()

        if not self._metadata.get("name") and self._metadata.get("hareruya_archetype"):
            self._metadata["name"] = self._metadata["hareruya_archetype"]

    def _process_deck(self) -> None:  # override
        main_tag = self._soup.find("div", class_="deckSearch-deckList__deckList__wrapper")

        for sub_tag in main_tag.descendants:
            if isinstance(sub_tag, NavigableString):
                continue

            if class_ := sub_tag.attrs.get("class"):
                if "deckSearch-deckList__deckList__totalNumber" in class_:
                    if "Sideboard" in sub_tag.text:
                        self._shift_to_sideboard()
                    elif "Commander" in sub_tag.text:
                        self._shift_to_commander()
                    elif self._state is not ParsingState.MAINDECK:
                        self._shift_to_maindeck()
            else:
                name_tag = sub_tag.find("a", class_="popup_product")
                if not name_tag:
                    continue
                name = name_tag.text.strip().strip("《》")
                qty_tag = sub_tag.find("span")
                if not qty_tag:
                    continue
                quantity = int(qty_tag.text)
                cards = self.get_playset(self.find_card(name), quantity)
                if self._state is ParsingState.MAINDECK:
                    self._maindeck += cards
                elif self._state is ParsingState.SIDEBOARD:
                    self._sideboard += cards
                elif self._state is ParsingState.COMMANDER:
                    self._set_commander(cards[0])
