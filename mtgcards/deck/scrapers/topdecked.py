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
from mtgcards.utils.scrape import ScrapingError, get_dynamic_soup_by_xpath, getsoup, SELENIUM_TIMEOUT

_log = logging.getLogger(__name__)


class TopDeckedScraper(DeckScraper):
    """Scraper of TopDecked decklist page.
    """
    _XPATH = ("//ion-segment-button[contains(@class, 'md') and contains(@class, 'in-toolbar') "
              "and contains(@class, 'segment-button-after-checked')]")
    # _CONSENT_XPATH = "//ion-button[text()=' Ok! ']"
    _CARD_XPATH = ("//span[contains(@class, 'card-block__invisible__name') "
                   "and contains(@class, 'ng-star-inserted')]")

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        try:
            self._main_names, self._side_names = self._get_card_data()
            self._scrape_metadata()
            self._scrape_deck()
        except TimeoutException:
            _log.warning(f"Scraping failed due to Selenium timing out")

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "www.topdecked.com/decks/" in url

    def _get_card_data(self) -> tuple[list[str], list[str]]:
        driver = webdriver.Chrome()
        _log.info(f"Webdriving using Chrome to: '{self.url}'...")
        driver.get(self.url)

        try:
            side_btn = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, self._XPATH)))
            if not side_btn:
                raise NoSuchElementException(f"Unable to find 'SIDE' button")
            _log.info(f"Page has been loaded and 'SIDE' button is present")

            main_elements = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                EC.presence_of_all_elements_located((By.XPATH, self._CARD_XPATH)))
            main_names = [element.text.strip() for element in main_elements]
            main_names = [name for name in main_names if name]

            side_btn.click()
            _log.info("'SIDE' button clicked")

            time.sleep(1)

            side_elements = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                EC.presence_of_all_elements_located((By.XPATH, self._CARD_XPATH)))
            side_names = [element.text.strip() for element in side_elements]
            side_names = [name for name in side_names if name]

            return main_names, side_names

        finally:
            driver.quit()

    def _scrape_metadata(self) -> None:  # override
        pass

    def _scrape_deck(self) -> None:  # override
        pass

        self._build_deck()
