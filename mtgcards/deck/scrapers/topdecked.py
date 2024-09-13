"""

    mtgcards.deck.scrapers.topdecked.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TopDecked decklists.

    @author: z33k

"""
import logging

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mtgcards import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.utils.scrape import SELENIUM_TIMEOUT, click_for_clipboard
from mtgcards.utils import get_date_from_ago_text

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
    _NAME_XPATH = "//ion-title[contains(@class, 'header__title')]"
    _FMT_XPATH = "//span[contains(@class, 'format') and contains(@class, 'text-uppercase')]"
    _DATE_XPATH = ("//span[contains(@class, 'prefix') and contains(@class, 'text-none') and "
                   "contains(@class, 'ng-star-inserted')]")

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        try:
            self._arena_decklist = self._get_data()
            self._scrape_metadata()
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
            name_el = driver.find_element(By.XPATH, self._NAME_XPATH)
            self._metadata["name"] = _sanitize_element_text(name_el.text)
            fmt_el = driver.find_element(By.XPATH, self._FMT_XPATH)
            self._update_fmt(_sanitize_element_text(fmt_el.text))
            date_el = driver.find_element(By.XPATH, self._DATE_XPATH)
            self._metadata["date"] = get_date_from_ago_text(_sanitize_element_text(date_el.text))

            # arena decklist
            share_btn = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, self._SHARE_XPATH)))
            share_btn.click()
            _log.info("Share button clicked")
            arena = click_for_clipboard(driver, self._ARENA_XPATH, self._ARENA_DELAY)
            return arena.splitlines()

    def _scrape_metadata(self) -> None:  # override
        pass

    def _scrape_deck(self) -> None:  # override
        pass

        self._build_deck()
