"""

    mtg.lib.scrape.wayback
    ~~~~~~~~~~~~~~~~~~~~~~
    Utilities for scraping Wayback Machine pages.

    @author: mazz3rr

"""
import backoff
from bs4 import BeautifulSoup
from wayback import WaybackClient
from wayback.exceptions import MementoPlaybackError, WaybackException, WaybackRetryError

from mtg.lib.time import timed
from mtg.lib.scrape.core import _log


def _wayback_predicate(soup: BeautifulSoup | None) -> bool:
    if soup and "Error connecting to database" in str(soup):
        _log.warning(
            "Problems with connecting to Internet Archive's database. Re-trying with backoff...")
        return True
    return False


@timed("fetching wayback soup")
@backoff.on_predicate(
    backoff.expo,
    predicate=_wayback_predicate,
    jitter=None,
    max_tries=7
)
def fetch_wayback_soup(url: str) -> BeautifulSoup | None:
    """Fetch a BeautifulSoup object (or None) for a URL from Wayback Machine.
    """
    try:
        client = WaybackClient()
        _log.info(f"Searching for {url!r} in Wayback Machine...")
        if memento := next(client.search(url, limit=-1, fast_latest=True), None):
            try:
                response = client.get_memento(memento, exact=False)
            except MementoPlaybackError:
                _log.warning(f"Wayback Machine memento for {url!r} could not be retrieved")
                return None
            return BeautifulSoup(response.text, "lxml")
        return None
    except (WaybackException, WaybackRetryError) as e:
        _log.warning(f"Wayback Machine failed with: {e!r}")
        return None
