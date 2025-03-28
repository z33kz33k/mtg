"""

    mtg.deck.scrapers.topdeck.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TopDeck.gg deck containers.

    @author: z33k

"""
import logging
from typing import Type, override

from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.utils.scrape import strip_url_query

_log = logging.getLogger(__name__)


def check_unexpected_urls(urls: list[str], *scrapers: Type[DeckScraper]) -> None:
    names = [scraper.__name__ for scraper in scrapers]
    if unexpected := [url for url in urls if url.startswith("http") and
                      not any(s.is_deck_url(url) for s in scrapers)]:
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
    CONTAINER_NAME = "TopDeck.gg bracket"  # override
    XPATH = "//table[contains(@class, 'table') and contains(@class, 'dataTable')]"  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "topdeck.gg/bracket/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _collect(self) -> list[str]:
        deck_tags = self._soup.find_all("a", string="Decklist")
        deck_urls = [t["href"] for t in deck_tags]
        check_unexpected_urls(deck_urls, *self._get_deck_scrapers())
        return deck_urls


@DeckUrlsContainerScraper.registered
class TopDeckProfileScraper(DeckUrlsContainerScraper):
    """Scraper of TopDeck.gg profile page.
    """
    CONTAINER_NAME = "TopDeck.gg profile"  # override
    XPATH = ("//a[contains(@class, 'btn') and contains(@class, 'btn-sm') "
             "and not(contains(@href, 'topdeck.gg'))]")  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
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
        deck_urls = [t["href"] for t in deck_tags]
        check_unexpected_urls(deck_urls, *self._get_deck_scrapers())
        return deck_urls
