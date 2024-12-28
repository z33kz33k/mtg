"""

    mtg.deck.scrapers.starcitygames.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape StarCityGames decklists.

    @author: z33k

"""
import logging

import dateutil.parser

from mtg.deck import ParsingState
from mtg.deck.scrapers import ContainerScraper, DeckScraper
from mtg.utils import extract_int, from_iterable, sanitize_whitespace
from mtg.utils.scrape import ScrapingError, getsoup, strip_url_params

_log = logging.getLogger(__name__)


@DeckScraper.registered
class StarCityGamesScraper(DeckScraper):
    """Scraper of StarCityGames decklist page.
    """
    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        if "old.starcitygames.com/decks/" not in url.lower():
            return False
        url = url.removesuffix("/")
        _, end = url.split("/decks/", maxsplit=1)
        if all(ch.isdigit() for ch in end):
            return True
        return False

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url, with_endpoint=False)

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
        self._metadata["name"] = self._soup.find("header", class_="deck_title").text.strip()
        self._metadata["author"] = self._soup.find("header", class_="player_name").text.strip()
        if event_tag := self._soup.find("header", class_="deck_played_placed"):
            event = sanitize_whitespace(event_tag.text.strip())
            if " at " in event and " on " in event:
                self._metadata["event"] = {}
                place, rest = event.split(" at ", maxsplit=1)
                self._metadata["event"]["place"] = extract_int(place)
                event_name, date = rest.split(" on ", maxsplit=1)
                self._metadata["event"]["name"] = event_name
                self._metadata["event"]["date"] = dateutil.parser.parse(date.strip()).date()
            else:
                self._metadata["event"] = event
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


@ContainerScraper.registered
class StarCityGamesEventScraper(ContainerScraper):
    """Scraper of StarCityGames event page.
    """
    CONTAINER_NAME = "StarCityGames event"  # override
    _DECK_SCRAPER = StarCityGamesScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        if "old.starcitygames.com/decks/" not in url.lower():
            return False
        url = url.removesuffix("/")
        _, end = url.split("/decks/", maxsplit=1)
        if "/" in end:
            return True
        return False

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url, with_endpoint=False)

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _, name = self.CONTAINER_NAME.split()
            _log.warning(f"{name.title()} data not available")
            return []

        section_tag = self._soup.select_one("section#content")
        deck_tags = [
            a_tag for a_tag in section_tag.find_all(
                "a", href=lambda h: h and StarCityGamesScraper.is_deck_url(h))]
        return [tag.attrs["href"] for tag in deck_tags if tag is not None]
