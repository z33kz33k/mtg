"""

    mtgcards.deck.scrapers.starcitygames.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape StarCityGames decklists.

    @author: z33k

"""
import logging

from mtgcards.deck import ParsingState
from mtgcards.const import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import getsoup
from utils import from_iterable, sanitize_whitespace

_log = logging.getLogger(__name__)


class StarCityGamesScraper(DeckScraper):
    """Scraper of StarCityGames decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(self.url)
        self._scrape_metadata()
        self._scrape_deck()

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "old.starcitygames.com/decks/" in url

    def _scrape_metadata(self) -> None:  # override
        self._metadata["name"] = self._soup.find("header", class_="deck_title").text.strip()
        self._metadata["author"] = self._soup.find("header", class_="player_name").text.strip()
        if event_tag := self._soup.find("header", class_="deck_played_placed"):
            self._metadata["event"] = sanitize_whitespace(event_tag.text.strip())
        self._update_fmt(self._soup.find("div", class_="deck_format").text.strip().lower())

    def _scrape_deck(self) -> None:  # override
        deck_tag = self._soup.find("div", class_="deck_card_wrapper")
        for tag in deck_tag.descendants:
            if tag.name == "h3":
                if "Sideboard" in tag.text:
                    self._shift_to_sideboard()
                elif "Commander" in tag.text:
                    self._shift_to_commander()
                elif "Companion" in tag.text:
                    self._shift_to_companion()
                elif self._state is not ParsingState.MAINBOARD:
                    self._shift_to_mainboard()
            elif tag.name == "li":
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

        if self.fmt == "commander":
            deck_name = self._metadata["name"]
            if commander := from_iterable(self._mainboard, lambda c: c.name == deck_name):
                self._set_commander(commander)

        self._build_deck()
