"""

    mtg.deck.scrapers.edhtop16.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape EDHTop 16 deck containers.

    @author: z33k

"""
import json
import logging

from mtg import Json
from mtg.deck.scrapers import DeckUrlsContainerScraper
from mtg.deck.scrapers.moxfield import MoxfieldDeckScraper
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)


@DeckUrlsContainerScraper.registered
class EdhTop16TournamentScraper(DeckUrlsContainerScraper):
    """Scraper of EDHTop 16 tournament page.
    """
    CONTAINER_NAME = "EDHTop16 tournament"  # override
    _DECK_SCRAPERS = MoxfieldDeckScraper,  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "edhtop16.com/tournament/" in url.lower()

    @staticmethod
    def _process_data(data: Json) -> list[str]:
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
        return self._process_data(data)


@DeckUrlsContainerScraper.registered
class EdhTop16CommanderScraper(EdhTop16TournamentScraper):
    """Scraper of EDHTop 16 commander page.
    """
    CONTAINER_NAME = "EDHTop16 commander"  # override
    _DECK_SCRAPERS = MoxfieldDeckScraper,  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "edhtop16.com/commander/" in url.lower()

    @staticmethod
    def _process_data(data: Json) -> list[str]:  # override
        urls = []
        match data:
            case {
                "props": {
                    "pageProps": {
                        "payload": {
                            "data": {
                                "commander": {
                                    "entries": {
                                        "edges": edges
                                    }
                                }
                            }
                        }
                    }
                }
            }:
                for edge in edges:
                    urls.append(edge["node"]["decklist"])
            case _:
                pass
        return urls
