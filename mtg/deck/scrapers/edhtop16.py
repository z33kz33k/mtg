"""

    mtg.deck.scrapers.edhtop16.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape EDHTop 16 deck containers.

    @author: z33k

"""
import json
import logging
from typing import override

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckUrlsContainerScraper
from mtg.deck.scrapers.topdeck import check_unexpected_urls

_log = logging.getLogger(__name__)


@DeckUrlsContainerScraper.registered
class EdhTop16TournamentScraper(DeckUrlsContainerScraper):
    """Scraper of EDHTop 16 tournament page.
    """
    CONTAINER_NAME = "EDHTop16 tournament"  # override

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._arena_decklists = []

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "edhtop16.com/tournament/" in url.lower()

    @staticmethod
    def _resolve_decklist(decklist: str) -> str:
        tokens = decklist.split("1 ")[1:]
        commander, *playsets = [f"1 {t}" for t in tokens if t]
        return "\n".join(["Commander", commander, "", "Deck"] + [*playsets])

    def _process_decklist(self, decklist: str | None, urls: list[str]) -> None:
        if decklist:
            decklist = decklist.strip()
            if decklist.lower().startswith("http"):
                urls.append(decklist)
            else:
                try:
                    self._arena_decklists.append(self._resolve_decklist(decklist))
                except ValueError:
                    pass

    def _process_data(self, data: Json) -> list[str]:
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
                    decklist = entry["decklist"]
                    self._process_decklist(decklist, urls)
            case _:
                pass
        return urls

    @override
    def _collect(self) -> list[str]:
        script_tag = self._soup.find("script", id="__NEXT_DATA__")
        if not script_tag:
            _log.warning(self._error_msg)
            return []

        data = json.loads(script_tag.text)
        deck_urls = self._process_data(data)
        check_unexpected_urls(deck_urls, *self._get_deck_scrapers())

        return deck_urls

    @override
    def scrape(self) -> list[Deck]:
        decks = super().scrape()
        if self._arena_decklists:
            _log.info(
                f"Gathered {len(self._arena_decklists)} text decklists from a {self.CONTAINER_NAME}"
                f" at: {self.url!r}")
            for arena_decklist in self._arena_decklists:
                if deck := ArenaParser(arena_decklist, metadata=self._metadata).parse():
                    decks.append(deck)
        return decks


@DeckUrlsContainerScraper.registered
class EdhTop16CommanderScraper(EdhTop16TournamentScraper):
    """Scraper of EDHTop 16 commander page.
    """
    CONTAINER_NAME = "EDHTop16 commander"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "edhtop16.com/commander/" in url.lower()

    def _process_data(self, data: Json) -> list[str]:  # override
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
                    decklist = edge["node"]["decklist"]
                    self._process_decklist(decklist, urls)
            case _:
                pass
        return urls
