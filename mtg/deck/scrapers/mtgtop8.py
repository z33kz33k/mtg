"""

    mtg.deck.scrapers.mtgtop8.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGTop8 decklists.

    @author: z33k

"""
import contextlib
import logging
from datetime import datetime

from mtg.deck.scrapers import DeckUrlsContainerScraper, UrlBasedDeckScraper
from mtg.utils import extract_int
from mtg.utils.scrape import ScrapingError
from mtg.utils.scrape import getsoup

_log = logging.getLogger(__name__)


EVENT_RANKS = "minor", "regular", "major"  # indicated by number of stars (1, 2, 3)


# TODO: scrape metagame
@UrlBasedDeckScraper.registered
class MtgTop8DeckScraper(UrlBasedDeckScraper):
    """Scraper of MTGTop8 decklist page.
    """
    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgtop8.com/event?e=" in url.lower() and "&d=" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return url.removesuffix("/").replace("&switch=visual", "").replace(
            "&switch=text", "") + "&switch=text"

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        if _ := self._soup.find("div", string="No event could be found."):
            raise ScrapingError("No event could be found")

    def _parse_metadata(self) -> None:  # override
        event_tag, name_tag = [tag for tag in self._soup.find_all("div", class_="event_title")
                               if tag.find("a", class_="arrow") is None]
        self._metadata["event"] = {}
        self._metadata["event"]["name"] = event_tag.text.strip().removesuffix(" Event")
        place, name = name_tag.text.strip().split(maxsplit=1)
        self._metadata["event"]["place"] = place
        if "-" in name:
            name, author = name.split("-", maxsplit=1)
            self._metadata["name"] = name.strip()
            self._metadata["author"] = author.strip()
        else:
            self._metadata["name"] = name.strip()
        fmt_tag = self._soup.find("div", class_="meta_arch")
        self._update_fmt(fmt_tag.text.strip().lower())
        with contextlib.suppress(IndexError):
            self._metadata["event"]["rank"] = EVENT_RANKS[len(fmt_tag.find_all("img")) - 1]
        players_date_text = self._soup.find('div', style='margin-bottom:5px;').text.strip()
        if "-" in players_date_text:
            players_text, date_text = players_date_text.split("-", maxsplit=1)
            self._metadata["event"]["players"] = extract_int(players_text)
        else:
            date_text = players_date_text
        self._metadata["event"]["date"] = datetime.strptime(date_text.strip(), '%d/%m/%y').date()
        if source_tag := self._soup.find("a", target="_blank"):
            self._metadata["event"]["source"] = source_tag.text.strip()

    def _parse_decklist(self) -> None:  # override
        deck_tag = self._soup.find("div", style="display:flex;align-content:stretch;")
        cards, commander_on = self._maindeck, False
        for block_tag in deck_tag:
            for sub_tag in block_tag:
                if sub_tag.name == "div" and sub_tag.attrs.get("class") == ['O14']:
                    if sub_tag.text == "SIDEBOARD":
                        cards = self._sideboard
                        commander_on = False
                    elif sub_tag.text == "COMMANDER":
                        commander_on = True
                    else:
                        commander_on = False
                if "deck_line" in sub_tag.attrs["class"]:
                    quantity, name = sub_tag.text.split(maxsplit=1)
                    card = self.find_card(name.strip())
                    if commander_on:
                        self._set_commander(card)
                    else:
                        quantity = extract_int(quantity)
                        cards += self.get_playset(card, quantity)


@DeckUrlsContainerScraper.registered
class MtgTop8EventScraper(DeckUrlsContainerScraper):
    """Scraper of MTGTop8 event page.
    """
    CONTAINER_NAME = "MTGTop8 event"  # override
    DECK_URL_TEMPLATE = "https://www.mtgtop8.com/event{}"
    _DECK_SCRAPER = MtgTop8DeckScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "mtgtop8.com/event?e=" in url.lower() and "&d=" not in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return MtgTop8DeckScraper.sanitize_url(url)

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning(self._error_msg)
            return []

        a_tags = [tag for tag in self._soup.find_all(
            "a", href=lambda h: h and "e=" in h and "&d="in h) if not tag.find("img")
                  and tag.text not in ('Switch to Visual', '→')]
        deck_urls = {}
        for a_tag in a_tags:
            deck_urls[a_tag.text] = a_tag.attrs["href"]
        return [self.DECK_URL_TEMPLATE.format(url) for url in deck_urls.values()]
