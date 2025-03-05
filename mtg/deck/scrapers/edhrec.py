"""

    mtg.deck.scrapers.edhrec.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape EDHREC decklists.

    @author: z33k

"""
import json
import logging
import re
from datetime import datetime
from typing import override

import dateutil.parser
from bs4 import BeautifulSoup, Tag

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper, HybridContainerScraper, TagBasedDeckParser
from mtg.deck.scrapers.archidekt import ArchidektFolderScraper
from mtg.deck.scrapers.cardsrealm import CardsrealmFolderScraper
from mtg.deck.scrapers.moxfield import MoxfieldBookmarkScraper
from mtg.deck.scrapers.tappedout import TappedoutFolderScraper
from mtg.deck.scrapers.topdeck import DECK_SCRAPERS as TOPDECK_SCRAPERS
from mtg.scryfall import Card
from mtg.utils import ParsingError, prepend
from mtg.utils.scrape import ScrapingError, get_links, strip_url_query
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)
URL_PREFIX = "https://edhrec.com"


def get_source(src: str) -> str | None:
    if ".edhrec.com" in src:
        _, *parts = src.split(".")
        return ".".join(parts)
    return None


def _get_data(url: str, data_key="data") -> tuple[Json, BeautifulSoup]:
    soup = getsoup(url)
    if not soup:
        raise ScrapingError("Page not available")
    script_tag = soup.find("script", id="__NEXT_DATA__")
    try:
        data = json.loads(script_tag.text)
        deck_data = data["props"]["pageProps"][data_key]
    except (AttributeError, KeyError):
        raise ScrapingError("Deck data not available")
    return deck_data, soup


@DeckScraper.registered
class EdhrecPreviewDeckScraper(DeckScraper):
    """Scraper of EDHREC preview decklist page.
    """
    COLORS_TO_BASIC_LANDS = {
        "W": "Plains",
        "U": "Island",
        "B": "Swamp",
        "R": "Mountain",
        "G": "Forest",
    }

    @property
    def cards(self) -> list[Card]:
        cards = []
        if self._commander:
            cards.append(self._commander)
        if self._partner_commander:
            cards.append(self._partner_commander)
        cards += self._maindeck
        return cards

    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "edhrec.com/" in url.lower() and "/deckpreview/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        self._deck_data, self._soup = _get_data(self.url)

    @override
    def _parse_metadata(self) -> None:
        self._update_fmt("commander")
        self._metadata["date"] = datetime.fromisoformat(self._deck_data["savedate"]).date()
        if header := self._deck_data.get("header"):
            self._metadata["name"] = header
        self._metadata["is_cedh"] = self._deck_data["cedh"]
        if edhrec_tags := self._deck_data.get("edhrec_tags"):
            self._metadata["edhrec_tags"] = edhrec_tags
        if tags := self._deck_data.get("tags"):
            self._metadata["tags"] = self.process_metadata_deck_tags(tags)
        if salt := self._deck_data.get("salt"):
            self._metadata["salt"] = salt
        if theme := self._deck_data.get("theme"):
            self._metadata["theme"] = theme
        if tribe := self._deck_data.get("tribe"):
            self._metadata["tribe"] = tribe

    def _add_basic_lands(self) -> None:
        lands = [self.COLORS_TO_BASIC_LANDS[c] for c in self._deck_data["coloridentity"]]
        pool = [self.find_card(l) for l in lands]
        cursor = 0
        while len(self.cards) < 100:
            self._maindeck.append(pool[cursor])
            cursor += 1
            if cursor == len(pool):
                cursor = 0

    @override
    def _parse_decklist(self) -> None:
        for card_name in self._deck_data["cards"]:
            self._maindeck += self.get_playset(self.find_card(card_name), 1)

        for card_name in [c for c in self._deck_data["commanders"] if c]:
            card = self.find_card(card_name)
            self._set_commander(card)

        self._add_basic_lands()


@DeckScraper.registered
class EdhrecAverageDeckScraper(DeckScraper):
    """Scraper of EDHREC average decklist page and commander page.
    """
    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return ("edhrec.com/" in url.lower()
                and ("/average-decks/" in url.lower() or "/commanders/" in url.lower())
                and "/month" not in url.lower())

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(url)
        return url.replace("/commanders/", "/average-decks/")

    @override
    def _pre_parse(self) -> None:
        self._deck_data, self._soup = _get_data(self.url)

    @override
    def _parse_metadata(self) -> None:
        self._update_fmt("commander")
        self._metadata["date"] = datetime.today().date()
        if header := self._deck_data.get("header"):
            self._metadata["name"] = header

    @override
    def _parse_decklist(self) -> None:
        for i, card_text in enumerate(self._deck_data["deck"]):
            qty, card_name = card_text.split(maxsplit=1)
            card = self.find_card(card_name)
            if i == 0:
                self._set_commander(card)
            else:
                if card.is_partner:
                    self._set_commander(card)
                else:
                    self._maindeck += self.get_playset(card, int(qty))


class EdhrecArticleDeckParser(TagBasedDeckParser):
    """Parser of an EDHREC decklist HTML tag (that lives inside <script> JSON data).
    """
    def __init__(self, deck_tag: Tag, metadata: Json | None = None) -> None:
        super().__init__(deck_tag, metadata)
        self._arena_decklist = ""

    @override
    def _parse_metadata(self) -> None:
        if name := self._deck_tag.attrs.get("name"):
            self._metadata["name"] = name

    @staticmethod
    def _clean_decklist(decklist: str) -> str:
        # remove category tags and keep content between them
        # matches patterns like [Category]content[/Category]
        cleaned = re.sub(r'\[/?[\w\s!]+\]\n?', '', decklist)
        # remove leading/trailing whitespace and asterisks
        lines = [line.strip().lstrip('*') for line in cleaned.splitlines()]
        return '\n'.join([f"1{l}" if l.startswith(" ") else l for l in lines])

    @staticmethod
    def _handle_commander(decklist: str) -> str:
        if "[/Commander]\n" in decklist:
            prefix, decklist = decklist.split("[/Commander]\n", maxsplit=1)
            return "Commander" + prefix.removeprefix("[Commander]") + f"\nDeck\n{decklist}"
        return decklist

    @override
    def _parse_decklist(self) -> None:
        cards_text = self._deck_tag.attrs.get("cards")
        if not cards_text:
            raise ScrapingError("Cards data not found")
        decklist = self._handle_commander(cards_text)
        self._arena_decklist = self._clean_decklist(decklist)

    @override
    def _build_deck(self) -> Deck:
        try:
            return ArenaParser(
                self._arena_decklist, self._metadata).parse(
                suppress_parsing_errors=False, suppress_invalid_deck=False)
        except ValueError as err:
            if "No Arena lines" in str(err):
                raise ParsingError("Ill-formed Arena decklist")
            raise


@HybridContainerScraper.registered
class EdhrecArticleScraper(HybridContainerScraper):
    """Scraper of EDHREC article page.
    """
    CONTAINER_NAME = "EDHREC article"  # override
    # override
    DECK_SCRAPERS = tuple([EdhrecPreviewDeckScraper, EdhrecAverageDeckScraper, *TOPDECK_SCRAPERS])
    TAG_BASED_DECK_PARSER = EdhrecArticleDeckParser  # override
    # override
    CONTAINER_SCRAPERS = (
        ArchidektFolderScraper, MoxfieldBookmarkScraper, CardsrealmFolderScraper,
        TappedoutFolderScraper)

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return (("edhrec.com/articles/" in url.lower()
                 or "articles.edhrec.com/" in url.lower()) and "/author/" not in url.lower())

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        self._decks_data, self._soup = _get_data(self.url, data_key="post")

    @override
    def _parse_metadata(self) -> None:
        self._update_fmt("commander")
        if author := self._decks_data.get("author", {}).get("name"):
            self._metadata["author"] = author
        if date := self._decks_data.get("date"):
            self._metadata["date"] = dateutil.parser.parse(date).date()
        if excerpt := self._decks_data.get("excerpt"):
            self._metadata.setdefault("article", {})["excerpt"] = excerpt
        if title := self._decks_data.get("title"):
            self._metadata.setdefault("article", {})["title"] = title
        if tags := self._decks_data.get("tags"):
            self._metadata["tags"] = self.process_metadata_deck_tags(tags)

    def _collect_tags(self) -> list[Tag]:
        content_soup = BeautifulSoup(self._decks_data["content"], "lxml")
        return [*content_soup.find_all("span", class_="edhrecp__deck-s")]

    def _collect_urls(self) -> tuple[list[str], list[str]]:
        links = get_links(self._soup, query_stripped=True)
        tokens = "/deckpreview/", "/average-decks/", "/commanders/"
        links = [
            prepend(l, URL_PREFIX) if any(l.startswith(t) for t in tokens) else l for l in links]
        return self._sift_links(*links)

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        self._parse_metadata()
        deck_urls, container_urls = self._collect_urls()
        return deck_urls, self._collect_tags(), [], container_urls


@HybridContainerScraper.registered
class EdhrecAuthorScraper(HybridContainerScraper):
    """Scraper of EDHREC author page.
    """
    CONTAINER_NAME = "EDHREC author"  # override
    CONTAINER_SCRAPERS = EdhrecArticleScraper,  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return (("edhrec.com/articles/" in url.lower()
                 or "articles.edhrec.com/" in url.lower()) and "/author/" in url.lower())

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        self._decks_data, self._soup = _get_data(self.url, data_key="posts")

    @override
    def _parse_metadata(self) -> None:
        pass

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        prefix = f'{URL_PREFIX}/articles/'
        return [], [], [], [prepend(d["slug"], prefix) for d in self._decks_data]


