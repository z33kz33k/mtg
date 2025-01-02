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

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper, TagBasedDeckParser
from mtg.utils import from_iterable, sanitize_whitespace
from mtg.utils.scrape import ScrapingError
from mtg.utils.scrape.dynamic import get_dynamic_soup

_log = logging.getLogger(__name__)


class MagicGgNewDeckTagParser(TagBasedDeckParser):
    """Parser of Magic.gg (new-type) decklist HTML tag.
    """
    def _parse_metadata(self) -> None:  # override
        attrs = self._deck_tag.attrs
        self._metadata["author"] = attrs["deck-title"]
        self._metadata["name"] = f"{attrs['subtitle']} ({attrs['deck-title']})"
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
            lines += ["Commander", "", *commander.text.splitlines()]
        if companion := self._deck_tag.find("companion-card"):
            if lines:
                lines.append("")
            lines += ["Companion", "", *companion.text.splitlines()]
        if lines:
            lines.append("")
        lines += self._deck_tag.find("main-deck").text.splitlines()
        lines += ["", "Sideboard"]
        if sideboard := self._deck_tag.find("side-board"):
            lines += sideboard.text.splitlines()
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
        self._metadata["name"] = f"{subtitle} ({author})"

        tags = [*self._deck_tag.select("div.css-1AJSc > span.css-3F_4f")]
        event_tag = None
        if len(tags) == 3:
            fmt_tag, date_tag, _ = tags
        elif len(tags) == 4:
            event_tag, fmt_tag, date_tag, _ = tags
        else:
            return
        self._update_fmt(fmt_tag.text.strip())
        self._metadata["date"] = dateutil.parser.parse(date_tag.text.strip()).date()
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
    _XPATH = '//div[@class="css-3X0PN"]'

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
        self._soup, _, _ = get_dynamic_soup(self.url, self._XPATH)
        if not self._soup:
            raise ScrapingError("Page not available")
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
#
#
# @DecksJsonContainerScraper.registered
# class MtgoEventScraper(DecksJsonContainerScraper):
#     """Scraper of MTGO event page.
#     """
#     CONTAINER_NAME = "MTGO event"
#     _DECK_PARSER = MtgoDeckJsonParser
#
#     @staticmethod
#     def is_container_url(url: str) -> bool:  # override
#         return f"mtgo.com/decklist/" in url.lower() and "#deck_" not in url.lower()
#
#     @staticmethod
#     def sanitize_url(url: str) -> str:  # override
#         return strip_url_params(url)
#
#     def _collect(self) -> list[Json]:  # override
#         self._soup = getsoup(self.url, headers=HEADERS)
#         if not self._soup:
#             _log.warning(self._error_msg)
#             return []
#         try:
#             json_data = _get_json(self._soup)
#         except ScrapingError:
#             _log.warning(self._error_msg)
#             return []
#
#         decks_data = _get_decks_data(json_data)
#         if rank_data := json_data.get("final_rank"):
#             _process_ranks(rank_data, *decks_data)
#         self._metadata.update(_get_event_metadata(json_data))
#         return decks_data
