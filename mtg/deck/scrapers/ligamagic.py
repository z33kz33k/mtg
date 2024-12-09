"""

    mtg.deck.scrapers.ligamagic.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape LigaMagic decklists.

    Note: experimental (requires use of scraping APIs to bypass CloudFlare).

    @author: z33k

"""
import logging
from collections import defaultdict

import dateutil.parser
from bs4 import Tag

from mtg import Json
from mtg import SECRETS
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import Card
from mtg.utils import extract_int
from mtg.utils.scrape import ScrapingError, getsoup, url_decode

_log = logging.getLogger(__name__)
_API_KEY = SECRETS["zenrows"]["api_key"]
_API_URL = "https://api.zenrows.com/v1/"


@DeckScraper.registered
class LigaMagicScraper(DeckScraper):
    """Scraper of LigaMagic decklist page.
    """
    REQUEST_TIMEOUT = 300

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._tags = defaultdict(list)
        self._params = {
            'url': self.url,
            'apikey': _API_KEY,
            'js_render': 'true',
            'wait_for': 'div#deck-view',
            'premium_proxy': 'true',
            'proxy_country': 'br',
        }

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return all(t in url.lower() for t in ("ligamagic.com.br", "/deck", "&id="))

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(_API_URL, params=self._params, request_timeout=self.REQUEST_TIMEOUT)
        if not self._soup:
            raise ScrapingError("Page not available")
        main_tag = self._soup.find("div", id="deck-view")
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

    def _parse_metadata(self) -> None:  # override
        header_tag = self._soup.find("div", id="deck-header")
        self._metadata["name"] = header_tag.find("div", class_="title").find("span").text.strip()
        fmt_text = header_tag.find("div", class_="format").text.strip()
        if " - " in fmt_text:
            fmt_text, theme_text = fmt_text.split(" - ", maxsplit=1)
            self._update_custom_theme("ligamagic", theme_text)
        self._update_fmt(fmt_text)
        if author_tag := header_tag.find("div", class_="createdby"):
            self._metadata["author"] = author_tag.find("a").text.strip()
        if event_tag := header_tag.find("div", class_="event"):
            self._metadata["event"] = event_tag.find("a").text.strip()
        if right_block_tag := header_tag.find("div", class_="rightblock"):
            if date_tag := right_block_tag.find("div", class_="date"):
                self._metadata["date"] = dateutil.parser.parse(date_tag.text.strip())

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

    def _parse_deck(self) -> None:  # override
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
