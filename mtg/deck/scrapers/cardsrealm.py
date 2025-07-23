"""

    mtg.deck.scrapers.cardsrealm
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape Cardsrealm decklists.

    @author: z33k

"""
import logging
import time
from typing import override

import dateutil.parser
from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.common import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mtg import Json
from mtg.deck.scrapers import DeckScraper, DeckUrlsContainerScraper, \
    FolderContainerScraper, HybridContainerScraper
from mtg.utils import timed
from mtg.utils.scrape import ScrapingError, dissect_js, strip_url_query
from mtg.utils.scrape.dynamic import SELENIUM_TIMEOUT, accept_consent

_log = logging.getLogger(__name__)
BASIC_DOMAIN = "cardsrealm.com"
URL_PREFIX = "https://mtg.cardsrealm.com"


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


@DeckScraper.registered
class CardsrealmDeckScraper(DeckScraper):
    """Scraper of Cardsrealm decklist page.
    """
    DATA_FROM_SOUP = True  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return f"{BASIC_DOMAIN}/" in url.lower() and "/decks/" in url.lower()

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(url)
        return to_eng_url(url, "/decks/")

    @override
    def _get_data_from_soup(self) -> Json:
        def process(text: str) -> str:
            obj, _ = text.rsplit("]", maxsplit=1)
            return obj + "]"
        return dissect_js(
            self._soup, "var deck_cards = ", 'var torneio_type =', end_processor=process)

    @override
    def _parse_metadata(self) -> None:
        card_data = self._data[0]
        self._metadata["name"] = card_data["deck_title"]
        date_text = card_data.get("deck_lastchange", card_data['deck_card_datetime'])
        self._metadata["date"] = dateutil.parser.parse(date_text).date()
        self._metadata["author"] = card_data["givenNameUser"]
        if views := card_data.get("deck_views"):
            self._metadata["views"] = views
        self._update_fmt(card_data["tour_type_name"].lower())

    def _parse_card_json(self, card_json: Json) -> None:
        name = card_json["name_of_card"]
        quantity = card_json["deck_quantity"]
        card = self.find_card(name)
        if card_json["deck_sideboard"] == 1:
            self._sideboard += self.get_playset(card, quantity)
        elif card_json["deck_sideboard"] == 0:
            self._maindeck += self.get_playset(card, quantity)

    @override
    def _parse_deck(self) -> None:
        # filter out tokens and maybe-boards
        for card_data in [cd for cd  in self._data if cd["deck_sideboard"] in (0, 1)]:
            self._parse_card_json(card_data)
        self._derive_commander_from_sideboard()


@DeckUrlsContainerScraper.registered
class CardsrealmProfileScraper(DeckUrlsContainerScraper):
    """Scraper of Cardsrealm user profile page.
    """
    CONTAINER_NAME = "Cardsrealm profile"  # override
    DECK_SCRAPERS = CardsrealmDeckScraper,  # override
    DECK_URL_PREFIX = URL_PREFIX  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return all(t in url.lower() for t in (f"{BASIC_DOMAIN}/", "/profile/", "/decks"))

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(url)
        return to_eng_url(url, "/profile/")

    @override
    def _collect(self) -> list[str]:
        deck_divs = [
            div for div in self._soup.find_all("div", class_=lambda c: c and "deck_div_all" in c)]
        deck_tags = [d.find("a", href=lambda h: h and "/decks/" in h) for d in deck_divs]
        if not deck_tags:
            raise ScrapingError("Deck tags not found", scraper=type(self), url=self.url)
        return [tag.attrs["href"] for tag in deck_tags]


@FolderContainerScraper.registered
@DeckUrlsContainerScraper.registered
class CardsrealmFolderScraper(CardsrealmProfileScraper):
    """Scraper of Cardsrealm decks folder page.
    """
    CONTAINER_NAME = "Cardsrealm folder"  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return all(t in url.lower() for t in (f"{BASIC_DOMAIN}/", "/decks/folder/"))

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(url)
        return to_eng_url(url, "/decks/")


# e.g.: https://mtg.cardsrealm.com/en-us/meta-decks/pauper/tournaments/1k27j-pauper-royale-220
def _is_meta_tournament_url(url: str) -> bool:
    return all(t in url.lower() for t in (f"{BASIC_DOMAIN}/", "/meta-decks/", "/tournaments/"))


# e.g.: https://mtg.cardsrealm.com/en-us/tournament/1k27j-pauper-royale-220
def _is_regular_tournament_url(url: str) -> bool:
    return (all(t in url.lower() for t in (f"{BASIC_DOMAIN}/", "/tournament/"))
            and "/meta-decks/" not in url.lower())


@DeckUrlsContainerScraper.registered
class CardsrealmMetaTournamentScraper(DeckUrlsContainerScraper):
    """Scraper of Cardsrealm meta-deck tournaments page.
    """
    CONTAINER_NAME = "Cardsrealm meta-deck tournament"  # override
    DECK_SCRAPERS = CardsrealmDeckScraper,  # override
    DECK_URL_PREFIX = URL_PREFIX  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return _is_meta_tournament_url(url)

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(url)
        return to_eng_url(url, "/meta-decks/")

    @override
    def _collect(self) -> list[str]:
        deck_tags = [
            tag for tag in
            self._soup.find_all(
                lambda t: t.name == "a"
                          and t.text.strip() == "Decklist"
                          and t.parent.name == "span")]
        if not deck_tags:
            raise ScrapingError("Deck tags not found", scraper=type(self), url=self.url)
        return sorted({tag.attrs["href"] for tag in deck_tags})


@DeckUrlsContainerScraper.registered
class CardsrealmRegularTournamentScraper(DeckUrlsContainerScraper):
    """Scraper of Cardsrealm regular tournaments page.
    """
    SELENIUM_PARAMS = {  # override
        "xpath": "//button[text()='show deck']",
        "consent_xpath": '//button[@id="ez-accept-all"]'
    }
    CONTAINER_NAME = "Cardsrealm regular tournament"  # override
    DECK_SCRAPERS = CardsrealmDeckScraper,  # override

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return _is_regular_tournament_url(url)

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(url)
        return to_eng_url(url, "/tournament/")

    @timed("getting dynamic soup")
    def _get_dynamic_soup(self) -> BeautifulSoup:
        with webdriver.Chrome() as driver:
            try:
                _log.info(f"Webdriving using Chrome to: '{self.url}'...")
                driver.get(self.url)

                accept_consent(driver, self.SELENIUM_PARAMS["consent_xpath"])

                buttons = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                    EC.presence_of_all_elements_located((By.XPATH, self.SELENIUM_PARAMS["xpath"])))
                _log.info("Page has been loaded and XPath-specified elements are present")

                for btn in buttons:
                    btn.click()

                time.sleep(0.5)
                return BeautifulSoup(driver.page_source, "lxml")

            except ElementClickInterceptedException:
                msg = "Selenium click intercepted by a pop-up. Not all decklists gathered"
                err = ScrapingError(msg, scraper=type(self), url=self.url)
                _log.warning(f"Scraping failed with: {err!r}")
                return BeautifulSoup(driver.page_source, "lxml")

            except TimeoutException:
                err = ScrapingError(self._selenium_timeout_msg, scraper=type(self), url=self.url)
                _log.warning(f"Scraping failed with: {err!r}")
                return BeautifulSoup(driver.page_source, "lxml")

    @override
    def _fetch_soup(self) -> None:
        self._soup = self._get_dynamic_soup()

    @override
    def _collect(self) -> list[str]:
        deck_divs = [
            div for div in self._soup.find_all("div", class_=lambda c: c and "mainDeck" in c)]
        deck_tags = [d.find("a", href=lambda h: h and "/decks/" in h) for d in deck_divs]
        if not deck_tags:
            raise ScrapingError("Deck tags not found", scraper=type(self), url=self.url)
        return [tag.attrs["href"] for tag in deck_tags if tag is not None]


@HybridContainerScraper.registered
class CardsrealmArticleScraper(HybridContainerScraper):
    """Scraper of Cardsrealm decks article page.
    """
    CONTAINER_NAME = "Cardsrealm article"  # override
    # override
    CONTAINER_SCRAPERS = (
        CardsrealmProfileScraper, CardsrealmFolderScraper, CardsrealmRegularTournamentScraper,
        CardsrealmMetaTournamentScraper)

    @staticmethod
    @override
    def is_valid_url(url: str) -> bool:
        return (all(
            t in url.lower() for t in (f"{BASIC_DOMAIN}/", "/articles/"))
                and "/search/" not in url.lower())

    @staticmethod
    @override
    def sanitize_url(url: str) -> str:
        url = strip_url_query(url)
        return to_eng_url(url, "/articles/")

    @override
    def _collect(self) -> tuple[list[str], list[Tag], list[Json], list[str]]:
        article_tag = self._soup.find("div", id="article_div_all")
        if article_tag is None:
            raise ScrapingError("Article tag not found", scraper=type(self), url=self.url)
        deck_links, container_links = self._get_links_from_tags(article_tag, url_prefix=URL_PREFIX)
        return deck_links, [], [], container_links
