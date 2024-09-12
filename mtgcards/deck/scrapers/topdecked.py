"""

    mtgcards.deck.scrapers.topdecked.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape TopDecked decklists.

    @author: z33k

"""
import logging
import time
from datetime import datetime

import dateutil.parser
from bs4 import Tag
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mtgcards import Json
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.scryfall import Card
from mtgcards.utils import extract_int
from mtgcards.utils.scrape import ScrapingError, get_dynamic_soup_by_xpath, getsoup, \
    SELENIUM_TIMEOUT, scroll_down, scroll_down_with_arrows, scroll_with_mouse_wheel

_log = logging.getLogger(__name__)


# TODO: scrap this bullshit and try to click 'Share to Arena' option to get Arena decklist from
#  clipboard
class TopDeckedScraper(DeckScraper):
    """Scraper of TopDecked decklist page.
    """
    _DECK_XPATH = ("//ion-segment-button[contains(@class, 'md') and contains(@class, 'in-toolbar') "
              "and contains(@class, 'segment-button-checked')]")
    _SIDE_XPATH = ("//ion-segment-button[contains(@class, 'md') and contains(@class, 'in-toolbar') "
              "and contains(@class, 'segment-button-after-checked')]")
    _CARD_XPATH = ("//span[contains(@class, 'card-block__invisible__name') "
                   "and contains(@class, 'ng-star-inserted')]")
    _CONSENT_XPATH = "//ion-button[contains(., 'Ok!')]"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        try:
            self._main_names, self._side_names = self._get_card_names()
            self._scrape_metadata()
            self._scrape_deck()
        except TimeoutException:
            _log.warning(f"Scraping failed due to Selenium timing out")

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.topdecked.com/decks/" in url

    def _get_card_names(self) -> tuple[list[str], list[str]]:
        driver = webdriver.Chrome()
        _log.info(f"Webdriving using Chrome to: '{self.url}'...")
        driver.get(self.url)

        try:
            consent = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, self._CONSENT_XPATH)))
            consent.click()
            WebDriverWait(driver, SELENIUM_TIMEOUT).until_not(
                EC.presence_of_element_located((By.XPATH, self._CONSENT_XPATH)))
            _log.info("Consent pop-up closed")

            time.sleep(1)

            main_elements = WebDriverWait(driver, 30).until(
                EC.presence_of_all_elements_located((By.XPATH, self._CARD_XPATH)))
            main_names = [element.text.strip() for element in main_elements]

            scroll_down_with_arrows(driver, 45)
            time.sleep(1)

            main_elements = WebDriverWait(driver, 30).until(
                EC.presence_of_all_elements_located((By.XPATH, self._CARD_XPATH)))
            main_names += [element.text.strip() for element in main_elements]

            try:
                side_btn = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                    EC.element_to_be_clickable((By.XPATH, self._SIDE_XPATH)))
            except TimeoutException:
                _log.warning(f"'SIDE' button cannot be located")
                side_names = []
            else:
                side_btn.click()
                _log.info("'SIDE' button clicked")

                time.sleep(1)

                side_elements = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                    EC.presence_of_all_elements_located((By.XPATH, self._CARD_XPATH)))
                side_names = [element.text.strip() for element in side_elements]

            return [n for n in main_names if n], [sn for sn in side_names if sn]

        finally:
            driver.quit()


    def _scrape_metadata(self) -> None:  # override
        pass

    def _scrape_deck(self) -> None:  # override
        pass

        self._build_deck()
