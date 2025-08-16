"""

    mtg.deck.scrapers.cardkingdom
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape decklists featured on CardKingdom Blog.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser
from bs4 import Tag

from mtg import Json, SECRETS
from mtg.deck.scrapers import HybridContainerScraper, UrlHook
from mtg.utils.scrape import ScrapingError, is_more_than_root_path, strip_url_query

_log = logging.getLogger(__name__)
HEADERS = {
    "Host": "blog.cardkingdom.com",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Sec-GPC": "1",
    "Connection": "keep-alive",
    "Cookie": SECRETS["cardkingdom"]["cookie"],
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Priority": "u=0, i",
    "TE": "trailers",
}


URL_HOOKS = (
    # article & author
    UrlHook(
        ('"blog.cardkingdom.com/"', ),
        ('-"/category/"', '-"/tag/"', '-"/submissions/"', '-"/updates/"'),
    ),
)


@HybridContainerScraper.registered
class CardKingdomArticleScraper(HybridContainerScraper):
    """Scraper of CardKingdom article page.
    """
    CONTAINER_NAME = "CardKingdom article"  # override
    HEADERS = HEADERS  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        tokens = "/category/", '/tag/', '/submissions/', '/updates/', '/author/'
        return is_more_than_root_path(
            url, "blog.cardkingdom.com") and not any(t in url.lower() for t in tokens)

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _parse_metadata(self) -> None:
        if header_tag := self._soup.select_one("header.entry-header"):
            if title_tag := header_tag.find("h1"):
                self._metadata.setdefault("article", {})["title"] = title_tag.text.strip()
            if p_tag := header_tag.find("p"):
                author_span, date_span, cat_span, *_ = p_tag.find_all("span")
                self._metadata.setdefault("article", {})["author"] = author_span.text.strip()
                if time_tag := date_span.find("time"):
                    self._metadata.setdefault("article", {})["date"] = dateutil.parser.parse(
                        time_tag.attrs["datetime"]).date()
                if categories := [a.text.strip() for a in cat_span.find_all("a")]:
                    self._metadata.setdefault(
                        "article", {})["tags"] = self.process_metadata_deck_tags(categories)

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        article_tag = self._soup.select_one("div.content")
        if not article_tag:
            err = ScrapingError("Article tag not found", scraper=type(self), url=self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            return [], [], [], []
        deck_urls, container_urls = self._find_links_in_tags(*article_tag.find_all("p"))
        return deck_urls, [], [], container_urls


@HybridContainerScraper.registered
class CardKingdomAuthorScraper(HybridContainerScraper):
    """Scraper of CardKingdom author page.
    """
    CONTAINER_NAME = "CardKingdom author"  # override
    CONTAINER_SCRAPERS = CardKingdomArticleScraper,  # override
    HEADERS = HEADERS  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "blog.cardkingdom.com/author/" in url.lower()

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        _, container_urls = self._find_links_in_tags(
            *self._soup.find_all("article"), css_selector="div.entry-wrap > header > h2 > a")
        return [], [], [], container_urls
