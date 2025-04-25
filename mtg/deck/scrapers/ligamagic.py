"""

    mtg.deck.scrapers.ligamagic.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape LigaMagic decklists.

    Note: experimental (requires use of scraping APIs to bypass CloudFlare).

    @author: z33k

"""
import logging
from collections import defaultdict
from typing import override

import dateutil.parser
from bs4 import BeautifulSoup, Tag

from mtg import Json
from mtg import SECRETS
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.scryfall import Card
from mtg.utils import extract_int
from mtg.utils.scrape import ScrapingError, getsoup, url_decode

_log = logging.getLogger(__name__)
_API_KEY = SECRETS["zenrows"]["api_key"]
_API_URL = "https://api.zenrows.com/v1/"
REQUEST_TIMEOUT = 300


def _get_soup_with_zenrows(url: str, css_selector: str) -> BeautifulSoup | None:
    params = {
        'url': url,
        'apikey': _API_KEY,
        'js_render': 'true',
        'wait_for': css_selector,
        'premium_proxy': 'true',
        'proxy_country': 'br',
    }
    return getsoup(_API_URL, params=params, request_timeout=REQUEST_TIMEOUT)


# TODO: uncomment when ready
# @DeckScraper.registered
class LigaMagicDeckScraper(DeckScraper):
    """Scraper of LigaMagic decklist page.
    """
    _CSS_SELECTOR = "div#deck-view"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._tags = defaultdict(list)

    # TODO: take care of LigaMagic's own: `lig.ae` shortener URLs
    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return all(t in url.lower() for t in ("ligamagic.com.br", "/deck", "&id="))

    @override
    def _pre_parse(self) -> None:
        self._soup = _get_soup_with_zenrows(self.url, self._CSS_SELECTOR)
        if not self._soup:
            raise ScrapingError("Page not available", scraper=type(self), url=self.url)
        main_tag = self._soup.select_one(self._CSS_SELECTOR)
        state = "maindeck"
        stoppers = "Branco", "Azul", "Preto", "Vermelho", "Verde", "Multi Colorida"  # color names
        potential_stoppers = "Artefato", "Terrenos"
        for tag in main_tag.find_all("div", class_="deck-line"):
            if type_tag := tag.find("div", class_=lambda c: c and "deck-type" in c):
                state = type_tag.text.strip()
                # stop the moment we're out of the basic deck view and in the color one
                if any(s in state for s in stoppers):
                    break
                if any(ps in state for ps in potential_stoppers) and state in self._tags:
                    break
            elif line_tag := tag.find("div", class_="deck-box-left"):
                self._tags[state].append(line_tag)

    @override
    def _parse_metadata(self) -> None:
        header_tag = self._soup.find("div", id="deck-header")
        self._metadata["name"] = header_tag.find(
            "div", class_="title").find("span", class_=lambda c: not c).text.strip()
        fmt_text = header_tag.find("div", class_="format").text.strip()
        if " - " in fmt_text:
            fmt_text, theme_text = fmt_text.split(" - ", maxsplit=1)
            self._update_archetype_or_theme(theme_text)
        self._update_fmt(fmt_text)
        if author_tag := header_tag.find("div", class_="createdby"):
            self._metadata["author"] = author_tag.find("a").text.strip()
        if event_tag := header_tag.find("div", class_="event"):
            self._metadata["event"] = event_tag.find("a").text.strip()
        if right_block_tag := header_tag.find("div", class_="rightblock"):
            if date_tag := right_block_tag.find("div", class_="date"):
                self._metadata["date"] = dateutil.parser.parse(date_tag.text.strip()).date()

    @classmethod
    def _parse_tag_list(cls, tag_list: list[Tag]) -> list[Card]:
        cards = []
        for tag in tag_list:
            qty = tag.find("div", class_="deck-qty").text.strip()
            quantity = extract_int(qty)
            name = tag.find("div", class_="deck-card").find("a").attrs["href"].removeprefix(
                "./?view=cards/card&card=")
            card = cls.find_card(url_decode(name))
            cards += cls.get_playset(card, quantity)
        return cards

    @override
    def _parse_decklist(self) -> None:
        for state in self._tags:
            if "Comandante" in state:
                for card in self._parse_tag_list(self._tags[state]):
                    self._set_commander(card)
            elif "Companheiro" in state:
                self._companion = self._parse_tag_list(self._tags[state])[0]
            elif "Sideboard" in state:
                self._sideboard += self._parse_tag_list(self._tags[state])
            else:
                self._maindeck += self._parse_tag_list(self._tags[state])


# TODO: uncomment when ready
# @ContainerScraper.registered
class LigaMagicEventScraper(DeckUrlsContainerScraper):
    """Scraper of LigaMagic event page.
    """
    CONTAINER_NAME = "LigaMagic event"  # override
    DECK_SCRAPERS = LigaMagicDeckScraper,  # override
    DECK_URL_PREFIX = "https://www.ligamagic.com.br"  # override
    _CSS_SELECTOR = "div.evnt-dks"

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return all(t in url.lower() for t in ("ligamagic.com.br", "/evento", "&id="))

    @override
    def _pre_parse(self) -> None:
        self._soup = _get_soup_with_zenrows(self.url, self._CSS_SELECTOR)
        if not self._soup:
            raise ScrapingError(self._error_msg, scraper=type(self), url=self.url)

    @override
    def _collect(self) -> list[str]:
        deck_tags = [tag.find("a") for tag in self._soup.find_all("div", class_="deckname")]
        if not deck_tags:
            raise ScrapingError("Deck tags not found", scraper=type(self), url=self.url)
        return [tag.attrs["href"].removeprefix(".") for tag in deck_tags]
