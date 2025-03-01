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

from bs4 import BeautifulSoup, Tag
import dateutil.parser

from mtg import DeckTagsContainerScraper, Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckScraper, TagBasedDeckParser
from mtg.scryfall import Card
from mtg.utils.scrape import ScrapingError
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)


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
    def is_deck_url(url: str) -> bool:  # override
        return "edhrec.com/" in url.lower() and "/deckpreview/" in url.lower()

    def _pre_parse(self) -> None:  # override
        self._deck_data, self._soup = _get_data(self.url)

    def _parse_metadata(self) -> None:  # override
        self._update_fmt("commander")
        self._metadata["date"] = datetime.fromisoformat(self._deck_data["savedate"]).date()
        if header := self._deck_data.get("header"):
            self._metadata["name"] = header
        self._metadata["is_cedh"] = self._deck_data["cedh"]
        if edhrec_tags := self._deck_data.get("edhrec_tags"):
            self._metadata["edhrec_tags"] = edhrec_tags
        if tags := self._deck_data.get("tags"):
            self._metadata["tags"] = tags
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

    def _parse_decklist(self) -> None:  # override
        for card_name in self._deck_data["cards"]:
            self._maindeck += self.get_playset(self.find_card(card_name), 1)

        for card_name in [c for c in self._deck_data["commanders"] if c]:
            card = self.find_card(card_name)
            self._set_commander(card)

        self._add_basic_lands()


@DeckScraper.registered
class EdhrecAverageDeckScraper(DeckScraper):
    """Scraper of EDHREC average decklist page.
    """
    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "edhrec.com/" in url.lower() and "/average-decks/" in url.lower()

    def _pre_parse(self) -> None:  # override
        self._deck_data, self._soup = _get_data(self.url)

    def _parse_metadata(self) -> None:  # override
        self._update_fmt("commander")
        self._metadata["date"] = datetime.today().date()
        if header := self._deck_data.get("header"):
            self._metadata["name"] = header

    def _parse_decklist(self) -> None:  # override
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

    def _parse_metadata(self) -> None:
        if name := self._deck_tag.attrs.get("name"):
            self._metadata["name"] = name

    @staticmethod
    def _clean_decklist(decklist: str) -> str:
        # remove category tags and keep content between them
        # matches patterns like [Category]content[/Category]
        cleaned = re.sub(r'\[/?\w+\]\n?', '', decklist)
        # remove leading/trailing whitespace and asterisks
        return '\n'.join(line.strip().lstrip('*') for line in cleaned.splitlines())

    @staticmethod
    def _handle_commander(decklist: str) -> str:
        if "[/Commander]\n" in decklist:
            prefix, decklist = decklist.split("[/Commander]\n", maxsplit=1)
            return "Commander" + prefix.removeprefix("[Commander]") + f"\nDeck\n{decklist}"
        return decklist

    def _parse_decklist(self) -> None:
        cards_text = self._deck_tag.attrs.get("cards")
        if not cards_text:
            raise ScrapingError("Cards data not found")
        decklist = self._handle_commander(cards_text)
        self._arena_decklist = self._clean_decklist(decklist)

    def _build_deck(self) -> Deck:
        return ArenaParser(
            self._arena_decklist.splitlines(), self._metadata).parse(suppress_invalid_deck=False)


# TODO: scraping contained Archidekt links, like here:
#  https://edhrec.com/articles/edhrecast-our-decks - this calls for refactoring of
#  HybridContainerScraper so it covers all hybrid cases
@DeckTagsContainerScraper.registered
class EdhrecArticleScraper(DeckTagsContainerScraper):
    """Scraper of EDHREC article page.
    """
    CONTAINER_NAME = "EDHREC article"  # override
    DECK_PARSER = EdhrecArticleDeckParser  # override

    @staticmethod
    def is_container_url(url: str) -> bool:
        return "edhrec.com/articles/" in url.lower() and "author" not in url.lower()

    def _pre_parse(self) -> None:  # override
        self._decks_data, self._soup = _get_data(self.url, data_key="post")

    def _parse_metadata(self) -> None:  # override
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
            self._metadata["tags"] = tags

    def _collect(self) -> list[Tag]:  # override
        self._parse_metadata()
        content_soup = BeautifulSoup(self._decks_data["content"], "lxml")
        return [*content_soup.find_all("span", class_="edhrecp__deck-s")]
