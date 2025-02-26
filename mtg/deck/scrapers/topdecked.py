"""

    mtg.deck.scrapers.topdecked.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TopDecked decklists.

    @author: z33k

"""
import contextlib
import logging

import dateutil.parser
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mtg import Json
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser, PlaysetLine
from mtg.deck.scrapers import DeckScraper
from mtg.scryfall import COMMANDER_FORMATS
from mtg.utils import extract_float, get_date_from_ago_text
from mtg.utils.scrape import ScrapingError, strip_url_query
from mtg.utils.scrape.dynamic import SELENIUM_TIMEOUT, click_for_clipboard

_log = logging.getLogger(__name__)


def _sanitize_element_text(text: str) -> str:
    text = text.strip()
    if "\n" in text:
        text, *_ = text.split("\n")
    return text


@DeckScraper.registered
class TopDeckedRegularDeckScraper(DeckScraper):
    """Scraper of TopDecked regular decklist page.
    """
    CONSENT_XPATH = "//ion-button[contains(., 'Ok!')]"
    CONSENT_TIMEOUT = 30
    SHARE_XPATH = "//ion-button[@tourstep='decklist_view_share']"
    ARENA_XPATH = "//button[descendant::*[contains(text(), 'Share to Arena')]]"
    ARENA_DELAY = 5
    NAME_XPATH = "//ion-title[contains(@class, 'title-default')]"
    FMT_XPATH = "//span[contains(@class, 'format') and contains(@class, 'text-uppercase')]"
    DATE_XPATH = ("//span[contains(@class, 'prefix') and contains(@class, 'text-none') and "
                  "contains(@class, 'ng-star-inserted')]")

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._arena_decklist = []

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.topdecked.com/decks/" in url.lower()

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        return strip_url_query(url)

    def _process_metadata_with_selenium(self, driver: webdriver.Chrome) -> None:
        name_el = driver.find_element(By.XPATH, self.NAME_XPATH)
        self._metadata["name"] = _sanitize_element_text(name_el.text)
        fmt_el = driver.find_element(By.XPATH, self.FMT_XPATH)
        self._update_fmt(_sanitize_element_text(fmt_el.text))
        with contextlib.suppress(NoSuchElementException):  # meta-decks feature no date data
            date_el = driver.find_element(By.XPATH, self.DATE_XPATH)
            date_text = _sanitize_element_text(date_el.text)
            if "ago" in date_text:
                self._metadata["date"] = get_date_from_ago_text(date_text)
            else:
                self._metadata["date"] = dateutil.parser.parse(date_text).date()

    def _get_data(self) -> list[str]:
        with webdriver.Chrome() as driver:
            _log.info(f"Webdriving using Chrome to: '{self.url}'...")
            driver.get(self.url)

            # consent
            consent = WebDriverWait(driver, self.CONSENT_TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, self.CONSENT_XPATH)))
            consent.click()
            WebDriverWait(driver, SELENIUM_TIMEOUT / 2).until_not(
                EC.presence_of_element_located((By.XPATH, self.CONSENT_XPATH)))
            _log.info("Consent pop-up closed")

            # metadata
            self._process_metadata_with_selenium(driver)

            # arena decklist
            share_btn = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, self.SHARE_XPATH)))
            share_btn.click()
            _log.info("Share button clicked")
            arena = click_for_clipboard(driver, self.ARENA_XPATH, self.ARENA_DELAY)
            return arena.splitlines()

    # pre-process does all the work here
    def _pre_parse(self) -> None:  # override
        try:
            self._arena_decklist = self._get_data()
        except NoSuchElementException as err:
            err_text, *_ = str(err).split("(Session info")
            raise ScrapingError(f"Scraping failed due to: '{err_text.strip()}'")
        except TimeoutException:
            raise ScrapingError(f"Scraping failed due to Selenium timing out")

    def _parse_metadata(self) -> None:  # override
        pass

    def _handle_commander(self) -> None:
        commander_line, partner_line = self._arena_decklist[1:3]
        commander = PlaysetLine(commander_line).to_playset()[0]
        partner = PlaysetLine(partner_line).to_playset()[0]
        if commander.is_partner and partner.is_partner:
            del self._arena_decklist[1:3]
            self._arena_decklist.insert(0, "Commander")
            self._arena_decklist.insert(1, commander_line)
            self._arena_decklist.insert(2, partner_line)
            self._arena_decklist.insert(3, "")
        else:
            del self._arena_decklist[1]
            self._arena_decklist.insert(0, "Commander")
            self._arena_decklist.insert(1, commander_line)
            self._arena_decklist.insert(2, "")

    def _parse_decklist(self) -> None:  # override
        if self.fmt and self.fmt in COMMANDER_FORMATS:
            self._handle_commander()

    def _build_deck(self) -> Deck:  # override
        return ArenaParser(self._arena_decklist, self._metadata).parse(suppress_invalid_deck=False)


@DeckScraper.registered
class TopDeckedMetaDeckScraper(TopDeckedRegularDeckScraper):
    """Scarper of TopDecked meta-deck decklist page.
    """
    SHARE_XPATH = "//ion-button[contains(text(), 'Share')]"
    _META_SHARE_XPATH = (
        "//span[contains(@class, 'text-medium') and contains(@class, 'subtext') "
        "and contains(text(), 'of meta')]")

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.topdecked.com/metagame/" in url.lower() and "/decks/" in url.lower()

    def _process_metadata_with_selenium(self, driver: webdriver.Chrome) -> None:  # override
        super()._process_metadata_with_selenium(driver)
        meta_share_el = driver.find_element(By.XPATH, self._META_SHARE_XPATH)
        self._metadata["meta_share"] = extract_float(_sanitize_element_text(meta_share_el.text))
