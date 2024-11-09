"""

    mtg.deck.scrapers.aetherhub.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape AetherHub decklists.

    @author: z33k

"""
import logging
from datetime import datetime

from selenium.common.exceptions import TimeoutException

from mtg.deck import Archetype, Mode, ParsingState
from mtg.deck.scrapers import ContainerScraper, DeckScraper
from mtg.utils import extract_float, extract_int, from_iterable
from mtg.utils.scrape import ScrapingError, get_dynamic_soup_by_xpath, getsoup, strip_url_params

_log = logging.getLogger(__name__)


# TODO: meta-decks
@DeckScraper.registered
class AetherhubScraper(DeckScraper):
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
        if url.endswith("/Gallery"):
            url = url.removesuffix("/Gallery")
        elif url.endswith("/Gallery/"):
            url = url.removesuffix("/Gallery/")
        return url

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
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

        # meta (only in meta-decklists)
        if meta_tag := self._soup.find("h5", class_="text-center"):
            try:
                text = meta_tag.text.strip()
                share_part, change_part = text.split("of meta")
                self._metadata["meta"] = {}
                self._metadata["meta"]["share"] = extract_float(share_part)
                self._metadata["meta"]["share_change"] = extract_float(change_part)

                count_tag = self._soup.select("h4.text-center.pt-2")[0]
                count_text, _ = count_tag.text.strip().split("decks,")
                self._metadata["meta"]["count"] = extract_int(count_text)
            except (IndexError, ValueError):
                _log.warning(f"No metagame data available for {self.url!r}")

    def _parse_deck(self) -> None:  # override
        deck_tags = self._soup.find_all("div", class_="row")
        deck_tag = from_iterable(
            deck_tags, lambda t: t.text.strip().startswith(("Main", "Commander", "Companion")))
        for tag in deck_tag.descendants:
            if tag.name == "h5":
                if "Side" in tag.text:
                    self._shift_to_sideboard()
                elif "Commander" in tag.text:
                    self._shift_to_commander()
                elif "Companion" in tag.text:
                    self._shift_to_companion()
                elif self._state is not ParsingState.MAINDECK:
                    self._shift_to_maindeck()
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
                    if self._state is ParsingState.MAINDECK:
                        self._maindeck += cards
                    elif self._state is ParsingState.SIDEBOARD:
                        self._sideboard += cards
                    elif self._state is ParsingState.COMMANDER:
                        self._set_commander(cards[0])
                    elif self._state is ParsingState.COMPANION:
                        self._companion = cards[0]


@ContainerScraper.registered
class AetherhubUserScraper(ContainerScraper):
    """Scraper of Aetherhub user page.
    """
    CONTAINER_NAME = "Aetherhub user"  # override
    URL_TEMPLATE = "https://aetherhub.com{}"
    _DECK_SCRAPER = AetherhubScraper  # override
    _XPATH = '//table[@id="metaHubTable"]'
    _CONSENT_XPATH = '//button[@class="ncmp__btn" and contains(text(), "Accept")]'

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
            self._soup, _, _ = get_dynamic_soup_by_xpath(
                self.url, self._XPATH, consent_xpath=self._CONSENT_XPATH,
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
