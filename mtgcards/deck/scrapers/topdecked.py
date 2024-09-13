"""

    mtgcards.deck.scrapers.topdecked.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TopDecked decklists.

    @author: z33k

"""
import logging

from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mtgcards import Json
from mtgcards.deck.arena import ArenaParser, PlaysetLine
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import SELENIUM_TIMEOUT, click_for_clipboard
from mtgcards.utils import get_date_from_ago_text, extract_float
from mtgcards.scryfall import COMMANDER_FORMATS

_log = logging.getLogger(__name__)


def _sanitize_element_text(text: str) -> str:
    text = text.strip()
    if "\n" in text:
        text, *_ = text.split("\n")
    return text


class TopDeckedScraper(DeckScraper):
    """Scraper of TopDecked decklist page.
    """
    _CONSENT_XPATH = "//ion-button[contains(., 'Ok!')]"
    _CONSENT_TIMEOUT = 30
    _SHARE_XPATH = "//ion-button[@tourstep='decklist_view_share']"
    _ARENA_XPATH = "//button[descendant::*[contains(text(), 'Share to Arena')]]"
    _ARENA_DELAY = 4
    _NAME_XPATH = "//ion-title[contains(@class, 'title-default')]"
    _FMT_XPATH = "//span[contains(@class, 'format') and contains(@class, 'text-uppercase')]"
    _DATE_XPATH = ("//span[contains(@class, 'prefix') and contains(@class, 'text-none') and "
                   "contains(@class, 'ng-star-inserted')]")

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        try:
            self._arena_decklist = self._get_data()
            self._scrape_deck()
        except TimeoutException:
            _log.warning(f"Scraping failed due to Selenium timing out")

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.topdecked.com/decks/" in url

    def _get_data(self) -> list[str]:
        with webdriver.Chrome() as driver:
            _log.info(f"Webdriving using Chrome to: '{self.url}'...")
            driver.get(self.url)

            # consent
            consent = WebDriverWait(driver, self._CONSENT_TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, self._CONSENT_XPATH)))
            consent.click()
            WebDriverWait(driver, SELENIUM_TIMEOUT / 2).until_not(
                EC.presence_of_element_located((By.XPATH, self._CONSENT_XPATH)))
            _log.info("Consent pop-up closed")

            # metadata
            self._scrape_metadata_with_selenium(driver)

            # arena decklist
            share_btn = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, self._SHARE_XPATH)))
            share_btn.click()
            _log.info("Share button clicked")
            arena = click_for_clipboard(driver, self._ARENA_XPATH, self._ARENA_DELAY)
            return arena.splitlines()

    def _scrape_metadata_with_selenium(self, driver: webdriver.Chrome) -> None:
        name_el = driver.find_element(By.XPATH, self._NAME_XPATH)
        self._metadata["name"] = _sanitize_element_text(name_el.text)
        fmt_el = driver.find_element(By.XPATH, self._FMT_XPATH)
        self._update_fmt(_sanitize_element_text(fmt_el.text))
        try:
            date_el = driver.find_element(By.XPATH, self._DATE_XPATH)
            self._metadata["date"] = get_date_from_ago_text(
                _sanitize_element_text(date_el.text))
        except NoSuchElementException:  # meta-decks feature no date data
            pass

    def _scrape_metadata(self) -> None:  # override
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

    def _scrape_deck(self) -> None:  # override
        if self.fmt and self.fmt in COMMANDER_FORMATS:
            self._handle_commander()

        self._deck = ArenaParser(self._arena_decklist, self._metadata).deck


class TopDeckedMetadeckScraper(TopDeckedScraper):
    """Scarper of TopDecked meta-deck decklist page.
    """
    _SHARE_XPATH = "//ion-button[contains(text(), 'Share')]"
    _META_SHARE_XPATH = (
        "//span[contains(@class, 'text-medium') and contains(@class, 'subtext') "
        "and contains(text(), 'of meta')]")

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.topdecked.com/metagame/" in url and "/decks/" in url

    def _scrape_metadata_with_selenium(self, driver: webdriver.Chrome) -> None:  # override
        super()._scrape_metadata_with_selenium(driver)
        meta_share_el = driver.find_element(By.XPATH, self._META_SHARE_XPATH)
        self._metadata["meta_share"] = extract_float(_sanitize_element_text(meta_share_el.text))
