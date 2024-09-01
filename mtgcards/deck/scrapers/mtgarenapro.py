"""

    mtgcards.deck.scrapers.mtgarenapro.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Scrape MTGArena.Pro decklists.

    @author: z33k

"""
import logging
import time
from datetime import datetime

import pyperclip
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mtgcards import Json
from mtgcards.deck import Deck, InvalidDeck, Mode, ParsingState
from mtgcards.deck.scrapers import DeckScraper
from mtgcards.scryfall import all_formats
from mtgcards.utils import extract_int, timed
from mtgcards.utils.scrape import ScrapingError, getsoup, \
    http_requests_counted, throttled_soup
from utils.scrape import SELENIUM_TIMEOUT

_log = logging.getLogger(__name__)


class MtgArenaProScraper(DeckScraper):
    """Scraper of MTGArena.Pro decklist page.
    """
    # _CONSENT_XPATH = "//span[text()='Accept All']"
    # _CONSENT_XPATH = "//a[contains(@class, 'cmptxt_btn_yes') and @role='button']"
    _EXPORT_DECK_XPATH = "//div[text()='Export deck']"
    _COPY_OUTPUT_XPATH = "//div[text()='Copy output']"

    def __init__(self, url: str, metadata: Json | None = None) -> None:
        super().__init__(url, metadata)
        self._soup = getsoup(self.url)
        # try:
        #     self._clipboard, self._soup = self._get_clipboard_and_soup()
        #     self._scrape_metadata()
        #     self._scrape_deck()
        # except TimeoutException:
        #     _log.warning(f"Scraping failed due to Selenium timing out")

    @staticmethod
    def is_deck_url(url: str) -> bool:  # override
        return "mtgarena.pro/decks/" in url

    @staticmethod
    def sanitize_url(url: str) -> str:  # override
        url = DeckScraper.sanitize_url(url)
        return url

    # @timed("getting clipboard and soup")
    # def _get_clipboard_and_soup(self) -> tuple[str, BeautifulSoup]:
    #     driver = webdriver.Chrome()
    #     _log.info(f"Webdriving using Chrome to: '{self.url}'...")
    #     driver.get(self.url)
    #
    #     soup = BeautifulSoup(driver.page_source, "lxml")
    #     try:
    #         for click_xpath in (self._EXPORT_DECK_XPATH, self._COPY_OUTPUT_XPATH):
    #             # element = driver.find_element(By.XPATH, click_xpath)
    #             element = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
    #                 EC.presence_of_element_located((By.XPATH, click_xpath)))
    #             driver.execute_script("arguments[0].click();", element)
    #
    #         time.sleep(0.6)
    #         clipboard = pyperclip.paste()
    #
    #         return clipboard, soup
    #
    #     except TimeoutException:
    #         _log.error(f"Timed out waiting for element specified to be present")
    #         raise
    #     finally:
    #         driver.quit()

    def _scrape_metadata(self) -> None:  # override
        pass

    def _scrape_deck(self) -> None:  # override
        pass

        self._build_deck()
