"""

    mtg.deck.scrapers.playingmtg
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape PlayingMTG decklists.

    @author: mazz3rr

"""
import logging
from collections.abc import Iterator
from typing import override

import dateutil.parser

from mtg.deck.scrapers.abc import (
    DEFAULT_THROTTLING, DeckScraper, DeckUrlsContainerScraper,
    HybridContainerScraper,
)
from mtg.lib.numbers import extract_float, extract_int
from mtg.lib.scrape.core import (
    ScrapingError, fetch_json, find_links, find_next_sibling_tag,
    get_path_segments, is_more_than_root_path, normalize_url, prepend_url, strip_url_query,
)
from mtg.lib.scrape.dynamic import Xpath
from mtg.lib.time import date_from_unixtime

_log = logging.getLogger(__name__)
URL_PREFIX = "https://playingmtg.com"
_THROTTLING = DEFAULT_THROTTLING * 2


@DeckScraper.registered
class PlayingMtgDeckScraper(DeckScraper):
    """Scraper of PlayingMTG decklist page.
    """
    JSON_FROM_API = True
    EXAMPLE_URLS = (
        "https://playingmtg.com/decks/frodo-sam-and-their-favourite-squirrel-s-copy-2/",
        "https://playingmtg.com/decks/reckless-raid-mtg-arena-starter-deck/",
        "https://playingmtg.com/decks/greasefang-parhelion-jqckl/",
    )

    @classmethod
    @override
    def is_valid_url(cls, url: str) -> bool:
        return is_more_than_root_path(url, "playingmtg.com", "decks")

    @classmethod
    @override
    def normalize_url(cls, url: str) -> str:
        url = normalize_url(url, case_sensitive=True)
        return strip_url_query(url)

    def _get_slug(self) -> str:
        _, slug, *_ = get_path_segments(self._url)
        return slug

    @override
    def _fetch_json(self) -> None:
        slug = self._get_slug()
        api_url = f"https://api.dotgg.gg/cgfw/getdeck?game=magic&slug={slug}&mode=boards"
        self._json = fetch_json(api_url)

    @override
    def _validate_json(self) -> None:
        super()._validate_json()
        if not self._json.get("boards"):
            raise ScrapingError("No cards data", scraper=type(self), url=self.url)

    @override
    def _parse_input_for_metadata(self) -> None:
        if fmt := self._json.get("format"):
            self._update_fmt(fmt)
        if dt := self._json.get("date"):
            self._metadata["date"] = date_from_unixtime(int(dt), 1)
        if name := self._json.get("humanname"):
            self._metadata["name"] = name
        if desc := self._json.get("description"):
            self._metadata["description"] = desc
        if views := self._json.get("views"):
            self._metadata["views"] = int(views)
        if author := self._json.get("authornick"):
            self._metadata["author"] = author
        if archetype := self._json.get("archetype_name"):
            self._update_archetype_or_theme(archetype)

    def _get_boards_iterator(self) -> Iterator[tuple[int, dict]]:
        boards = self._json["boards"]
        if isinstance(boards, list):
            for i, item in enumerate(boards):
                yield i, item
        elif isinstance(boards, dict):
            for k, v in boards.items():
                yield int(k), v
        else:
            raise TypeError(f"Unexpected type for boards collection: '{type(boards)}'")

    @override
    def _parse_input_for_decklist(self) -> None:
        for board_code, cards_data in self._get_boards_iterator():
            board = self._sideboard if board_code == 1 else self._maindeck
            for set_num, qty in cards_data.items():
                set_code, colnum = set_num.split("-", maxsplit=1)
                card = self.find_card_by_collector_number(set_code, colnum)
                playset = self.get_playset(card, int(qty))
                if board_code == 2:
                    self._set_commander(card)
                else:
                    board += playset


# TODO
@DeckUrlsContainerScraper.registered
class PlayingMtgTournamentScraper(DeckUrlsContainerScraper):
    """Scraper of PlayingMTG tournament page.
    """
    SELENIUM_PARAMS = {  # override
        "xpaths": [
            Xpath('//div[text()="Event Date"]', wait_for_all=True),
        ],
    }
    THROTTLING = _THROTTLING  # override
    CONTAINER_NAME = "PlayingMTG tournament"  # override
    DECK_SCRAPER_TYPES = PlayingMtgDeckScraper,  # override
    DECK_URL_PREFIX = URL_PREFIX  # override
    EXAMPLE_URLS = (
        "https://playingmtg.com/tournaments/mtgo-league-3164/",
    )

    @classmethod
    @override
    def is_valid_url(cls, url: str) -> bool:
        return is_more_than_root_path(url, "playingmtg.com", "tournaments")

    def _parse_input_for_metadata(self) -> None:
        if event_date_hook := self._soup.find("div", string=lambda s: s and s == "Event Date"):
            self._metadata["event"] = {}
            # date
            date_tag = event_date_hook.parent
            date_text = date_tag.text.strip().removeprefix("Event Date").strip()
            self._metadata["event"]["date"] = dateutil.parser.parse(date_text).date()
            # name
            name_tag = find_next_sibling_tag(date_tag)
            if not name_tag:
                return
            self._metadata["event"]["name"] = name_tag.text.strip()
            # format and latest set
            fmt_set_tag = find_next_sibling_tag(name_tag)
            if not fmt_set_tag:
                return
            for tag in fmt_set_tag.find_all("div"):
                if "Latest set: " in tag.text:
                    self._metadata["event"]["latest_set"] = tag.text.strip().strip().removeprefix(
                        "Latest set: ").strip().lower()
                else:
                    self._metadata["event"]["format"] = tag.text.strip().lower()
            # themes
            info_tag = find_next_sibling_tag(fmt_set_tag)
            if not info_tag:
                return
            theme_tags = info_tag.find_all("div")
            self._metadata["event"]["themes"] = []
            for tag in theme_tags:
                data = {}
                if theme_name_tag := tag.find("small"):
                    data["name"] = theme_name_tag.text.strip()
                if theme_share_tag := tag.find("div"):
                    data["share"] = extract_float(theme_share_tag.text.strip())
                if data:
                    self._metadata["event"]["themes"].append(data)
            # players and winner
            players_tag = find_next_sibling_tag(info_tag)
            if not players_tag:
                return
            self._metadata["event"]["players"] = extract_int(players_tag.text.strip())
            winner_tag = find_next_sibling_tag(players_tag)
            if not winner_tag:
                return
            self._metadata["event"]["winner"] = winner_tag.text.strip().removeprefix(
                "Winner").strip()

    @override
    def _parse_input_for_decks_data(self) -> None:
        self._deck_urls = find_links(
            self._soup, href=lambda h: h and "/decks/" in h and "playingmtg.com/" not in h)


# TODO: tags-based decklists scraping (only if PlayingMTG articles start to be regularly featured
#  in YT videos)
@HybridContainerScraper.registered
class PlayingMtgArticleScraper(HybridContainerScraper):
    """Scraper of PlayingMTG article page.
    """
    SELENIUM_PARAMS = {  # override
        "xpaths": [
            Xpath(
                text='//div[@class="RootOfEmbeddedDeck"]//a[contains(@href, "/decks/")]',
                wait_for_all=True,
            ),
        ],
    }
    THROTTLING = _THROTTLING  # override
    CONTAINER_NAME = "PlayingMTG article"  # override
    CONTAINER_SCRAPER_TYPES = PlayingMtgTournamentScraper,  # override
    CONTAINER_URL_PREFIX = URL_PREFIX  # override
    EXAMPLE_URLS = (
        "https://playingmtg.com/pro-tour-aetherdrift-top-8-standard-decklists/",
    )

    @classmethod
    @override
    def is_valid_url(cls, url: str) -> bool:
        tokens = (
            "decks", "tournaments", "wp-content", "news", "mtg-arena", "spoilers", "commander",
            "standard", "modern", "pioneer", "collection", "prices", "products", "schedule",
            "builder", "meta", "tier-list"
        )
        if any(f"playingmtg.com/{t}" in url.lower() for t in tokens):
            return False
        return is_more_than_root_path(url, "playingmtg.com")

    @override
    def _parse_input_for_decks_data(self) -> None:
        deck_tags = [*self._soup.find_all("div", class_="RootOfEmbeddedDeck")]
        a_tags = [t.find("a", href=lambda h: h and "/decks/" in h) for t in deck_tags]
        deck_urls = [prepend_url(t["href"], URL_PREFIX) for t in a_tags if t]

        article_tag = self._soup.find("article")
        if not article_tag:
            err = ScrapingError("Article tag not found", scraper=type(self), url=self.url)
            _log.warning(f"Scraping failed with: {err!r}")
            self._deck_urls = deck_urls
            return

        p_deck_urls, self._container_urls = self._find_links_in_tags(*article_tag.find_all("p"))
        self._deck_urls = deck_urls + [l for l in p_deck_urls if l not in deck_urls]
