"""

    mtg.deck.scrapers.untapped.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Untapped.gg decklists.

    @author: z33k

"""
import logging
from datetime import datetime

from selenium.common.exceptions import NoSuchElementException, TimeoutException

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser
from mtg.deck.scrapers import DeckUrlsContainerScraper, DeckScraper
from mtg.utils import extract_float, extract_int
from mtg.utils.scrape import ScrapingError
from mtg.utils.scrape import strip_url_query
from mtg.utils.scrape.dynamic import get_dynamic_soup

_log = logging.getLogger(__name__)
CONSENT_XPATH = '//button[contains(@class, "fc-button fc-cta-consent") and @aria-label="Consent"]'
CLIPBOARD_XPATH = "//span[text()='Copy to MTGA']"


@DeckScraper.registered
class UntappedProfileDeckScraper(DeckScraper):
    """Scraper of decklist page of Untapped.gg user's profile.
    """
    NO_GAMES_XPATH = ("//div[text()='No games have been played with this deck in the selected "
                       "time frame']")
    PRIVATE_XPATH = "//div[text()='This profile is private']"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._clipboard = ""

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtga.untapped.gg/profile/" in url.lower() and "/deck/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, self._clipboard = get_dynamic_soup(
                self.url, CLIPBOARD_XPATH, self.NO_GAMES_XPATH, self.PRIVATE_XPATH,
                consent_xpath=CONSENT_XPATH, clipboard_xpath=CLIPBOARD_XPATH)
        except NoSuchElementException:
            raise ScrapingError("Scraping failed due to absence of the looked for element")
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _parse_metadata(self) -> None:  # override
        name_tag = self._soup.select_one('span[class*="DeckListContainer__Title"]')
        strong_tag = name_tag.find("strong")
        self._metadata["name"] = strong_tag.text.strip()
        author_tag = self._soup.find("h1", string=lambda s: s and s.endswith("'s Profile"))
        self._metadata["author"] = author_tag.text.strip().removesuffix("'s Profile")

    def _build_deck(self) -> Deck:
        return ArenaParser(self._clipboard.splitlines(), metadata=self._metadata).parse(
            suppress_invalid_deck=False)

    def _parse_decklist(self) -> None:  # override
        pass


@DeckScraper.registered
class UntappedRegularDeckScraper(DeckScraper):
    """Scraper of a regular Untapped.gg decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._clipboard = ""

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtga.untapped.gg/decks/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_query(url)
        return url.replace("input/", "") if "/input/" in url else url

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, self._clipboard = get_dynamic_soup(
                self.url, CLIPBOARD_XPATH, consent_xpath=CONSENT_XPATH,
                clipboard_xpath=CLIPBOARD_XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _parse_metadata(self) -> None:  # override
        name_tag = self._soup.select("h1[class*='styles__H1']")[-1]
        name = name_tag.text.strip()
        if " (" in name:
            name, *_ = name.split(" (")
        self._metadata["name"] = name

    def _build_deck(self) -> Deck:  # override
        return ArenaParser(self._clipboard.splitlines(), metadata=self._metadata).parse(
            suppress_invalid_deck=False)

    def _parse_decklist(self) -> None:  # override
        pass


@DeckScraper.registered
class UntappedMetaDeckScraper(DeckScraper):
    """Scraper of Untapped meta-decks page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._clipboard = ""

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtga.untapped.gg/meta/decks/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _pre_parse(self) -> None:  # override
        try:
            self._soup, _, self._clipboard = get_dynamic_soup(
                self.url, CLIPBOARD_XPATH, consent_xpath=CONSENT_XPATH,
                clipboard_xpath=CLIPBOARD_XPATH)
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _parse_metadata(self) -> None:  # override
        name_tag = self._soup.select_one("h1[class*='layouts__MetaPageHeaderTitle']")
        if not name_tag:
            name_tag = self._soup.select_one("span[class*='DeckViewHeader__ArchetypeName']")
        if not name_tag:
            raise ScrapingError("Page data not available")
        name = name_tag.text.strip().removesuffix(" Deck")
        self._metadata["name"] = name
        fmt_tag = self._soup.find("div", id="filter-format")
        self._metadata["format"] = fmt_tag.text.strip().lower()
        if time_tag := self._soup.find("time"):
            self._metadata["date"] = datetime.strptime(
                time_tag.attrs["datetime"], "%Y-%m-%dT%H:%M:%S.%fZ").date()
        winrate, matches, avg_duration = self._soup.select("span[class*='LabledStat__Value']")
        self._metadata["meta"] = {}
        if winrate.text.strip():
            self._metadata["meta"]["winrate"] = extract_float(winrate.text.strip())
        if matches.text.strip():
            self._metadata["meta"]["matches"] = extract_int(matches.text.strip())
        if avg_duration.text.strip():
            self._metadata["meta"]["avg_minutes"] = extract_float(avg_duration.text.strip())
        time_range_tag = self._soup.select_one("div[class*='TimeRangeFilter__DateText']")
        self._metadata["meta"]["time_range_since"] = time_range_tag.text.removesuffix("Now")

    def _build_deck(self) -> Deck:  # override
        return ArenaParser(self._clipboard.splitlines(), metadata=self._metadata).parse(
            suppress_invalid_deck=False)

    def _parse_decklist(self) -> None:  # override
        pass


@DeckUrlsContainerScraper.registered
class UntappedProfileScraper(DeckUrlsContainerScraper):
    """Scraper of Untapped.gg user profile page.
    """
    THROTTLING = DeckUrlsContainerScraper.THROTTLING * 1.4
    CONTAINER_NAME = "Untapped profile"  # override
    URL_TEMPLATE = "https://mtga.untapped.gg{}"
    DECK_SCRAPERS = UntappedProfileDeckScraper,  # override
    XPATH = "//a[contains(@href, '/profile/') and contains(@class, 'deckbox')]"
    CONSENT_XPATH = CONSENT_XPATH

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return "mtga.untapped.gg/profile/" in url.lower() and "/deck/" not in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _collect(self) -> list[str]:  # override
        a_tags = self._soup.find_all("a", href=lambda h: h and "/profile/" in h)
        a_tags = [a_tag for a_tag in a_tags if "deckbox" in a_tag.attrs["class"]]
        return [self.URL_TEMPLATE.format(a_tag["href"]) for a_tag in a_tags]
