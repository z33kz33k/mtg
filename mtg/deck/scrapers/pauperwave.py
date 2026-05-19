"""

    mtg.deck.scrapers.pauperwave
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Pauperwave decklists.

    @author: mazz3rr

"""
import json
import logging
from datetime import date
from typing import Any, override

from mtg.constants import Json
from mtg.deck.abc import DeckJsonParser
from mtg.deck.scrapers.abc import DecksJsonContainerScraper
from mtg.lib.common import Noop
from mtg.lib.scrape.core import (
    ScrapingError, fetch_json, get_path_segments, is_more_than_root_path,
    strip_url_query,
)
from mtg.scryfall import Card
from mtg.session import ScrapingSession

_log = logging.getLogger(__name__)


class PauperwaveDeckJsonParser(DeckJsonParser):
    """Parser of Pauperwave decklist JSON data.
    """
    @override
    def _parse_input_for_metadata(self) -> None:
        self.update_metadata(**self._deck_json["metadata"])

    def _parse_card_data(self, card_data: dict) -> list[Card]:
        qty, name = card_data["quantity"], card_data["name"]
        return self.get_playset(self.find_card(name), qty)

    @override
    def _parse_input_for_decklist(self) -> None:
        cards_data = self._deck_json["cards"]
        for cat, card_list in cards_data.items():
            board = self._sideboard if cat == "Sideboard" else self._maindeck
            for card_data in card_list:
                if cat == "Commander":  # assumed case only (couldn't produce an example)
                    self._set_commander(self._parse_card_data(card_data)[0])
                else:
                    board += self._parse_card_data(card_data)
        self._metadata["format"] = "paupercommander" if self._commander else "pauper"


@DecksJsonContainerScraper.registered
class PauperwaveArticleScraper(DecksJsonContainerScraper):
    """Scraper of Pauperwave article page.
    """
    CONTAINER_NAME = "Pauperwave article"  # override
    DECK_JSON_PARSER_TYPE = PauperwaveDeckJsonParser # override
    JSON_FROM_SOUP = True  # override
    METADATA_BEFORE_DECKS = False
    _HOOK = "/_payload.json?"
    EXAMPLE_URLS = (
        "https://blog.pauperwave.org/articles/2026-03-31-dennis-garbati-paupergeddon-spring-2026", # report
        "https://blog.pauperwave.org/articles/2026-04-26-pauperancino",  # decklist
        "https://blog.pauperwave.org/articles/2025-12-06-tutorial-pingers",  # tutorial
    )

    def __init__(
        self, url: str, metadata: Json | None = None,
        session: ScrapingSession | Noop | None = None) -> None:
        super().__init__(url, metadata, session)
        self._sentinel_item: dict | None = None

    @classmethod
    @override
    def is_valid_url(cls, url: str) -> bool:
        return is_more_than_root_path(url, "blog.pauperwave.org", "articles")

    @classmethod
    @override
    def normalize_url(cls, url: str) -> str:
        url = super().normalize_url(url)
        return strip_url_query(url)

    def _get_article_id(self) -> str:
        tag = self._soup.find("link", href=lambda h: h and self._HOOK in h)
        if not tag or not tag.attrs.get("href"):
            raise ScrapingError("No article ID tag", scraper=type(self), url=self.url)
        *_, article_id = tag["href"].split(self._HOOK)
        return article_id

    def _build_api_url(self) -> str:
        _, second, *_ = get_path_segments(self.url)
        return f"https://blog.pauperwave.org/articles/{second}{self._HOOK}{self._get_article_id()}"

    @override
    def _extract_json(self) -> None:
        self._json = fetch_json(self._build_api_url())

    @staticmethod
    def _is_sentinel_item(item: Any) -> bool:
        return isinstance(item, dict) and "__hash__" in item

    @override
    def _validate_json(self) -> None:
        super()._validate_json()
        if not isinstance(self._json, list) and any(
            self._is_sentinel_item(item) for item in self._json):
            raise ScrapingError("Invalid JSON data", scraper=type(self), url=self.url)

    @override
    def _parse_input_for_metadata(self) -> None:
        title_idx = self._sentinel_item["title"]
        self._metadata["article"] = {}
        self._metadata["article"]["title"] = self._json[title_idx]
        author_idx = self._sentinel_item["author"]
        self._metadata["article"]["author"] = self._json[author_idx]
        date_idx = self._sentinel_item["date"]
        self._metadata["article"]["date"] = date.fromisoformat(self._json[date_idx])
        desc_idx = self._sentinel_item["description"]
        self._metadata["article"]["description"] = self._json[desc_idx]
        tags_idx = self._sentinel_item["tags"]
        tags = [self._json[idx] for idx in self._json[tags_idx]]
        self._metadata["article"]["tags"] = self.normalize_metadata_deck_tags(tags)

    def _trim_data(self) -> None:
        """Trim the fetched JSON for it to hold only this-article-relevant data.
        """
        data = []
        sentinels = []
        for item in self._json:
            if len(sentinels) > 1:
                break
            if self._is_sentinel_item(item):
                if not self._sentinel_item:
                    self._sentinel_item = item
                sentinels.append(item)
            data.append(item)
        self._json = data[:-1]  # without last sentinel item

    def _build_deck_json(self, item: dict) -> dict:
        name = self._json[item["name"]]
        player = self._json[item["player"]]
        placement = self._json[item["placement"]]
        cards = self._json[item["parsed-cards"]]
        return {
            "metadata": {
                "name": name,
                "author": player,
                "place": placement,
            },
            "cards": json.loads(cards),
        }

    @override
    def _parse_input_for_decks_data(self) -> None:
        self._trim_data()
        self._parse_input_for_metadata()
        self._decks_json = [
            self._build_deck_json(item) for item in self._json
            if isinstance(item, dict) and "anchor-id" in item
        ]
