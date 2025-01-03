"""

    mtg.deck.scrapers.mtgazone.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTG Arena Zone decklists.

    @author: z33k

"""
import contextlib
import logging
from datetime import datetime
from typing import Iterable

import backoff
from bs4 import Tag
from requests import ConnectionError, HTTPError, ReadTimeout

from mtg import Json
from mtg.deck import Deck, Mode
from mtg.deck.scrapers import DeckScraper, DeckTagsContainerScraper, DeckUrlsContainerScraper, \
    TagBasedDeckParser
from mtg.scryfall import ARENA_FORMATS, Card
from mtg.utils import extract_int, from_iterable, timed
from mtg.utils.scrape import ScrapingError, getsoup, strip_url_params

_log = logging.getLogger(__name__)


# alternative approach would be to scrape:
# self._soup.find("input", {"type": "hidden", "name": "c"}).attrs["value"].split("||")
# but it has a downside of not having clear sideboard-maindeck separation
class MtgaZoneDeckTagParser(TagBasedDeckParser):
    """Parser of a MTG Arena Zone decklist HTML tag.
    """
    def _parse_metadata(self) -> None:  # override
        name_author_tag = self._deck_tag.find("div", class_="name-container")
        if not name_author_tag:
            raise ScrapingError(
                "Name tag not found. The deck you're trying to scrape has been most probably "
                "paywalled by MTGAZone")
        name_tag = name_author_tag.find("div", class_="name")
        name, author, event = name_tag.text.strip(), None, None
        if " by " in name:
            name, author = name.split(" by ")
        elif " – " in name:
            name, event = name.split(" – ")
        self._metadata["name"] = name
        author_tag = name_author_tag.find("div", class_="by")
        if not author_tag:
            raise ScrapingError(
                "Author tag not found. The deck you're trying to scrape has been most "
                "probably paywalled by MTGAZone")
        author = author_tag.text.strip().removeprefix("by ")
        self._metadata["author"] = author
        if event:
            self._metadata["event"] = event
        fmt_tag = self._deck_tag.find("div", class_="format")
        if not fmt_tag:
            raise ScrapingError(
                "Format tag not found. The deck you're trying to scrape has been most probably "
                "paywalled by MTGAZone")
        fmt = fmt_tag.text.strip().lower()
        self._update_fmt(fmt)
        if time_tag := self._deck_tag.find("time", class_="ct-meta-element-date"):
            self._metadata["date"] = datetime.fromisoformat(time_tag.attrs["datetime"]).date()

    @classmethod
    def _to_playset(cls, card_tag) -> list[Card]:
        quantity = int(card_tag.attrs["data-quantity"])
        a_tag = card_tag.find("a")
        name = a_tag.text.strip()
        *_, scryfall_id = a_tag.attrs["data-cimg"].split("/")
        scryfall_id, *_ = scryfall_id.split(".jpg")
        return cls.get_playset(cls.find_card(name, scryfall_id=scryfall_id), quantity)

    def _process_decklist(self, decklist_tag: Tag) -> list[Card]:
        decklist = []
        card_tags = decklist_tag.find_all("div", class_="card")
        for card_tag in card_tags:
            decklist.extend(self._to_playset(card_tag))
        return decklist

    def _parse_decklist(self) -> None:  # override
        if commander_tag := self._deck_tag.select_one("div.decklist.short.commander"):
            for card in self._process_decklist(commander_tag):
                self._set_commander(card)

        if companion_tag := self._deck_tag.select_one("div.decklist.short.companion"):
            self._companion = self._process_decklist(companion_tag)[0]

        main_tag = self._deck_tag.select_one("div.decklist.main")
        self._maindeck = self._process_decklist(main_tag)

        if sideboard_tags := self._deck_tag.select("div.decklist.sideboard"):
            with contextlib.suppress(IndexError):
                sideboard_tag = sideboard_tags[1]
                self._sideboard = self._process_decklist(sideboard_tag)


@DeckScraper.registered
class MtgaZoneDeckScraper(DeckScraper):
    """Scraper of MTG Arena Zone decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_parser: MtgaZoneDeckTagParser | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgazone.com/user-decks/" in url.lower() or "mtgazone.com/deck/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url, keep_fragment=False)

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        deck_tag = self._soup.find("div", class_="deck-block")
        if deck_tag is None:
            raise ScrapingError("Deck data not found (probably paywalled)")
        self._deck_parser = MtgaZoneDeckTagParser(deck_tag, self._metadata)

    def _parse_metadata(self) -> None:  # override
        pass

    def _parse_decklist(self) -> None:  # override
        pass

    def _build_deck(self) -> Deck:  # override
        return self._deck_parser.parse()


@DeckTagsContainerScraper.registered
class MtgaZoneArticleScraper(DeckTagsContainerScraper):
    """Scraper of MTG Arena Zone article page.
    """
    CONTAINER_NAME = "MTGAZone article"
    _DECK_PARSER = MtgaZoneDeckTagParser

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return f"mtgazone.com/" in url.lower() and not any(
            t in url.lower() for t in ("/user-decks", "/deck/", "/plans/premium",
                                       "/mtg-arena-codes", "/author/"))

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url, keep_fragment=False)

    def _collect(self) -> list[Tag]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning(self._error_msg)
            return []

        deck_tags = [*self._soup.find_all("div", class_="deck-block")]
        if not deck_tags:
            if not deck_tags:
                _log.warning(self._error_msg)
                return []

        return deck_tags


@DeckUrlsContainerScraper.registered
class MtgaZoneAuthorScraper(DeckUrlsContainerScraper):
    """Scraper of MTG Arena Zone article page.
    """
    CONTAINER_NAME = "MTGAZone author"  # override
    _DECK_SCRAPER = MtgaZoneDeckScraper  # override

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._deck_urls, self._article_urls = [], []

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "mtgazone.com/author/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url, keep_fragment=False)

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning(self._error_msg)
            return []

        links = [
            t.attrs["href"].removesuffix("/") for t in self._soup.select("article > h2 > a")]
        deck_urls = [l for l in links if MtgaZoneDeckScraper.is_deck_url(l)]
        self._article_urls = [l for l in links if MtgaZoneArticleScraper.is_container_url(l)]

        return deck_urls

    # override
    @timed("nested container scraping", precision=2)
    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def scrape(
            self, already_scraped_deck_urls: Iterable[str] = (),
            already_failed_deck_urls: Iterable[str] = ()) -> tuple[list[Deck], set[str]]:
        decks, failed_deck_urls = [], set()
        self._deck_urls = self._collect()
        if self._deck_urls:
            _log.info(
                f"Gathered {len(self._deck_urls)} deck URL(s) from a {self.CONTAINER_NAME} at:"
                f" {self.url!r}")
            scraped_decks, scraped_failed = self._process_deck_urls(
                already_scraped_deck_urls, already_failed_deck_urls)
            decks.extend(scraped_decks)
            failed_deck_urls.update(scraped_failed)
        if self._article_urls:
            already_scraped_deck_urls = {
                url.removesuffix("/").lower() for url in already_scraped_deck_urls}
            _log.info(
                f"Gathered {len(self._article_urls)} article URL(s) from a {self.CONTAINER_NAME} "
                f"at: {self.url!r}")
            for i, url in enumerate(self._article_urls, start=1):
                sanitized_url = MtgaZoneArticleScraper.sanitize_url(url)
                if sanitized_url.lower() in already_scraped_deck_urls:
                    _log.info(f"Skipping already scraped article URL: {sanitized_url!r}...")
                elif sanitized_url.lower() in already_failed_deck_urls:
                    _log.info(f"Skipping already failed article URL: {sanitized_url!r}...")
                else:
                    _log.info(f"Scraping article {i}/{len(self._article_urls)}...")
                    article_decks = MtgaZoneArticleScraper(url, dict(self._metadata)).scrape()
                    if not article_decks:
                        failed_deck_urls.add(sanitized_url.lower())
                    else:
                        decks += [d for d in article_decks if d not in decks]
        return decks, failed_deck_urls


def _parse_tiers(table: Tag) -> dict[str, int]:
    tiers = {}
    for row in table.find_all("tr"):
        tier_col, deck_col = row.find_all("td")
        tier = extract_int(tier_col.find("strong").text)
        deck = deck_col.find("a").text.strip()
        tiers[deck] = tier
    return tiers


def _parse_meta_deck(deck_tag: Tag, decks2tiers: dict[str, int], deck_place: int) -> Deck:
    deck = MtgaZoneDeckTagParser(deck_tag).parse(suppress_invalid_deck=False)
    meta = {
        "meta": {
            "place": deck_place
        }
    }
    tier = decks2tiers.get(deck.name)
    if tier is None:
        deck_name = from_iterable(decks2tiers, lambda d: deck.name in d)
        if deck_name:
            tier = decks2tiers[deck_name]
    if tier:
        meta["meta"]["tier"] = tier
    deck.update_metadata(meta=meta["meta"])
    return deck


@timed("scraping meta decks")
def scrape_meta(fmt="standard", bo3=True) -> list[Deck]:
    formats = {fmt for fmt in ARENA_FORMATS if fmt not in {"brawl", "standardbrawl"}}
    formats = sorted({*formats, "pioneer"})
    fmt = fmt.lower()
    if fmt not in formats:
        raise ValueError(f"Invalid format: {fmt!r}. Can be only one of: {formats}")

    mode = "-bo3" if bo3 else "-bo1"
    if fmt == "pioneer":
        mode = ""
    url = f"https://mtgazone.com/{fmt}{mode}-metagame-tier-list/"

    soup = getsoup(url)
    if not soup:
        raise ScrapingError("Page not available")
    time_tag = soup.find("time", class_="ct-meta-element-date")
    deck_date = datetime.fromisoformat(time_tag.attrs["datetime"]).date()
    tier_table = soup.find("figure", class_="wp-block-table")
    table_body = tier_table.find("tbody")
    decks2tiers = _parse_tiers(table_body)

    decks = []
    for i, deck_tag in enumerate(soup.find_all("div", class_="deck-block"), start=1):
        deck = _parse_meta_deck(deck_tag, decks2tiers, i)
        deck.update_metadata(date=deck_date)
        deck.update_metadata(mode=mode[1:].title() if mode else Mode.BO3.value)
        decks.append(deck)

    return decks
