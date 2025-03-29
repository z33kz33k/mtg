"""

    mtg.deck.scrapers.playingmtg.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape PlayingMTG decklists.

    @author: z33k

"""
import logging
from typing import override

import dateutil.parser
from bs4 import Tag
from selenium.common.exceptions import TimeoutException

from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper
from mtg.scryfall import Card
from mtg.utils import extract_float, extract_int
from mtg.utils.scrape import ScrapingError, get_links, strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup

_log = logging.getLogger(__name__)
URL_PREFIX = "https://playingmtg.com"


@DeckScraper.registered
class PlayingMtgDeckScraper(DeckScraper):
    """Scraper of PlayingMTG decklist page.
    """
    # XPATH = '//div[text()="Main Board"]'
    XPATH = '//a[contains(@href, "/playingmtg.com/cards/")]'

    @staticmethod
    @override
    def is_deck_url(url: str) -> bool:
        return "playingmtg.com/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        return strip_url_query(url)

    @override
    def _pre_parse(self) -> None:
        try:
            self._soup, _, _ = get_dynamic_soup(self.url, self.XPATH, wait_for_all=True)
        except TimeoutException:
            self._soup = None
        if not self._soup:
            raise ScrapingError("Page not available")

    @override
    def _parse_metadata(self) -> None:
        if title_tag := self._soup.select_one("h1.page-title"):
            self._metadata["name"] = title_tag.attrs["title"]
        # TODO
        # if fmt_tag := self._soup.find("div", {"class": ["sc-eyqwws", "jUMbtV"], "title": ""}):
        #     self._update_fmt(fmt_tag.find("a").text.strip().removeprefix("Format: "))
        # info_tags = [*self._soup.select_one("ul.entry-meta").find_all("li")]
        # if len(info_tags) == 2:
        #     author_tag, date_tag = info_tags
        #     theme_tag = None
        # elif len(info_tags) == 3:
        #     theme_tag, author_tag, date_tag = info_tags
        # else:
        #     theme_tag, author_tag, date_tag = None, None, None
        # if theme_tag:
        #     self._update_archetype_or_theme(theme_tag.text.strip())
        # if author_tag:
        #     self._metadata["author"] = author_tag.text.strip()
        # if date_tag:
        #     self._metadata["date"] = dateutil.parser.parse(date_tag.text.strip()).date()
        # if desc_tag := self._soup.select_one("div.sc-jJZtqq.hdJLbY"):
        #     self._metadata["description"] = desc_tag.text.strip().removeprefix("Deck Description")

    @classmethod
    def _parse_card(cls, card_tag: Tag) -> list[Card]:
        data_tags = [
            t for t in card_tag.find_all("div") if t.has_attr("title") and "$" not in t.text]
        qty, name = None, None
        for tag in data_tags:
            if all(ch.isdigit() for ch in tag.text):
                qty = int(tag.text)
            else:
                name = tag.text.strip()
        return cls.get_playset(cls.find_card(name), qty)

    @override
    def _parse_decklist(self) -> None:
        maindeck_hook = self._soup.find("div", string=lambda s: s and s == "Main Board")
        maindeck_tag = maindeck_hook.parent
        card_tags = [a_tag.parent for a_tag in maindeck_tag.find_all(
            "a", href=lambda h: h and "playingmtg.com/" in h)]
        for card_tag in card_tags:
            self._maindeck += self._parse_card(card_tag)

        if sideboard_hook := self._soup.find("div", string=lambda s: s and s == "Side Board"):
            sideboard_tag = sideboard_hook.parent
            card_tags = [a_tag.parent for a_tag in sideboard_tag.find_all(
                "a", href=lambda h: h and "playingmtg.com/" in h)]
            for card_tag in card_tags:
                self._sideboard += self._parse_card(card_tag)


# FIXME
@DeckUrlsContainerScraper.registered
class PlayingMtgTournamentScraper(DeckUrlsContainerScraper):
    """Scraper of PlayingMTG tournament page.
    """
    CONTAINER_NAME = "PlayingMTG tournament"  # override
    XPATH = '//a[@class="sc-eTNaoj aJnCl"]'  # override
    DECK_SCRAPERS = PlayingMtgDeckScraper,  # override
    DECK_URL_PREFIX = URL_PREFIX  # override

    @staticmethod
    @override
    def is_container_url(url: str) -> bool:
        return "playingmtg.com/tournaments/" in url.lower()

    def _parse_metadata(self) -> None:
        if info_tag := self._soup.select_one("div.sc-cCUCJR.hDZsaq"):
            self._metadata["event"] = {}
            if date_tag := info_tag.select_one("div.sc-gOJDFQ.cySNTC"):
                date_text = date_tag.text.strip().removeprefix("Event Date").strip()
                self._metadata["event"]["date"] = dateutil.parser.parse(date_text).date()
            if name_tag := info_tag.select_one("a.sc-fhxlfq.cQfNNM"):
                self._metadata["event"]["name"] = name_tag.text.strip()
            if fmt_tag := info_tag.select_one("div.sc-cwxWdN.cOVKUM"):
                self._metadata["event"]["format"] = fmt_tag.text.strip().lower()
            if set_tag := info_tag.select_one("div.sc-fbaEzm.hIQPkW"):
                self._metadata["event"]["latest_set"] = set_tag.text.strip().strip().removeprefix(
                    "Latest set: ").strip().lower()
            if theme_tags := [*info_tag.select("div.sc-euTIOJ.knuiml")]:
                self._metadata["event"]["themes"] = []
                for tag in theme_tags:
                    data = {}
                    if theme_name_tag := tag.find("small"):
                        data["name"] = theme_name_tag.text.strip()
                    if theme_share_tag := tag.find("div"):
                        data["share"] = extract_float(theme_share_tag.text.strip())
                    if data:
                        self._metadata["event"]["themes"].append(data)
            if players_tag := info_tag.select_one("div.sc-gVbcWm.ecZxVc"):
                self._metadata["event"]["players"] = extract_int(players_tag.text.strip())
            if winner_tag := info_tag.select_one("div.sc-eUmdFK.cLSdEr"):
                self._metadata["event"]["winner"] = winner_tag.text.strip().removeprefix(
                    "Winner").strip()

    @override
    def _collect(self) -> list[str]:
        self._parse_metadata()
        return get_links(self._soup, css_selector="a.sc-eTNaoj.aJnCl")
