"""

    mtg.deck.scrapers.topdeck.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TopDeck.gg deck containers.

    @author: z33k

"""
import logging
from typing import Type, override

from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.utils import extract_int
from mtg.utils.scrape import ScrapingError, strip_url_query

_log = logging.getLogger(__name__)


@DeckScraper.registered
class TopDeckDeckScraper(DeckScraper):
    """Scraper of TopDeck.gg decklist page.
    """
    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "topdeck.gg/deck/" in url.lower()

    @override
    def _is_inaccessible(self) -> bool:
        tag = self._soup.find("h3")
        return tag and tag.text.strip() == "Unable to Display Deck"

    @override
    def _parse_metadata(self) -> None:
        header_tag = self._soup.select_one("div.row.align-items-center")
        if not header_tag:
            raise ScrapingError("Header tag not found", scraper=type(self), url=self.url)
        if author_tag := header_tag.find("h1"):
            self._metadata["author"] = author_tag.text.strip()
        if event_tag := header_tag.find("h3"):
            self._metadata.setdefault("event", {})["name"] = event_tag.text.strip()
        if event_url_tag := header_tag.find("a", href=lambda h: h and h.startswith("/bracket/")):
            self._metadata.setdefault(
                "event", {})["url"] = "https://topdeck.gg" + event_url_tag.attrs["href"]
        if fmt_tag := header_tag.find("small"):
            self._update_fmt(fmt_tag.text.strip().removeprefix("Magic: The Gathering "))
        if p_tag := header_tag.find("p"):
            rank, record = p_tag.text.strip().split("•Record: ", maxsplit=1)
            self._metadata.setdefault("event", {})["rank"] = extract_int(rank)
            self._metadata.setdefault("event", {})["record"] = record.strip()

    @override
    def _parse_decklist(self) -> None:
        decklist_tag = self._soup.find(
            "script", string=lambda s: s and "const decklistContent = `" in s)
        if not decklist_tag:
            raise ScrapingError("Decklist tag not found", scraper=type(self), url=self.url)
        _, decklist = decklist_tag.text.split("const decklistContent = `", maxsplit=1)
        decklist, _ = decklist.split("`;", maxsplit=1)
        self._decklist = decklist.replace("~~Commanders~~", "Commander").replace(
            "~~Mainboard~~", "Deck").replace("~~Sideboard~~", "Sideboard")

    @override
    def _build_deck(self) -> Deck | None:
        return ArenaParser(self._decklist, metadata=self._metadata).parse()


def check_unexpected_urls(urls: list[str], *scrapers: Type[DeckScraper]) -> None:
    names = [scraper.__name__ for scraper in scrapers]
    if unexpected := [url for url in urls if url.startswith("http") and
                      not any(s.is_valid_url(url) for s in scrapers)]:
        _log.warning(f"Non-{names} deck(s) found: {', '.join(unexpected)}")


# seen scrapers:
# ArchidektDeckScraper
# DeckboxDeckScraper
# GoldfishDeckScraper
# ManaBoxDeckScraper
# ManaStackDeckScraper
# MoxfieldDeckScraper
# ScryfallDeckScraper
# TappedoutDeckScraper


@DeckUrlsContainerScraper.registered
class TopDeckBracketScraper(DeckUrlsContainerScraper):
    """Scraper of TopDeck.gg bracket page.
    """
    SELENIUM_PARAMS = {  # override
        "xpath": "//a[text()='Decklist']",
        "wait_for_all": True
    }
    CONTAINER_NAME = "TopDeck.gg bracket"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "topdeck.gg/bracket/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _collect(self) -> list[str]:
        deck_tags = self._soup.find_all("a", string="Decklist")
        if not deck_tags:
            raise ScrapingError("Decklist tags not found", scraper=type(self), url=self.url)
        deck_urls = [t["href"] for t in deck_tags]
        check_unexpected_urls(deck_urls, *self._get_deck_scrapers())
        return deck_urls


@DeckUrlsContainerScraper.registered
class TopDeckProfileScraper(DeckUrlsContainerScraper):
    """Scraper of TopDeck.gg profile page.
    """
    SELENIUM_PARAMS = {  # override
        "xpath": ("//a[contains(@class, 'btn') and contains(@class, 'btn-sm') "
                  "and not(contains(@href, 'topdeck.gg'))]"),
        "wait_for_all": True
    }
    CONTAINER_NAME = "TopDeck.gg profile"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "topdeck.gg/profile/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _collect(self) -> list[str]:
        deck_tags = self._soup.find_all(
            "a", class_=lambda c: c and "btn" in c and "btn-sm" in c,
            href=lambda h: h and "topdeck.gg" not in h)
        if not deck_tags:
            raise ScrapingError("Decklist tags not found", scraper=type(self), url=self.url)
        deck_urls = [t["href"] for t in deck_tags]
        check_unexpected_urls(deck_urls, *self._get_deck_scrapers())
        return deck_urls
