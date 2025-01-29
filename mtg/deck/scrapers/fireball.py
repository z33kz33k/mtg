"""

    mtg.deck.scrapers.fireball.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape ChannelFireball decklists.

    @author: z33k

"""
import logging

from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper, DecksJsonContainerScraper
from mtg.deck.scrapers.tcgplayer import (
    TcgPlayerInfiniteArticleScraper, TcgPlayerInfiniteDeckScraper, TcgPlayerInfinitePlayerScraper)

_log = logging.getLogger(__name__)
FIREBALL_URL_TEMPLATE = "https://www.channelfireball.com{}"


@DeckScraper.registered
class ChannelFireballDeckScraper(TcgPlayerInfiniteDeckScraper):
    """Scraper of ChannelFireball decklist page.
    """
    # override
    API_URL_TEMPLATE = ("https://cfb-infinite-api.tcgplayer.com/deck/magic/{}"
                        "/?source=cfb-infinite-content&subDecks=true&cards=true&stats=true")

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
    API_URL_TEMPLATE = ("https://cfb-infinite-api.tcgplayer.com/content/decks/magic?source="
                        "cfb-infinite-content&rows=100&format=&playerName={}&latest=true"
                        "&sort=created&order=desc")
    _DECK_SCRAPERS = ChannelFireballDeckScraper,  # override
    _DECK_URL_TEMPLATE = FIREBALL_URL_TEMPLATE

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "channelfireball.com/magic-the-gathering/decks/player/" in url.lower()


@DecksJsonContainerScraper.registered
class ChannelFireballArticleScraper(TcgPlayerInfiniteArticleScraper):
    """Scraper of ChannelFireball article page.
    """
    CONTAINER_NAME = "ChannelFireball article"  # override
    API_URL_TEMPLATE = ChannelFireballDeckScraper.API_URL_TEMPLATE

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return f"channelfireball.com/article/" in url.lower()

