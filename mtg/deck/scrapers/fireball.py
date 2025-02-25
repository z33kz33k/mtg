"""

    mtg.deck.scrapers.fireball.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape ChannelFireball decklists.

    ChannelFireball is a TCG Player subsidiary since 2022. As such, its webpages use TCG Player's
    backend.

    @author: z33k

"""
import logging

from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper, DecksJsonContainerScraper, \
    HybridContainerScraper
from mtg.deck.scrapers.tcgplayer import (
    TcgPlayerInfiniteArticleScraper, TcgPlayerInfiniteDeckScraper,
    TcgPlayerInfinitePlayerScraper, TcgPlayerInfiniteAuthorScraper)

_log = logging.getLogger(__name__)
FIREBALL_URL_TEMPLATE = "https://www.channelfireball.com{}"


# NOTE: As of Feb 25th, TCGPlayer seems to have recently withdrawn special ChannelFireball-specific
# API domain: 'cfg-infinite-api.tcgplayer.com' that the scrapers below used to utilize. Now there's
# a simple redirection from ChannelFireball URL directly to TCGPlayer Infinite article and the
# regular TCGPlayer Infinite API domain is used.


@DeckScraper.registered
class ChannelFireballDeckScraper(TcgPlayerInfiniteDeckScraper):
    """Scraper of ChannelFireball decklist page.
    """
    # override
    # API_URL_TEMPLATE = ("https://cfb-infinite-api.tcgplayer.com/deck/magic/{}"
    #                     "/?source=cfb-infinite-content&subDecks=true&cards=true&stats=true")
    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "channelfireball.com/magic-the-gathering/deck/" in url.lower()


@DeckUrlsContainerScraper.registered
class ChannelFireballPlayerScraper(TcgPlayerInfinitePlayerScraper):
    """Scraper of ChannelFireball player page.
    """
    CONTAINER_NAME = "ChannelFireball player"  # override
    # override
    # 100 rows is pretty arbitrary but tested to work
    # API_URL_TEMPLATE = ("https://cfb-infinite-api.tcgplayer.com/content/decks/magic?source="
    #                     "cfb-infinite-content&rows=100&format=&playerName={}&latest=true"
    #                     "&sort=created&order=desc")
    DECK_SCRAPERS = ChannelFireballDeckScraper,  # override
    DECK_URL_TEMPLATE = FIREBALL_URL_TEMPLATE  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "channelfireball.com/magic-the-gathering/decks/player/" in url.lower()


@DecksJsonContainerScraper.registered
class ChannelFireballArticleScraper(TcgPlayerInfiniteArticleScraper):
    """Scraper of ChannelFireball article page.
    """
    CONTAINER_NAME = "ChannelFireball article"  # override
    # API_URL_TEMPLATE = ChannelFireballDeckScraper.API_URL_TEMPLATE

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return f"channelfireball.com/article/" in url.lower()


@HybridContainerScraper.registered
class ChannelFireballAuthorScraper(TcgPlayerInfiniteAuthorScraper):
    """Scraper of ChannelFireball author page.
    """
    CONTAINER_NAME = "ChannelFireball author"  # override
    CONTAINER_SCRAPERS = ChannelFireballArticleScraper,  # override
    # AUTHOR_API_URL_TEMPLATE =  ("https://cfb-infinite-api.tcgplayer.com/content/author/{}/?source="
    #                             "cfb-infinite-content&rows=48&game=&format=")
    DECK_URL_TEMPLATE = FIREBALL_URL_TEMPLATE  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "channelfireball.com/author/" in url.lower() and not url.lower().endswith("/decks")
