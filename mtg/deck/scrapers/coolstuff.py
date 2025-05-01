"""

    mtg.deck.scrapers.coolstuff.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape CoolStuffInc decklists.

    @author: z33k

"""
import logging
from typing import Type, override

import dateutil.parser
from bs4 import Tag

from mtg import Json, SECRETS
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import ContainerScraper, FolderContainerScraper, HybridContainerScraper, \
    TagBasedDeckParser, is_in_domain_but_not_main
from mtg.utils import ParsingError, extract_int
from mtg.utils.scrape import ScrapingError, strip_url_query

_log = logging.getLogger(__name__)


HEADERS = {
    "Host": "www.coolstuffinc.com",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Sec-GPC": "1",
    "Connection": "keep-alive",
    "Cookie": SECRETS["coolstuff"]["cookie"],
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Priority": "u=0, i",
}


# TODO: a sub-parser to handle cases where there's no 'Export text' button


class CoolStuffIncDeckTagParser(TagBasedDeckParser):
    """Parser of an CoolStuffInc decklist HTML tag.
    """
    @property
    def commander_count(self) -> int:
        commander_tag = self._deck_tag.find(
            "li", class_="card-type", string=lambda s: s and "Commander (" in s)
        if commander_tag:
            return extract_int(commander_tag.text.strip())
        return 0

    @override
    def _parse_metadata(self) -> None:
        info_tag = self._deck_tag.find("h4")
        if not info_tag:
            raise ParsingError("Metadata tag not found")

        name, fmt, author, rest = "", "", "", []
        if "|" not in info_tag.text:
            name = info_tag.text.strip()
            fmt = self.derive_format_from_text(name)
        else:
            parts = info_tag.text.strip().split(" | ")
            if len(parts) == 2:
                name, author = parts
                fmt = self.derive_format_from_text(name)
            elif len(parts) == 3:
                name, fmt_text, author = parts
                fmt = self.derive_format_from_text(fmt_text)
            elif len(parts) > 3:
                name, fmt_text, author, *rest = parts
                fmt = self.derive_format_from_text(fmt_text)

        self._metadata["name"] = name.strip()
        if fmt:
            self._update_fmt(fmt)
        if author:
            self._metadata["author"] = author.strip()
        if rest:
            self._metadata["event"] = "".join(rest)

    @override
    def _parse_decklist(self) -> None:
        decklist_tag = self._deck_tag.find("a", {"data-reveal-id": "copydecklistmodal"})
        if not decklist_tag or not decklist_tag.attrs.get("data-text"):
            # TODO: return with None and delegate to sub-parser instead
            raise ParsingError("Decklist tag not found")
        decklist_text = decklist_tag.attrs["data-text"].strip()
        if "|~|" in decklist_text:
            maindeck, sideboard = decklist_text.split("|~|")
        else:
            maindeck, sideboard = decklist_text, ""
        maindeck = maindeck.split("|")
        sideboard = sideboard.split("|") if sideboard else []
        if self.commander_count:
            commander, maindeck = maindeck[:self.commander_count], maindeck[self.commander_count:]
        else:
            commander, maindeck = [], maindeck
        decklist = []
        if commander:
            decklist.append("Commander")
            decklist.extend(commander)
            decklist.append("")
        decklist.append("Deck")
        decklist += maindeck
        if sideboard:
            decklist.append("")
            decklist.append("Sideboard")
            decklist.extend(sideboard)
        self._decklist = "\n".join(decklist)

    @override
    def _build_deck(self) -> Deck | None:
        return ArenaParser(self._decklist, self._metadata).parse()


@HybridContainerScraper.registered
class CoolStuffIncArticleScraper(HybridContainerScraper):
    """Scraper of CoolStuffInc article page.
    """
    CONTAINER_NAME = "CoolStuffInc article"  # override
    HEADERS = HEADERS  # override
    TAG_BASED_DECK_PARSER = CoolStuffIncDeckTagParser  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return is_in_domain_but_not_main(url, "coolstuffinc.com/a")

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @classmethod
    @override
    def _get_container_scrapers(cls) -> set[Type[ContainerScraper]]:
        return FolderContainerScraper.get_registered_scrapers()

    @override
    def _parse_metadata(self) -> None:
        if header_tag := self._soup.find("header"):
            if title_tag := header_tag.find("h1"):
                self._metadata.setdefault("article", {})["title"] = title_tag.text.strip()
            if byline_tag := header_tag.find("div", class_="gm-article-byline"):
                if author_tag := byline_tag.find("a"):
                    self._metadata.setdefault("article", {})["author"] = author_tag.text.strip()
                if date_tag := byline_tag.find("div", string=lambda s: s and "Posted on " in s):
                    self._metadata["date"] = dateutil.parser.parse(
                        date_tag.text.strip().removeprefix("Posted on ")).date()

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        deck_tags = [*self._soup.select("div.gm-deck.row")]
        article_tag = self._soup.find("article")
        if not article_tag:
            err = ScrapingError("Article tag not found", scraper=type(self), url=self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            return [], deck_tags, [], []
        deck_urls, container_urls = self._get_links_from_tags(*article_tag.find_all("p"))
        return deck_urls, deck_tags, [], container_urls
