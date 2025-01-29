"""

    mtg.deck.scrapers.fireball.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape ChannelFireball decklists.

    @author: z33k

"""
import logging

from mtg.deck.scrapers import DeckScraper
from mtg.deck.scrapers.tcgplayer import TcgPlayerInfiniteDeckScraper

_log = logging.getLogger(__name__)


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
