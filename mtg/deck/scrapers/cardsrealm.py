"""

    mtg.deck.scrapers.cardsrealm.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Cardsrealm decklists.

    @author: z33k

"""
import logging
import time

import dateutil.parser
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mtg import Json
from mtg.deck.scrapers import ContainerScraper, UrlDeckScraper
from mtg.utils.scrape import SELENIUM_TIMEOUT, ScrapingError, accept_consent, dissect_js, getsoup, \
    strip_url_params
from mtg.utils import timed

_log = logging.getLogger(__name__)
BASIC_DOMAIN = "cardsrealm.com"


def get_source(src: str) -> str | None:
    if BASIC_DOMAIN in src and "mtg." not in src:
        return f"mtg.{BASIC_DOMAIN}"
    return None


def to_eng_url(url: str, lang_code_delimiter: str) -> str:
    if len(lang_code_delimiter) < 3 or any(
            ch != "/" for ch in (lang_code_delimiter[0], lang_code_delimiter[-1])):
        raise ValueError(f"Invalid language code delimiter: {lang_code_delimiter!r}")
    # attempt to replace any language code other than 'en-us' with 'en-us'
    _, first = url.split(f"{BASIC_DOMAIN}/", maxsplit=1)
    if first.startswith(lang_code_delimiter[1:]):  # no lang code in url (implicitly means 'en-us')
        return url
    lang, _ = first.split(lang_code_delimiter, maxsplit=1)
    return url.replace(f"/{lang}/", "/en-us/")


@UrlDeckScraper.registered
class CardsrealmScraper(UrlDeckScraper):
    """Scraper of Cardsrealm decklist page.
    """
    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._json_data: Json | None = None

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return f"{BASIC_DOMAIN}/" in url.lower() and "/decks/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url, with_endpoint=False)
        return to_eng_url(url, "/decks/")

    def _get_json(self) -> Json:
        def process(text: str) -> str:
            obj, _ = text.rsplit("]", maxsplit=1)
            return obj + "]"
        return dissect_js(
            self._soup, "var deck_cards = ", 'var torneio_type =', end_processor=process)

    def _pre_parse(self) -> None:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            raise ScrapingError("Page not available")
        self._json_data = self._get_json()

    def _parse_metadata(self) -> None:  # override
        card_data = self._json_data[0]
        self._metadata["name"] = card_data["deck_title"]
        self._metadata["date"] = dateutil.parser.parse(card_data["deck_lastchange"]).date()
        self._metadata["author"] = card_data["givenNameUser"]
        self._metadata["views"] = card_data["deck_views"]
        self._update_fmt(card_data["tour_type_name"].lower())

    def _parse_card_json(self, card_json: Json) -> None:
        name = card_json["name_of_card"]
        quantity = card_json["deck_quantity"]
        card = self.find_card(name)
        # filter out tokens and maybe-boards
        if card_json["deck_sideboard"] == 1:
            self._sideboard += self.get_playset(card, quantity)
        elif card_json["deck_sideboard"] == 0:
            self._maindeck += self.get_playset(card, quantity)

    def _parse_deck(self) -> None:  # override
        for card_data in self._json_data:
            self._parse_card_json(card_data)
        self._derive_commander_from_sideboard()


@ContainerScraper.registered
class CardsrealmProfileScraper(ContainerScraper):
    """Scraper of Cardsrealm user profile page.
    """
    CONTAINER_NAME = "Cardsrealm profile"  # override
    DECK_URL_TEMPLATE = "https://mtg.cardsrealm.com{}"
    _DECK_SCRAPER = CardsrealmScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return all(t in url.lower() for t in (f"{BASIC_DOMAIN}/", "/profile/", "/decks"))

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url, with_endpoint=False)
        return to_eng_url(url, "/profile/")

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _, name = self.CONTAINER_NAME.split()
            _log.warning(f"{name.title()} data not available")
            return []

        deck_divs = [
            div for div in self._soup.find_all("div", class_=lambda c: c and "deck_div_all" in c)]
        deck_tags = [d.find("a", href=lambda h: h and "/decks/" in h) for d in deck_divs]
        urls = [tag.attrs["href"] for tag in deck_tags]
        return [self.DECK_URL_TEMPLATE.format(url) for url in urls]


@ContainerScraper.registered
class CardsrealmFolderScraper(CardsrealmProfileScraper):
    """Scraper of Cardsrealm decks folder page.
    """
    CONTAINER_NAME = "Cardsrealm folder"  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return all(t in url.lower() for t in (f"{BASIC_DOMAIN}/", "/decks/folder/"))

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url, with_endpoint=False)
        return to_eng_url(url, "/decks/")


# e.g.: https://mtg.cardsrealm.com/en-us/meta-decks/pauper/tournaments/1k27j-pauper-royale-220
def _is_meta_tournament_url(url: str) -> bool:
    return all(t in url.lower() for t in (f"{BASIC_DOMAIN}/", "/meta-decks/", "/tournaments/"))


# e.g.: https://mtg.cardsrealm.com/en-us/tournament/1k27j-pauper-royale-220
def _is_regular_tournament_url(url: str) -> bool:
    return (all(t in url.lower() for t in (f"{BASIC_DOMAIN}/", "/tournament/"))
            and "/meta-decks/" not in url.lower())


@ContainerScraper.registered
class CardsrealmMetaTournamentScraper(ContainerScraper):
    """Scraper of Cardsrealm meta-deck tournaments page.
    """
    CONTAINER_NAME = "Cardsrealm meta-deck tournament"  # override
    DECK_URL_TEMPLATE = "https://mtg.cardsrealm.com{}"
    _DECK_SCRAPER = CardsrealmScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return _is_meta_tournament_url(url)

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url, with_endpoint=False)
        return to_eng_url(url, "/meta-decks/")

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _log.warning(f"Tournament data not available")
            return []

        deck_tags = [
            tag for tag in
            self._soup.find_all(
                lambda t: t.name == "a"
                          and t.text.strip() == "Decklist"
                          and t.parent.name == "span")]
        urls = {tag.attrs["href"] for tag in deck_tags}
        return [self.DECK_URL_TEMPLATE.format(url) for url in sorted(urls)]


@ContainerScraper.registered
class CardsrealmRegularTournamentScraper(ContainerScraper):
    """Scraper of Cardsrealm regular tournaments page.
    """
    CONTAINER_NAME = "Cardsrealm regular tournament"  # override
    _DECK_SCRAPER = CardsrealmScraper  # override
    _CONSENT_XPATH = '//button[@id="ez-accept-all"]'
    _XPATH = "//button[text()='show deck']"

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return _is_regular_tournament_url(url)

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url, with_endpoint=False)
        return to_eng_url(url, "/tournament/")

    @timed("getting dynamic soup")
    def _get_dynamic_soup(self) -> BeautifulSoup:
        with webdriver.Chrome() as driver:
            try:
                _log.info(f"Webdriving using Chrome to: '{self.url}'...")
                driver.get(self.url)

                accept_consent(driver, self._CONSENT_XPATH)

                buttons = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                    EC.presence_of_all_elements_located((By.XPATH, self._XPATH)))
                _log.info(
                    f"Page has been loaded and elements specified by {self._XPATH!r} are present")

                for btn in buttons:
                    btn.click()

                time.sleep(0.5)
                return BeautifulSoup(driver.page_source, "lxml")

            except ElementClickInterceptedException:
                _log.warning(
                    f"Selenium click intercepted by a pop-up. Not all decklists gathered")
                return BeautifulSoup(driver.page_source, "lxml")

            except TimeoutException:
                _log.warning(f"Selenium timed out during tournament scraping")
                return BeautifulSoup(driver.page_source, "lxml")


    def _collect(self) -> list[str]:  # override
        self._soup = self._get_dynamic_soup()
        if not self._soup:
            _log.warning(f"Tournament data not available")
            return []

        deck_divs = [
            div for div in self._soup.find_all("div", class_=lambda c: c and "mainDeck" in c)]
        deck_tags = [d.find("a", href=lambda h: h and "/decks/" in h) for d in deck_divs]
        return [tag.attrs["href"] for tag in deck_tags if tag is not None]


@ContainerScraper.registered
class CardsrealmArticleScraper(ContainerScraper):
    """Scraper of Cardsrealm decks article page.
    """
    CONTAINER_NAME = "Cardsrealm article"  # override
    DECK_URL_TEMPLATE = "https://mtg.cardsrealm.com{}"
    _DECK_SCRAPER = CardsrealmScraper  # override

    @staticmethod
    def is_container_url(url: str) -> bool:  # override
        return all(t in url.lower() for t in (f"{BASIC_DOMAIN}/", "/articles/"))

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = strip_url_params(url, with_endpoint=False)
        return to_eng_url(url, "/articles/")

    def _collect(self) -> list[str]:  # override
        self._soup = getsoup(self.url)
        if not self._soup:
            _, name = self.CONTAINER_NAME.split()
            _log.warning(f"{name.title()} data not available")
            return []

        deck_divs = [
            div for div in self._soup.find_all("div", class_=lambda c: c and "mainDeck" in c)]
        deck_tags = [d.find("a", href=lambda h: h and "/decks/" in h) for d in deck_divs]
        urls = [tag.attrs["href"] for tag in deck_tags]
        return [self.DECK_URL_TEMPLATE.format(url) for url in urls]
