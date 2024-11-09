"""

    mtg.deck.scrapers.magicville.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MagicVille decklists.

    @author: z33k

"""
import logging

from mtg.deck import ParsingState
from mtg.deck.scrapers import DeckScraper
from mtg.utils import get_date_from_french_ago_text
from mtg.utils.scrape import ScrapingError, getsoup

_log = logging.getLogger(__name__)


@DeckScraper.registered
class MagicVilleScraper(DeckScraper):
    """Scraper of MagicVille decklist page.
    """
    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        url = url.lower()
        return "magic-ville.com/" in url and "decks/showdeck?" in url

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return f"{url}&decklanglocal=eng"

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup or self._soup.text == "Ce deck n'existe pas.":
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
        fmt_tag = self._soup.find("div", class_="lil_menu", string=lambda s: s and "Appr" in s)
        fmt_text = fmt_tag.find("a")["href"]
        _, fmt_text = fmt_text.split("&f=", maxsplit=1)
        if "&file=" in fmt_text:
            fmt_text, _ = fmt_text.split("&file=", maxsplit=1)
        self._update_fmt(fmt_text)
        name_tag = self._soup.find("div", class_="title16")
        self._metadata["name"] = name_tag.text.strip()
        if author_tag := self._soup.find("a", href=lambda h: h and "/register/perso?user=" in h):
            _, author = author_tag["href"].split("/register/perso?user=", maxsplit=1)
            self._metadata["author"] = author
        elif author_tag := name_tag.find("span", class_="G14"):
            author = author_tag.text.strip()
            self._metadata["author"] = author
        if event_div := self._soup.find("div", class_="W12"):
            if evnet_a := event_div.find("a", href=lambda h: h and "decklists?event" in h):
                self._metadata["event"] = evnet_a.text.strip()
        if date_tag := self._soup.find("div", class_="W10"):
            date_text = date_tag.text.strip().removeprefix("modifié ").removeprefix("il y a ")
            _, suffix = date_text.rsplit("par ", maxsplit=1)
            date_text = date_text.removesuffix(suffix).strip()
            if date := get_date_from_french_ago_text(date_text):
                self._metadata["date"] = date

    def _parse_deck(self) -> None:  # override
        main_tag = self._soup.find("div", id="aff_graphique")
        for tag in main_tag.descendants:
            if (tag.name in ("div", "span")
                    and tag.attrs.get("class") == ["O16"]
                    and tag.text == "SIDEBOARD"):
                    self._state = ParsingState.SIDEBOARD
            elif (tag.name == "div"
                  and tag.attrs.get("class") == ["S14"]
                  and len([*tag.find_all("a")]) == 1):
                a_tag = tag.find("a")
                if "carte?ref=" in a_tag.attrs["href"]:
                    card = self.find_card(a_tag.text.strip())
                    self._set_commander(card)
            elif (tag.name == "div"
                  and tag.attrs.get("class") == ["S12"]):
                if qty_tag := tag.find("div"):
                    qty = int(qty_tag.text)
                else:
                    qty = 1
                name = tag.find("a").text.strip()
                playset = self.get_playset(self.find_card(name.strip()), qty)
                if self._state == ParsingState.SIDEBOARD:
                    self._sideboard += playset
                else:
                    self._maindeck += playset
