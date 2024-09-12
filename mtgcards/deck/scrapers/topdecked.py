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
from selenium.common import ElementClickInterceptedException
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
    SELENIUM_TIMEOUT, scroll_down, scroll_down_with_arrows, scroll_with_mouse_wheel, click_for_clipboard

_log = logging.getLogger(__name__)


class TopDeckedScraper(DeckScraper):
    """Scraper of TopDecked decklist page.
    """
    _SHARE_XPATH = "//ion-button[@tourstep='decklist_view_share']"
    _ARENA_XPATH = "//button[descendant::*[contains(text(), 'Share to Arena')]]"

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

            share = WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, self._SHARE_XPATH)))
            share.click()
            _log.info("Share button clicked")

            arena = click_for_clipboard(driver, self._ARENA_XPATH, 5)
            return arena.splitlines()

    def _scrape_metadata(self) -> None:  # override
        pass

    def _scrape_deck(self) -> None:  # override
        pass

        self._build_deck()
