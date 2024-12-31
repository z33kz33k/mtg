"""

    mtg.deck.scrapers.mtgo.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGO decklists.

    @author: z33k

"""
import logging

import dateutil.parser
from bs4 import Tag

from mtg import SECRETS
from mtg.deck import Deck, Mode
from mtg.deck.scrapers import DeckUrlsContainerScraper, TagBasedDeckScraper, UrlBasedDeckScraper
from mtg.scryfall import all_formats
from mtg.utils import extract_int, timed
from mtg.utils.scrape import ScrapingError, getsoup, http_requests_counted, strip_url_params, \
    throttled_soup

_log = logging.getLogger(__name__)


HEADERS = {
    "Host": "www.mtgo.com",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Sec-GPC": "1",
    "Connection": "keep-alive",
    "Cookie": SECRETS["mtgo"]["cookie"],
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Priority": "u=0, i",
}


