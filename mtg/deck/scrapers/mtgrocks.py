"""

    mtg.deck.scrapers.mtgrocks.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGRocks articles for decklists.

    MTGRocks uses a third-party provider (MTGDecks.net) for its articles' decklists.

    @author: z33k

"""
import json
import logging
from typing import Type, override

import dateutil.parser
from bs4 import Tag

from mtg import Json
from mtg.deck.scrapers import ContainerScraper, FolderContainerScraper, HybridContainerScraper, \
    is_in_domain_but_not_main
from mtg.utils.json import Node
from mtg.utils.scrape import ScrapingError, strip_url_query

_log = logging.getLogger(__name__)


@HybridContainerScraper.registered
class MtgRocksArticleScraper(HybridContainerScraper):
    """Scraper of MTGRocks article page.
    """
    CONTAINER_NAME = "MTGRocks article"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        tokens = ("/mtg-arena-codes/", "/deck-builder/", "/category/", "/sitemap/", "/about-us/",
                  "/editorial-policy/", "/privacy-policy/")
        return is_in_domain_but_not_main(
            url, "mtgrocks.com") and not any(t in url.lower() for t in tokens)

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
        script_tag = self._soup.find("script", type="application/ld+json")
        if not script_tag:
            raise ScrapingError("Metadata <script> tag not found", scraper=type(self), url=self.url)
        node = Node(json.loads(script_tag.text))
        if author_node := node.find(lambda n: "author" in n.data and "name" in n.data["author"]):
            self._metadata.setdefault("article", {})["author"] = author_node.data["author"]["name"]
        if title_node := node.find(lambda n: "headline" in n.data):
            self._metadata.setdefault("article", {})["title"] = title_node.data["headline"]
        if date_node := node.find(lambda n: "datePublished" in n.data):
            self._metadata.setdefault("article", {})["date"] = dateutil.parser.parse(
                date_node.data["datePublished"]).date()
        if desc_node := node.find(lambda n: "description" in n.data):
            self._metadata.setdefault("article", {})["description"] = desc_node.data["description"]
        if keywords_node := node.find(lambda n: "keywords" in n.data):
            self._metadata.setdefault(
                "article", {})["tags"] = self.process_metadata_deck_tags(
                keywords_node.data["keywords"])

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        iframe_urls = [  # MTGDecks.net decklists
            tag.attrs["data-lazy-src"].removesuffix("/iframe")
            for tag in self._soup.find_all("iframe", {"data-lazy-src": lambda d: d})]
        iframe_urls, _ = self._sift_links(*iframe_urls)

        article_tag = self._soup.select_one("div.elementor-widget-container")
        if not article_tag:
            err = ScrapingError("Article tag not found", scraper=type(self), url=self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            return iframe_urls, [], [], []
        deck_urls, container_urls = self._get_links_from_tags(*article_tag.find_all("p"))
        deck_urls = sorted({*iframe_urls, *deck_urls}) if deck_urls else iframe_urls
        return deck_urls, [], [], container_urls


@HybridContainerScraper.registered
class MtgRocksAuthorScraper(HybridContainerScraper):
    """Scraper of MTGRocks author page.
    """
    CONTAINER_NAME = "MTGRocks author"  # override
    CONTAINER_SCRAPERS = MtgRocksArticleScraper,  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return "mtgrocks.com/author/" in url.lower()

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        listing_tag = self._soup.select_one("div.jet-listing-grid")
        if not listing_tag:
            err = ScrapingError("Listing tag not found", scraper=type(self), url=self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            return [], [], [], []
        _, container_urls = self._get_links_from_tags(listing_tag)
        return [], [], [], container_urls
