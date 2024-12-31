"""

    mtg.deck.scrapers.aetherhub.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape AetherHub decklists.

    @author: z33k

"""
import logging
from datetime import datetime

import dateutil.parser
from selenium.common.exceptions import TimeoutException

from mtg.deck import Archetype, Mode
from mtg.deck.scrapers import ContainerScraper, UrlDeckScraper
from mtg.utils import extract_float, extract_int, from_iterable
from mtg.utils.scrape import ScrapingError, get_dynamic_soup, getsoup, strip_url_params

_log = logging.getLogger(__name__)


# TODO: scrape the meta
@UrlDeckScraper.registered
class AetherhubScraper(UrlDeckScraper):
    """Scraper of Aetherhub decklist page.

    Note:
        Companions are part of a sideboard list and aren't listed separately.
    """
    FORMATS = {
        "Arena Standard": ("standard", Mode.BO1),
        "Standard": ("standard", Mode.BO3),
        "Alchemy": ("alchemy", Mode.BO1),
        "Traditional Alchemy": ("alchemy", Mode.BO3),
        "Historic": ("historic", Mode.BO1),
        "Traditional Historic": ("historic", Mode.BO3),
        "Explorer": ("explorer", Mode.BO1),
        "Traditional Explorer": ("explorer", Mode.BO3),
        "Timeless": ("timeless", Mode.BO1),
        "Traditional Timeless": ("timeless", Mode.BO3),
        "Brawl": ("standardbrawl", Mode.BO3),
        "Historic Brawl": ("brawl", Mode.BO3),
        "Pioneer": ("pioneer", Mode.BO3),
        "Modern": ("modern", Mode.BO3),
        "Legacy": ("legacy", Mode.BO3),
        "Vintage": ("vintage", Mode.BO3),
        "Commander": ("commander", Mode.BO3),
        "Oathbreaker": ("oathbreaker", Mode.BO3),
    }

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        url = url.lower()
        return ("aetherhub.com/" in url and "/deck/" in url and "/mydecks/" not in url
                and "/builder" not in url)

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url)
        if "/gallery/" in url.lower():
            url = url.replace("/Gallery/", "/Public/").replace("/gallery/", "/public/")
        elif url.lower().endswith("/gallery"):
            url = url.removesuffix("/Gallery").removesuffix("/gallery")
        return url.removesuffix("/")

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup or "404 Page Not Found" in self._soup.text:
            raise ScrapingError("Page not available")

    def _parse_metadata(self) -> None:  # override
        # name and format
        if title_tag := self._soup.find("h2", class_="text-header-gold"):
            fmt_part, name_part = title_tag.text.strip().split("-", maxsplit=1)
            fmt_part = fmt_part.strip()
            if fmt_pair := self.FORMATS.get(fmt_part):
                fmt, mode = fmt_pair
                self._update_fmt(fmt)
                self._metadata["mode"] = mode.value
            self._metadata["name"] = name_part.strip()

        # author (only in user-submitted decklists)
        if author_tag := self._soup.find('a', href=lambda href: href and "/User/" in href):
            self._metadata["author"] = author_tag.text

        # date and other (only in user-submitted decklists)
        if date_tags := self._soup.select(
            "div.col-xs-7.col-sm-7.col-md-7.col-lg-7.pl-0.pr-0.text-left"):
            date_tag = date_tags[0]
            date_lines = [l.strip() for l in date_tag.text.strip().splitlines() if l]
            date_text = date_lines[0].removeprefix("Last Updated: ").strip()
            self._metadata["date"] = datetime.strptime(date_text, "%d %b %Y").date()
            self._metadata["views"] = int(date_lines[2])
            self._metadata["exports"] = int(date_lines[3])
            self._metadata["comments"] = int(date_lines[4])

        # archetype
        if archetype_tag := self._soup.find("div", class_="archetype-tag"):
            archetype = archetype_tag.text.strip().lower()
            if archetype in {a.value for a in Archetype}:
                self._metadata["archetype"] = archetype

        # meta (only in meta decklists)
        if meta_tag := self._soup.find("h4", class_="text-center"):
            _, text = meta_tag.text.strip().split(" - ")
            count_text, share_text = text.strip().split(", ")
            self._metadata["meta"] = {}
            self._metadata["meta"]["count"] = extract_int(count_text)
            self._metadata["meta"]["share"] = extract_float(share_text)

        # event (only in event decklists)
        if event_tag := self._soup.find("h5", class_="text-center"):
            text = event_tag.text.strip()
            if "\nby " in text and "/" in text:
                self._metadata["event"] = {}
                rank, *rest = event_tag.text.strip().split(maxsplit=1)
                if any(rank.endswith(t) for t in ("st", "nd", "rd", "th")):
                    self._metadata["event"]["rank"] = rank
                    rest = " ".join(rest)
                else:
                    rest = rank + " " + " ".join(rest)
                *rest, author = rest.rsplit("\nby ", maxsplit=1)
                self._metadata["event"]["player"] = self._metadata["author"] = author
                rest = " ".join(rest)
                *rest, date = rest.rsplit(maxsplit=1)
                if "/" in date:
                    self._metadata["event"]["date"] = dateutil.parser.parse(date).date()
                else:
                    rest = date + " " + " ".join(rest)
                rest = " ".join(rest)
                self._metadata["event"]["name"] = rest

    def _parse_decklist(self) -> None:  # override
        deck_tags = self._soup.find_all("div", class_="row")
        deck_tag = from_iterable(
            deck_tags, lambda t: t.text.strip().startswith(("Main", "Commander", "Companion")))

        if deck_tag is None:
            raise ScrapingError("Deck tag not found")

        for tag in deck_tag.descendants:
            if tag.name == "h5":
                if "Side" in tag.text:
                    self._state.shift_to_sideboard()
                elif "Commander" in tag.text:
                    self._state.shift_to_commander()
                elif "Companion" in tag.text:
                    self._state.shift_to_companion()
                elif not self._state.is_maindeck:
                    self._state.shift_to_maindeck()
            elif tag.name == "tr":
                td_tags = tag.find_all("td")
                if td_tags:
                    td_tag = td_tags[0]
                    lines = [l.strip() for l in td_tag.text.split("\n") if l.strip()]
                    if len(lines) < 2:
                        continue  # not a <td> card tag
                    qty_text, name = lines
                    quantity = int(qty_text)
                    card_tag = td_tag.find("a")
                    set_code = card_tag.attrs.get("data-card-set").lower()
                    collector = card_tag.attrs.get("data-card-number")
                    set_col = (set_code, collector) if set_code and collector else None
                    cards = self.get_playset(self.find_card(name, set_col), quantity)
                    if self._state.is_maindeck:
                        self._maindeck += cards
                    elif self._state.is_sideboard:
                        self._sideboard += cards
                    elif self._state.is_commander:
                        self._set_commander(cards[0])
                    elif self._state.is_companion:
                        self._companion = cards[0]


@ContainerScraper.registered
class AetherhubUserScraper(ContainerScraper):
    """Scraper of Aetherhub user page.
    """
    CONTAINER_NAME = "Aetherhub user"  # override
    URL_TEMPLATE = "https://aetherhub.com{}"
    _DECK_SCRAPER = AetherhubScraper  # override
    _XPATH = '//table[@id="metaHubTable"]'
    CONSENT_XPATH = '//button[@class="ncmp__btn" and contains(text(), "Accept")]'

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "aetherhub.com/user/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url)
        if not url.lower().endswith("/decks"):
            return f"{url}/decks"
        return url

    def _collect(self) -> list[str]:  # override
        try:
            self._soup, _, _ = get_dynamic_soup(
                self.url, self._XPATH, consent_xpath=self.CONSENT_XPATH,
                wait_for_consent_disappearance=False)
            if not self._soup:
                _log.warning("User data not available")
                return []
        except TimeoutException:
            _log.warning("User data not available")
            return []

        tbody = self._soup.find("tbody")
        return [self.URL_TEMPLATE.format(row.find("a")["href"])
                for row in tbody.find_all("tr")]


@ContainerScraper.registered
class AetherhubEventScraper(ContainerScraper):
    """Scraper of Aetherhub event page.
    """
    CONTAINER_NAME = "Aetherhub event"  # override
    URL_TEMPLATE = "https://aetherhub.com{}"
    _DECK_SCRAPER = AetherhubScraper  # override
    _XPATH = '//tr[@class="deckdata"]'

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "aetherhub.com/events/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_params(url)

    def _collect(self) -> list[str]:  # override
        try:
            self._soup, _, _ = get_dynamic_soup(
                self.url, self._XPATH, consent_xpath=AetherhubUserScraper.CONSENT_XPATH,
                wait_for_consent_disappearance=False)
            if not self._soup:
                _log.warning("Event data not available")
                return []
        except TimeoutException:
            _log.warning("Event data not available")
            return []

        rows = self._soup.find_all("tr", class_="deckdata")
        deck_tags = []
        for row in rows:
            _, deck_tag, *_ = row.find_all("td")
            deck_tags.append(deck_tag.find("a", href=lambda h: h and "/deck/" in h.lower()))
        deck_tags = [d for d in deck_tags if d is not None]
        return [self.URL_TEMPLATE.format(deck_tag["href"]) for deck_tag in deck_tags]
