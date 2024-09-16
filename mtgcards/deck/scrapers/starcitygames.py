"""

    mtgcards.deck.scrapers.starcitygames.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape StarCityGames decklists.

    @author: z33k

"""
import logging

from mtgcards.deck import ParsingState
from mtgcards import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import ScrapingError, getsoup
from mtgcards.utils import from_iterable, sanitize_whitespace

_log = logging.getLogger(__name__)


@DeckScraper.registered
class StarCityGamesScraper(DeckScraper):
    """Scraper of StarCityGames decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "old.starcitygames.com/decks/" in url

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._soup.find("header", class_="deck_title").text.strip()
        self._metadata["author"] = self._soup.find("header", class_="player_name").text.strip()
        if event_tag := self._soup.find("header", class_="deck_played_placed"):
            self._metadata["event"] = sanitize_whitespace(event_tag.text.strip())
        self._update_fmt(self._soup.find("div", class_="deck_format").text.strip().lower())

    def _parse_deck(self) -> None:  # override
        deck_tag = self._soup.find("div", class_="deck_card_wrapper")
        for tag in deck_tag.descendants:
            if tag.name == "h3":
                if "Sideboard" in tag.text:
                    self._shift_to_sideboard()
                elif "Commander" in tag.text:
                    self._shift_to_commander()
                elif "Companion" in tag.text:
                    self._shift_to_companion()
                elif self._state is not ParsingState.MAINDECK:
                    self._shift_to_maindeck()
            elif tag.name == "li":
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

        if self.fmt == "commander":
            deck_name = self._metadata["name"]
            if commander := from_iterable(self._maindeck, lambda c: c.name == deck_name):
                self._set_commander(commander)
