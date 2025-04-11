"""

    mtg.deck.scrapers.mtgdecksnet.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGDecks.net decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser
from bs4 import Tag
from selenium.common.exceptions import TimeoutException

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper, HybridContainerScraper, \
    TagBasedDeckParser
from mtg.utils.scrape import ScrapingError
from mtg.utils.scrape import strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup

_log = logging.getLogger(__name__)


class MtgDecksNetDeckTagParser(TagBasedDeckParser):
    """Parser of MtgDecks.net decklist HTML tag.
    """
    @override
    def _parse_metadata(self) -> None:
        info_tag = self._deck_tag.find("div", class_=lambda c: c and "deckHeader" in c)
        info = info_tag.text.strip()
        name_author_part, *event_parts, date_part = info.split("—")
        name, author = name_author_part.split("Builder:")
        self._metadata["name"] = name.strip().removesuffix(".")
        self._metadata["author"] = author.strip()
        self._metadata["event"] = "—".join(event_parts).strip().replace("\n", " ")
        if date_part and "\n" in date_part:
            date_part, *_ = date_part.split("\n")
            self._metadata["date"] = dateutil.parser.parse(date_part.strip()).date()

    @override
    def _parse_decklist(self) -> None:
        pass

    @override
    def _build_deck(self) -> Deck:  # override
        decklist_tag = self._deck_tag.find("textarea", id="arena_deck")
        if not decklist_tag:
            raise ScrapingError("Decklist tag not found")
        decklist = decklist_tag.text.strip()
        return ArenaParser(decklist, self._metadata).parse(
            suppress_parsing_errors=False, suppress_invalid_deck=False)


# TODO: scrape the meta
@DeckScraper.registered
class MtgDecksNetDeckScraper(DeckScraper):
    """Scraper of MTGDecks.net decklist page.
    """
    XPATH = "//textarea[@id='arena_deck']"
    _FORMATS = {
        "brawl": "standardbrawl",
        "historic-brawl": "brawl",
    }

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_parser: MtgDecksNetDeckTagParser | None = None

    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "mtgdecks.net/" in url.lower() and "-decklist-" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(url)
        return url.removesuffix("/visual")

    @override
    def _pre_parse(self) -> None:
        try:
            self._soup, _, _ = get_dynamic_soup(self.url, self.XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")
        deck_tag = self._soup.select_one("div.deck.shadow")
        if deck_tag is None:
            raise ScrapingError("Deck data not found")

        self._deck_parser = MtgDecksNetDeckTagParser(deck_tag, self._metadata)

    @override
    def _parse_metadata(self) -> None:
        fmt_tag = self._soup.select_one("div.breadcrumbs.pull-left")
        _, a_tag, *_ = fmt_tag.find_all("a")
        fmt = a_tag.text.strip().removeprefix("MTG ").lower()
        if found := self._FORMATS.get("fmt"):
            fmt = found
        self._update_fmt(fmt)

        self._deck_parser.update_metadata(**self._metadata)

    @override
    def _parse_decklist(self) -> None:
        pass

    @override
    def _build_deck(self) -> Deck:
        return self._deck_parser.parse()


@DeckUrlsContainerScraper.registered
class MtgDecksNetTournamentScraper(DeckUrlsContainerScraper):
    """Scraper of MTGDecks.net tournament page.
    """
    CONTAINER_NAME = "MTGDecks.net tournament"  # override
    XPATH = '//a[contains(@href, "-decklist-")]'  # override
    DECK_SCRAPERS = MtgDecksNetDeckScraper,  # override
    DECK_URL_PREFIX = "https://mtgdecks.net"  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "mtgdecks.net/" in url.lower() and "-tournament-" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return url.removesuffix("/").removesuffix("/winrates")

    @override
    def _collect(self) -> list[str]:
        deck_tags = [
            tag for tag in self._soup.find_all("a", href=lambda h: h and "-decklist-" in h)]
        return [deck_tag.attrs["href"] for deck_tag in deck_tags]


@HybridContainerScraper.registered
class MtgDecksNetArticleScraper(HybridContainerScraper):
    """Scraper of MtgDecksNet article page.
    """
    CONTAINER_NAME = "MtgDecksNet article"  # override
    TAG_BASED_DECK_PARSER = MtgDecksNetDeckTagParser  # override
    XPATH = "//div[@class='framed']"
    WAIT_FOR_ALL = True

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        tokens = ("/guides/", "/meta/", "/spoilers/", "/theory/", "/news/", "/profiles/")
        tokens = {f"mtgdecks.net{t}" for t in tokens}
        return any(t in url.lower() for t in tokens)

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _parse_metadata(self) -> None:
        # TODO: derive format from article body (place this code in the parent class)
        # TODO: derive format if possible from info tag in deck tag parser
        pass

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        deck_tags = [
            t for t in self._soup.select("div.framed") if t.select_one("textarea#arena_deck")]
        self._parse_metadata()
        article_tag = self._soup.select_one("div#articleBody")
        if not article_tag:
            _log.warning("Article tag not found")
            return [], deck_tags, [], []
        deck_urls, _ = self._get_links_from_tags(*article_tag.find_all("p"))
        return deck_urls, deck_tags, [], []
