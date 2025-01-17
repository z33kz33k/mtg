"""

    mtg.deck.scrapers.edhtop16.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape EDHTop 16 deck containers.

    @author: z33k

"""
import json
import logging

from mtg.deck.scrapers import DeckUrlsContainerScraper
from mtg.deck.scrapers.moxfield import MoxfieldDeckScraper
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)


@DeckUrlsContainerScraper.registered
class EdhTop16TournamentScraper(DeckUrlsContainerScraper):
    """Scraper of EDHTop 16 event page.
    """
    CONTAINER_NAME = "EDHTop16 tournament"  # override
    _DECK_SCRAPERS = MoxfieldDeckScraper,  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "edhtop16.com/tournament/" in url.lower()

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning(self._error_msg)
            return []

        script_tag = self._soup.find("script", id="__NEXT_DATA__")
        if not script_tag:
            _log.warning(self._error_msg)
            return []

        data = json.loads(script_tag.text)
        urls = []
        match data:
            case {
                "props": {
                    "pageProps": {
                        "payload": {
                            "data": {
                                "tournament": {
                                    "entries": entries
                                }
                            }
                        }
                    }
                }
            }:
                for entry in entries:
                    urls.append(entry["decklist"])
            case _:
                pass

        return urls
