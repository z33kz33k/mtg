"""

    mtg.deck.scrapers.fireball.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape ChannelFireball decklists.

    ChannelFireball is a TCG Player subsidiary since 2022. As such, its webpages use TCG Player's
    backend.

    @author: z33k

"""
import logging
from typing import override

from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper, DecksJsonContainerScraper, \
    HybridContainerScraper
from mtg.deck.scrapers.tcgplayer import (
    TcgPlayerInfiniteArticleScraper, TcgPlayerInfiniteDeckScraper,
    TcgPlayerInfinitePlayerScraper, TcgPlayerInfiniteAuthorScraper)

_log = logging.getLogger(__name__)
FIREBALL_URL_PREFIX = "https://www.channelfireball.com"


# NOTE: As of Feb 25th, TCGPlayer seems to have recently withdrawn special ChannelFireball-specific
# API domain: 'cfg-infinite-api.tcgplayer.com' that the scrapers below used to utilize. Now there's
# a simple redirection from ChannelFireball URL directly to TCGPlayer Infinite article and the
# regular TCGPlayer Infinite API domain is used.


@DeckScraper.registered
class ChannelFireballDeckScraper(TcgPlayerInfiniteDeckScraper):
    """Scraper of ChannelFireball decklist page.
    """
    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "channelfireball.com/magic-the-gathering/deck/" in url.lower()


@DeckUrlsContainerScraper.registered
class ChannelFireballPlayerScraper(TcgPlayerInfinitePlayerScraper):
    """Scraper of ChannelFireball player page.
    """
    CONTAINER_NAME = "ChannelFireball player"  # override
    DECK_SCRAPERS = ChannelFireballDeckScraper,  # override
    DECK_URL_PREFIX = FIREBALL_URL_PREFIX  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "channelfireball.com/magic-the-gathering/decks/player/" in url.lower()


@DecksJsonContainerScraper.registered
class ChannelFireballArticleScraper(TcgPlayerInfiniteArticleScraper):
    """Scraper of ChannelFireball article page.
    """
    CONTAINER_NAME = "ChannelFireball article"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return f"channelfireball.com/article/" in url.lower()


@HybridContainerScraper.registered
class ChannelFireballAuthorScraper(TcgPlayerInfiniteAuthorScraper):
    """Scraper of ChannelFireball author page.
    """
    CONTAINER_NAME = "ChannelFireball author"  # override
    CONTAINER_SCRAPERS = ChannelFireballArticleScraper,  # override
    CONTAINER_URL_PREFIX = FIREBALL_URL_PREFIX  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "channelfireball.com/author/" in url.lower() and not url.lower().endswith("/decks")
