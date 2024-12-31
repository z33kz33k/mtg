"""

    mtg.deck.scrapers.magicville.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MagicVille decklists.

    @author: z33k

"""
import logging

from mtg.deck.scrapers import ContainerScraper, UrlDeckScraper
from mtg.utils import get_date_from_french_ago_text
from mtg.utils.scrape import ScrapingError, getsoup

_log = logging.getLogger(__name__)


@UrlDeckScraper.registered
class MagicVilleScraper(UrlDeckScraper):
    """Scraper of MagicVille decklist page.
    """
    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        url = url.lower()
        return "magic-ville.com/" in url and "decks/showdeck" in url

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
        # name
        name, name_tag = None, None
        name_tags = [
            tag for tag in self._soup.find_all("div", class_="title16")
            if tag.text.strip() != fmt_text]
        if name_tags:
            name_tag = name_tags[0]
            name = name_tag.text.strip()
            if name.startswith("#"):
                rank, name = name.split(maxsplit=1)
                self._metadata.setdefault("event", {})["rank"] = rank.lstrip("#")
        # author
        author = ""
        if author_tag := self._soup.find("a", href=lambda h: h and "/register/perso?user=" in h):
            _, author = author_tag["href"].split("/register/perso?user=", maxsplit=1)
        elif name_tag:
            if author_tag := name_tag.find("span", class_="G14"):
                author = author_tag.text.strip()
        if author:
            self._metadata["author"] = author
        if name:
            self._metadata["name"] = name.removesuffix(f" {author}")
        # event
        if event_div := self._soup.find("div", class_="W12"):
            if evnet_a := event_div.find("a", href=lambda h: h and "decklists?event" in h):
                self._metadata.setdefault("event", {})["name"] = evnet_a.text.strip()
        # date
        if date_tag := self._soup.find("div", class_="W10"):
            date_text = date_tag.text.strip().removeprefix("modifié ").removeprefix("il y a ")
            _, suffix = date_text.rsplit("par ", maxsplit=1)
            date_text = date_text.removesuffix(suffix).strip()
            if date := get_date_from_french_ago_text(date_text):
                self._metadata["date"] = date

    def _parse_decklist(self) -> None:  # override
        main_tag = self._soup.find("div", id="aff_graphique")
        for tag in main_tag.descendants:
            if (tag.name in ("div", "span")
                    and tag.attrs.get("class") == ["O16"]
                    and tag.text == "SIDEBOARD"):
                if not self._state.is_sideboard:
                    self._state.shift_to_sideboard()
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
                if self._state.is_sideboard:
                    self._sideboard += playset
                else:
                    self._maindeck += playset


@ContainerScraper.registered
class MagicVilleEventScraper(ContainerScraper):
    """Scraper of MagicVille event page.
    """
    CONTAINER_NAME = "MagicVille event"  # override
    DECK_URL_TEMPLATE = "https://www.magic-ville.com/fr/decks/{}"
    _DECK_SCRAPER = MagicVilleScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return all(t in url.lower() for t in ("magic-ville.com/", "decks/decklists?", "event="))

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning("Event data not available")
            return []

        deck_tags = self._soup.find_all("a", href=lambda h: h and "showdeck?ref=" in h)
        return [self.DECK_URL_TEMPLATE.format(deck_tag.attrs["href"]) for deck_tag in deck_tags]


@ContainerScraper.registered
class MagicVilleUserScraper(ContainerScraper):
    """Scraper of MagicVille user page.
    """
    CONTAINER_NAME = "MagicVille user"  # override
    DECK_URL_TEMPLATE = "https://www.magic-ville.com/fr/{}"
    _DECK_SCRAPER = MagicVilleScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return all(t in url.lower() for t in ("magic-ville.com/", "register/perso?", "user="))

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning("User data not available")
            return []

        deck_tags = self._soup.find_all("a", href=lambda h: h and "/decks/showdeck.php?ref=" in h)
        return [
            self.DECK_URL_TEMPLATE.format(deck_tag.attrs["href"].removeprefix("../"))
            for deck_tag in deck_tags]

