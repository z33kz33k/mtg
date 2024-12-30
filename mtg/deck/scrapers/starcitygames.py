"""

    mtg.deck.scrapers.starcitygames.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape StarCityGames decklists.

    @author: z33k

"""
import logging

import dateutil.parser
from bs4 import Tag

from mtg import Json
from mtg.deck import ParsingState
from mtg.deck.scrapers import ContainerScraper, TagDeckScraper, UrlDeckScraper
from mtg.utils import extract_int, from_iterable, sanitize_whitespace
from mtg.utils.scrape import ScrapingError, getsoup, strip_url_params

_log = logging.getLogger(__name__)


# the divide of deck scraping logic into tag-based scraper and URL-based scraper sprung from the
# perceived need of parsing StarCityGames decklists-containing articles (e.g.:
# https://articles.starcitygames.com/magic-the-gathering/the-coolest-rogue-decks-for-standard-at-magic-spotlight-foundations/
# with a tag-based scraper (that, incidentally, could share the same deck-extracting logic with the
# URL-based one). This turned out to be unnecessary as the decklist HTML tags in StarCityGames
# articles contain also decklist URLs so the old approach of parsing deck URLs for decks
# could be utilized.


class StarCityGamesTagDeckScraper(TagDeckScraper):
    @staticmethod
    def _parse_event_line(line: str) -> Json | str:
        if " at " in line and " on " in line:
            data = {}
            place, rest = line.split(" at ", maxsplit=1)
            data["place"] = extract_int(place)
            event_name, date = rest.split(" on ", maxsplit=1)
            data["name"] = event_name
            data["date"] = dateutil.parser.parse(date.strip()).date()
            return data
        return line

    def _parse_header_tag(self, header_tag: Tag) -> None:
        self._metadata["name"] = header_tag.find("header", class_="deck_title").text.strip()
        self._metadata["author"] = header_tag.find("header", class_="player_name").text.strip()
        if event_tag := header_tag.find("header", class_="deck_played_placed"):
            event = sanitize_whitespace(event_tag.text.strip())
            self._metadata["event"] = self._parse_event_line(event)
        self._update_fmt(header_tag.find("div", class_="deck_format").text.strip().lower())

    def _parse_metadata(self) -> None:  # override
        self._parse_header_tag(self._deck_tag.find("div", class_="deck_header"))

    def _parse_decklist_tag(self, decklist_tag: Tag) -> None:
        for tag in decklist_tag.descendants:
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

    def _parse_deck(self) -> None:  # override
        decklist_tag = self._deck_tag.find("div", class_="deck_card_wrapper")
        self._parse_decklist_tag(decklist_tag)


@UrlDeckScraper.registered
class StarCityGamesUrlScraper(UrlDeckScraper, StarCityGamesTagDeckScraper):
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
        self._parse_header_tag(self._soup.find("div", class_="deck_header"))

    def _parse_deck(self) -> None:  # override
        decklist_tag = self._soup.find("div", class_="deck_card_wrapper")
        self._parse_decklist_tag(decklist_tag)


@ContainerScraper.registered
class StarCityGamesEventScraper(ContainerScraper):
    """Scraper of StarCityGames event page.
    """
    CONTAINER_NAME = "StarCityGames event"  # override
    _DECK_SCRAPER = StarCityGamesUrlScraper  # override

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
                "a", href=lambda h: h and StarCityGamesUrlScraper.is_deck_url(h))]
        return [tag.attrs["href"] for tag in deck_tags if tag is not None]


@ContainerScraper.registered
class StarCityGamesArticleScraper(ContainerScraper):
    """Scraper of StarCityGames decks article page.
    """
    CONTAINER_NAME = "StarCityGames article"  # override
    _DECK_SCRAPER = StarCityGamesUrlScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "articles.starcitygames.com/magic-the-gathering/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url)

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _, name = self.CONTAINER_NAME.split()
            _log.warning(f"{name.title()} data not available")
            return []

        deck_divs = [div for div in self._soup.find_all("div", class_="deck_listing")]
        deck_headers = [
            tag for tag in [d.find("header", class_="deck_title") for d in deck_divs]
            if tag is not None]
        a_tags = [
            tag for tag in
            [h.find("a", href=lambda h: h and StarCityGamesUrlScraper.is_deck_url(h))
             for h in deck_headers]
            if tag is not None]
        return [tag.attrs["href"] for tag in a_tags]
