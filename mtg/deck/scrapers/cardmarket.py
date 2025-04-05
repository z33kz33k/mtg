"""

    mtg.deck.scrapers.cardmarket.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Cardmarket decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser
from bs4 import Tag
from selenium.common import TimeoutException

from mtg import Json
from mtg.deck.scrapers import HybridContainerScraper, TagBasedDeckParser
from mtg.scryfall import COMMANDER_FORMATS, Card, all_formats
from mtg.utils import from_iterable
from mtg.utils.scrape import ScrapingError, strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup

_log = logging.getLogger(__name__)


class CardmarketDeckTagParser(TagBasedDeckParser):
    """Parser of Cardmarket decklist HTML tag.
    """
    @override
    def _parse_metadata(self) -> None:
        title = self._deck_tag.select_one("thead").text.strip()
        if ", " in title:
            name_part, *other_parts = title.split(", ")
            tokens = [t.lower() for p in other_parts for t in p.split()]
            if "duel" in tokens and "commander" in tokens:
                self._update_fmt("duel")
            elif "pauper" in tokens and "commander" in tokens:
                self._update_fmt("paupercommander")
            elif "historic" in tokens and "brawl" in tokens:
                self._update_fmt("brawl")
            elif "standard" in tokens and "brawl" in tokens:
                self._update_fmt("standardbrawl")
            elif fmt := from_iterable(tokens, lambda t: t in all_formats()):
                self._update_fmt(fmt)
            self._metadata["details"] = [*other_parts]
            if "by" in name_part:
                name, author = name_part.split(" by ", maxsplit=1)
            else:
                name = name_part
                author = None
            if author:
                self._metadata["author"] = author
            self._metadata["name"] = name
        else:
            self._metadata["name"] = title
            if "commander" in self._metadata["article_tags"]:
                self._update_fmt("commander")

    @classmethod
    def _parse_card(cls, card_tag: Tag) -> list[Card]:
        qty, *_ = card_tag.text.strip().split()
        name = card_tag.find("hoverable-card").attrs["name"]
        return cls.get_playset(cls.find_card(name), int(qty))

    @override
    def _parse_decklist(self) -> None:
        has_sideboard = len([*self._deck_tag.find_all("thead")]) == 2
        ul_tags = [*self._deck_tag.select("ul")]
        for i, ul_tag in enumerate(ul_tags):
            board = self._sideboard if has_sideboard and i == len(ul_tags) - 1 else self._maindeck
            for li_tag in [t for t in ul_tag.select("li") if t.text.strip()]:
                board += self._parse_card(li_tag)
        has_commander = False
        if self.fmt and self.fmt in COMMANDER_FORMATS:
            has_commander = True
        if not self.fmt and len(self._maindeck) in (99, 100):
            has_commander = True
            self._update_fmt("commander")
        if has_commander and has_sideboard:
            self._derive_commander_from_sideboard()
        elif has_commander:
            self._set_commander(self._maindeck[0])
            del self._maindeck[0]


@HybridContainerScraper.registered
class CardmarketArticleScraper(HybridContainerScraper):
    """Scraper of Cardmarket article page.
    """
    CONTAINER_NAME = "Cardmarket article"  # override
    TAG_BASED_DECK_PARSER = CardmarketDeckTagParser  # override
    XPATH = "//div[@class='table-responsive mb-4']"

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "cardmarket.com/" in url.lower() and "/insight/articles/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    def _pre_parse(self) -> None:
        try:
            self._soup, _, _ = get_dynamic_soup(self.url, self.XPATH, wait_for_all=True)
        except TimeoutException:
            self._soup = None
        if not self._soup:
            raise ScrapingError(self._error_msg)
        cat_tag = self._soup.select_one("div.u-article-meta__category")
        if not cat_tag or cat_tag.text.strip().lower() != "magic":
            raise ScrapingError("Not a MtG article")

    @override
    def _parse_metadata(self) -> None:
        if author_tag := self._soup.select_one("div.u-article-meta__writer"):
            self._metadata["author"] = author_tag.text.strip()
        if date_tag := self._soup.select_one("div.u-article-meta__published"):
            self._metadata["date"] = dateutil.parser.parse(date_tag.text.strip()).date()
        if article_tags := [
            t.text.strip().lower() for t in self._soup.select("a.u-article-meta__tag")]:
            self._metadata["article_tags"] = article_tags

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        deck_tags = [*self._soup.select("div.table-responsive.mb-4")]
        self._parse_metadata()
        article_tag = self._soup.find("article")
        if not article_tag:
            _log.warning("Article tag not found")
            return [], deck_tags, [], []
        deck_urls, _ = self._get_links_from_tags(*article_tag.find_all("p"))
        return deck_urls, deck_tags, [], []
