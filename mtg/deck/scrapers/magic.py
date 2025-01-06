"""

    mtg.deck.scrapers.magic.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Magic.gg decklists.

    Magic.gg is an official WotC eSports site focused on MTG Arena that covers also tabletop play.

    @author: z33k

"""
import logging

import dateutil.parser
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from selenium.common import TimeoutException

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper, DeckTagsContainerScraper, TagBasedDeckParser
from mtg.utils import sanitize_whitespace
from mtg.utils.scrape import ScrapingError, getsoup, strip_url_params
from mtg.utils.scrape.dynamic import get_dynamic_soup

_log = logging.getLogger(__name__)


def _get_deck_name(author: str, subtitle: str) -> str:
    if subtitle and author:
        return f"{subtitle} ({author})"
    if author:
        return author
    return subtitle


class MagicGgNewDeckTagParser(TagBasedDeckParser):
    """Parser of Magic.gg (new-type) decklist HTML tag.
    """
    def _parse_metadata(self) -> None:  # override
        attrs = self._deck_tag.attrs
        self._metadata["author"] = attrs["deck-title"]
        if name := _get_deck_name(attrs["deck-title"], attrs["subtitle"]):
            self._metadata["name"] = name
        self._update_fmt(attrs["format"])
        self._metadata["event"] = {
            "name": attrs["event-name"],
            "date": dateutil.parser.parse(attrs["event-date"]).date()
        }
        self._metadata["date"] = self._metadata["event"]["date"]

    def _build_arena(self) -> list[str]:
        lines = []
        # <commander-card> tag is only derived based on seen companion treatment
        if commander := self._deck_tag.find("commander-card"):
            commander_text = commander.text.lstrip()
            if commander_text:
                lines += ["Commander", *commander_text.splitlines()]
        if companion := self._deck_tag.find("companion-card"):
            companion_text = companion.text.lstrip()
            if companion_text:
                if lines:
                    lines.append("")
                lines += ["Companion", *companion_text.splitlines()]
        if lines:
            lines.append("")
        lines += ["Deck", *self._deck_tag.find("main-deck").text.lstrip().splitlines()]
        lines += ["", "Sideboard"]
        if sideboard := self._deck_tag.find("side-board"):
            lines += sideboard.text.lstrip().splitlines()
        return lines

    def _parse_decklist(self) -> None:  # override
        pass

    def _build_deck(self) -> Deck:
        return ArenaParser(self._build_arena(), self._metadata).parse(suppress_invalid_deck=False)


class MagicGgOldDeckTagParser(TagBasedDeckParser):
    """Parser of Magic.gg (old-type) decklist HTML tag.
    """
    def _parse_metadata(self) -> None:  # override
        author = self._deck_tag.select_one("div.css-2vNWs > span.css-3LH7E").text.strip()
        self._metadata["author"] = author
        subtitle = self._deck_tag.find(
            "span", class_=lambda c: c and all(
                t in c for t in ("css-2vNWs", "css-ausnN", "css-1dxey"))).text.strip()
        subtitle = sanitize_whitespace(subtitle)
        if name := _get_deck_name(author, subtitle):
            self._metadata["name"] = name

        tags = [*self._deck_tag.select("div.css-1AJSc > span.css-3F_4f")]
        event_tag = None
        if len(tags) == 3:
            fmt_tag, date_tag, _ = tags
        elif len(tags) == 4:
            event_tag, fmt_tag, date_tag, _ = tags
        else:
            return
        self._update_fmt(fmt_tag.text.strip())
        date_text = date_tag.text.strip().replace("_", "/")
        self._metadata["date"] = dateutil.parser.parse(date_text).date()
        if event_tag is not None:
            self._metadata["event"] = {
                "name": event_tag.text.strip(),
            }

    def _parse_decklist(self) -> None:  # override
        first_card_name = None

        for tag in [
            t for t in self._deck_tag.find("div", class_="css-163ya").descendants
            if not isinstance(t, (NavigableString, Comment)) and t.name in ("header", "button")]:

            if tag.name == "header":
                match tag.find("span", class_="css-TNC7f").text.strip():
                    case "Sideboard":
                        self._state.shift_to_sideboard()
                    case "Commander":
                        self._state.shift_to_commander()
                    case "Companion":
                        self._state.shift_to_companion()
                    case _:
                        if not self._state.is_maindeck:
                            self._state.shift_to_maindeck()

            elif tag.name == "button":
                name = tag.attrs["title"]
                if name == first_card_name and not self._state.is_sideboard:
                    # here we go again
                    break
                if not self._maindeck:
                    first_card_name = name
                qty = int(tag.find("span", class_="css-qFTzR").text.strip())
                cards = self.get_playset(self.find_card(name), qty)
                if self._state.is_maindeck:
                    self._maindeck += cards
                elif self._state.is_sideboard:
                    self._sideboard += cards
                elif self._state.is_commander:
                    self._set_commander(cards[0])
                elif self._state.is_companion:
                    self._companion = cards[0]


def _get_event_name(soup: BeautifulSoup) -> str:
    title = soup.select_one("head > title").text.strip()
    if "Decklist" in title:
        title, _ = title.split("Decklist", maxsplit=1)
        return title.strip()
    return title


@DeckScraper.registered
class MagicGgDeckScraper(DeckScraper):
    """Scraper of Magic.gg event page that points to an individual deck.
    """
    XPATH = '//div[@class="css-3X0PN"]'
    CONSENT_XPATH = '//button[@aria-label="Reject All"]'

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._decklist_id = self._parse_decklist_id()
        self._deck_parser: MagicGgOldDeckTagParser | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return f"magic.gg/decklists/" in url.lower() and "?decklist=" in url.lower()

    def _parse_decklist_id(self) -> str:
        *_, id_ = self.url.split("?decklist=")
        return id_

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, _ = get_dynamic_soup(
                self.url, self.XPATH, consent_xpath=self.CONSENT_XPATH)
            if not self._soup:
                raise ScrapingError("Page not available")
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

        deck_tag = self._soup.find("div", id=self._decklist_id)
        if deck_tag is None:
            raise ScrapingError(f"Deck designated by {self._decklist_id!r} data not found")
        self._metadata["event"] = {"name": _get_event_name(self._soup)}
        self._deck_parser = MagicGgOldDeckTagParser(deck_tag, self._metadata)

    def _parse_metadata(self) -> None:  # override
        pass

    def _parse_decklist(self) -> None:  # override
        pass

    def _build_deck(self) -> Deck:  # override
        return self._deck_parser.parse()


@DeckTagsContainerScraper.registered
class MagicGgEventScraper(DeckTagsContainerScraper):
    """Scraper of Magic.gg event page.
    """
    CONTAINER_NAME = "Magic.gg event"
    _DECK_PARSER = MagicGgNewDeckTagParser

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return f"magic.gg/decklists/" in url.lower() and "?decklist=" not in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url, keep_fragment=False)

    def _collect(self) -> list[Tag]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning(self._error_msg)
            return []

        deck_tags = [*self._soup.find_all("deck-list")]
        if not deck_tags:
            self.__class__._DECK_PARSER = MagicGgOldDeckTagParser
            try:
                self._soup, _, _ = get_dynamic_soup(
                    self.url, MagicGgDeckScraper.XPATH,
                    consent_xpath=MagicGgDeckScraper.CONSENT_XPATH)
                deck_tags = [*self._soup.find_all("div", class_="css-3X0PN")]
                if not deck_tags:
                    _log.warning(self._error_msg)
                    return []
            except TimeoutException:
                _log.warning(self._error_msg)
                return []
            self._metadata["event"] = {"name": _get_event_name(self._soup)}
        else:
            self.__class__._DECK_PARSER = MagicGgNewDeckTagParser

        return deck_tags