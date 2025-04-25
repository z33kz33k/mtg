"""

    mtg.deck.scrapers.mtgdecksnet.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGDecks.net decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser
from bs4 import Tag

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper, HybridContainerScraper, \
    TagBasedDeckParser
from mtg.utils.scrape import ScrapingError, get_previous_sibling_tag
from mtg.utils.scrape import strip_url_query

_log = logging.getLogger(__name__)
URL_PREFIX = "https://mtgdecks.net"


class MtgDecksNetDeckTagParser(TagBasedDeckParser):
    """Parser of MTGDecks.net decklist HTML tag.
    """
    def _find_title_tag(self) -> Tag | None:
        tries, tag = 3, self._deck_tag
        while tries:
            previous = get_previous_sibling_tag(tag)
            if not previous:
                return None
            if previous.name.startswith("h"):
                return previous
            tries -= 1
            tag = previous
        return None

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
        # format
        if title_tag := self._find_title_tag():
            if fmt := self.derive_format_from_text(title_tag.text):
                self._update_fmt(fmt)
        if not self.fmt:
            if fmt := self.derive_format_from_text(self._metadata["name"] + self._metadata["event"]):
                self._update_fmt(fmt)

    @override
    def _parse_decklist(self) -> None:
        pass

    @override
    def _build_deck(self) -> Deck:
        decklist_tag = self._deck_tag.find("textarea", id="arena_deck")
        if not decklist_tag:
            raise ScrapingError("Decklist tag not found", scraper=type(self), url=self.url)
        decklist = decklist_tag.text.strip()
        return ArenaParser(decklist, self._metadata).parse(
            suppress_parsing_errors=False, suppress_invalid_deck=False)


# TODO: scrape the meta
@DeckScraper.registered
class MtgDecksNetDeckScraper(DeckScraper):
    """Scraper of MTGDecks.net decklist page.
    """
    SELENIUM_PARAMS = {  # override
        "xpath": "//textarea[@id='arena_deck']"
    }
    _FORMATS = {
        "brawl": "standardbrawl",
        "historic-brawl": "brawl",
    }

    @property
    @override
    def _error_msg(self) -> str:
        return super()._error_msg + " (deck probably hidden)"

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "mtgdecks.net/" in url.lower() and "-decklist-" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(url)
        return url.removesuffix("/visual")

    def _get_deck_parser(self) -> MtgDecksNetDeckTagParser:
        deck_tag = self._soup.select_one("div.deck.shadow")
        if deck_tag is None:
            raise ScrapingError("Deck tag not found", scraper=type(self), url=self.url)
        return MtgDecksNetDeckTagParser(deck_tag, self._metadata)

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
    SELENIUM_PARAMS = {  # override
        "xpath": '//a[contains(@href, "-decklist-")]'
    }
    CONTAINER_NAME = "MTGDecks.net tournament"  # override
    DECK_SCRAPERS = MtgDecksNetDeckScraper,  # override
    DECK_URL_PREFIX = URL_PREFIX  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "mtgdecks.net/" in url.lower() and "-tournament-" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return url.removesuffix("/").removesuffix("/winrates")

    @override
    def _collect(self) -> list[str]:
        deck_tags = [
            tag for tag in self._soup.find_all("a", href=lambda h: h and "-decklist-" in h)]
        if not deck_tags:
            raise ScrapingError("Deck tags not found", scraper=type(self), url=self.url)
        return [deck_tag.attrs["href"] for deck_tag in deck_tags]


@HybridContainerScraper.registered
class MtgDecksNetArticleScraper(HybridContainerScraper):
    """Scraper of MTGDecks.net article page.
    """
    SELENIUM_PARAMS = {  # override
        "xpath": "//div[@class='framed']",
        "wait_for_all": True
    }
    CONTAINER_NAME = "MTGDecks.net article"  # override
    TAG_BASED_DECK_PARSER = MtgDecksNetDeckTagParser  # override
    CONTAINER_SCRAPERS = MtgDecksNetTournamentScraper,  # override
    CONTAINER_URL_PREFIX = URL_PREFIX  # override

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._article_tag: Tag | None = None

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        tokens = ("/guides/", "/meta/", "/spoilers/", "/theory/", "/news/", "/profiles/")
        tokens = {f"mtgdecks.net{t}" for t in tokens}
        return any(t in url.lower() for t in tokens)

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    def _parse_article_metadata(self) -> None:
        if title_tag := self._article_tag.find("h1"):
            if fmt := self.derive_format_from_text(title_tag.text):
                self._update_fmt(fmt)
                return
        tags = [
            *self._article_tag.find_all("p"), *self._article_tag.find_all("h2"),
            *self._article_tag.find_all("h3"), *self._article_tag.find_all("h4")]
        text = "".join(tag.text for tag in tags)
        if fmt := self.derive_format_from_text(text):
            self._update_fmt(fmt)

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        deck_tags = [
            t for t in self._soup.select("div.framed") if t.select_one("textarea#arena_deck")]
        self._article_tag = self._soup.select_one("div#articleBody")
        if not self._article_tag:
            _log.warning("Article tag not found")
            return [], deck_tags, [], []
        self._parse_article_metadata()
        deck_urls, container_urls = self._get_links_from_tags(*self._article_tag.find_all("p"))
        return deck_urls, deck_tags, [], container_urls
