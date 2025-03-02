"""

    mtg.deck.scrapers.topdeck.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TopDeck.gg deck containers.

    @author: z33k

"""
import logging
from typing import Type, override

from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.deck.scrapers.aetherhub import AetherhubDeckScraper
from mtg.deck.scrapers.archidekt import ArchidektDeckScraper
from mtg.deck.scrapers.cardboardlive import CardBoardLiveDeckScraper
from mtg.deck.scrapers.cardhoarder import CardhoarderDeckScraper
from mtg.deck.scrapers.deckbox import DeckboxDeckScraper
from mtg.deck.scrapers.deckstats import DeckstatsDeckScraper
from mtg.deck.scrapers.flexslot import FlexslotDeckScraper
from mtg.deck.scrapers.goldfish import GoldfishDeckScraper
from mtg.deck.scrapers.hareruya import InternationalHareruyaDeckScraper, JapaneseHareruyaDeckScraper
from mtg.deck.scrapers.magicville import MagicVilleDeckScraper
from mtg.deck.scrapers.manabox import ManaBoxDeckScraper
from mtg.deck.scrapers.manastack import ManaStackDeckScraper
from mtg.deck.scrapers.manatraders import ManatradersDeckScraper
from mtg.deck.scrapers.moxfield import MoxfieldDeckScraper
from mtg.deck.scrapers.mtgazone import MtgaZoneDeckScraper
from mtg.deck.scrapers.scryfall import ScryfallDeckScraper
from mtg.deck.scrapers.streamdecker import StreamdeckerDeckScraper
from mtg.deck.scrapers.tappedout import TappedoutDeckScraper
from mtg.deck.scrapers.tcgplayer import TcgPlayerDeckScraper, TcgPlayerInfiniteDeckScraper
from mtg.deck.scrapers.topdecked import TopDeckedRegularDeckScraper
from mtg.deck.scrapers.untapped import UntappedProfileDeckScraper, UntappedRegularDeckScraper
from mtg.utils.scrape import strip_url_query

_log = logging.getLogger(__name__)


def check_unexpected_urls(urls: list[str], *scrapers: Type[DeckScraper]) -> None:
    names = [scraper.__name__ for scraper in scrapers]
    if unexpected := [url for url in urls if url.startswith("http") and
                      not any(s.is_deck_url(url) for s in scrapers)]:
        _log.warning(f"Non-{names} deck(s) found: {', '.join(unexpected)}")


DECK_SCRAPERS = (
    AetherhubDeckScraper,  # not seen
    ArchidektDeckScraper,
    CardBoardLiveDeckScraper,  # not seen
    CardhoarderDeckScraper,  # not seen
    DeckboxDeckScraper,
    DeckstatsDeckScraper,  # not seen
    FlexslotDeckScraper,  # not seen
    GoldfishDeckScraper,
    InternationalHareruyaDeckScraper,  # not seen
    JapaneseHareruyaDeckScraper,  # not seen
    MagicVilleDeckScraper,  # not seen
    ManaBoxDeckScraper,
    ManaStackDeckScraper,
    ManatradersDeckScraper,  # not seen
    MoxfieldDeckScraper,
    MtgaZoneDeckScraper,  # not seen
    ScryfallDeckScraper,
    StreamdeckerDeckScraper,  # not seen
    TappedoutDeckScraper,
    TcgPlayerDeckScraper,  # not seen
    TcgPlayerInfiniteDeckScraper,  # not seen
    TopDeckedRegularDeckScraper,  # not seen
    UntappedRegularDeckScraper,  # not seen
    UntappedProfileDeckScraper,  # not seen
)


@DeckUrlsContainerScraper.registered
class TopDeckBracketScraper(DeckUrlsContainerScraper):
    """Scraper of TopDeck.gg bracket page.
    """
    CONTAINER_NAME = "TopDeck.gg bracket"  # override
    XPATH = "//table[contains(@class, 'table') and contains(@class, 'dataTable')]"  # override
    DECK_SCRAPERS = DECK_SCRAPERS # override

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
        check_unexpected_urls(deck_urls, *self.DECK_SCRAPERS)
        return deck_urls


@DeckUrlsContainerScraper.registered
class TopDeckProfileScraper(DeckUrlsContainerScraper):
    """Scraper of TopDeck.gg profile page.
    """
    CONTAINER_NAME = "TopDeck.gg profile"  # override
    XPATH = ("//a[contains(@class, 'btn') and contains(@class, 'btn-sm') "
             "and not(contains(@href, 'topdeck.gg'))]")  # override
    DECK_SCRAPERS = DECK_SCRAPERS  # override

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
        check_unexpected_urls(deck_urls, *self.DECK_SCRAPERS)
        return deck_urls
