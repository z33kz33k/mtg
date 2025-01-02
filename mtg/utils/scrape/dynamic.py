"""

    mtg.utils.scrape.py
    ~~~~~~~~~~~~~~~~~~~
    Utilities for scraping of dynamic sites.

    @author: z33k

"""
import json
import logging
import time

import backoff
import pyperclip
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common import ElementClickInterceptedException, NoSuchElementException, \
    TimeoutException
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from mtg import Json
from mtg.utils import timed
from mtg.utils.scrape import DEFAULT_THROTTLING, throttled


_log = logging.getLogger(__name__)
SELENIUM_TIMEOUT = 20.0  # seconds


@timed("getting dynamic soup")
@backoff.on_exception(backoff.expo, ElementClickInterceptedException, max_time=300)
def get_dynamic_soup(
        url: str,
        xpath: str,
        *halt_xpaths,
        click=False,
        consent_xpath="",
        clipboard_xpath="",
        wait_for_consent_disappearance=True,
        timeout=SELENIUM_TIMEOUT) -> tuple[BeautifulSoup, BeautifulSoup | None, str | None]:
    """Return BeautifulSoup object(s) from dynamically rendered page source at ``url`` using
    Selenium WebDriver that waits for presence of an element specified by ``xpath``.

    If specified, attempt at clicking the located element first is made and two soup objects are
    returned (with state before and after the click).

    If consent XPath is specified (it should point to a clickable consent button), then its
    presence first is checked and, if confirmed, consent is clicked before attempting any other
    action.

    Args:
        url: webpage's URL
        xpath: XPath to locate the main element
        halt_xpaths: XPaths to locate elements that should halt the wait
        click: if True, main element is clicked before returning the soups
        consent_xpath: XPath to locate a consent button (if present)
        clipboard_xpath: Xpath to locate a copy-to-clipboard button (if present)
        wait_for_consent_disappearance: if True, wait for the consent window to disappear
        timeout: timeout used in attempted actions (consent timeout is halved)

    Returns:
        tuple of: BeautifulSoup object from dynamically loaded page source, second such object (if
        the located element was clicked), clipboard content (if copy-to-clipboard element was
        clicked)
    """
    with webdriver.Chrome() as driver:
        try:
            _log.info(f"Webdriving using Chrome to: '{url}'...")
            driver.get(url)

            if consent_xpath:
                if wait_for_consent_disappearance:
                    accept_consent(driver, consent_xpath)
                else:
                    accept_consent_without_wait(driver, consent_xpath)

            element = _wait_for_elements(driver, xpath, *halt_xpaths, timeout=timeout)
            if not element:
                raise NoSuchElementException(f"Element specified by {xpath!r} is not present")
            _log.info(f"Page has been loaded and element specified by {xpath!r} is present")

            page_source, soup2 = driver.page_source, None
            if click:
                element.click()
                soup2 = BeautifulSoup(driver.page_source, "lxml")
            soup = BeautifulSoup(page_source, "lxml")

            clipboard = None
            if clipboard_xpath:
                clipboard = click_for_clipboard(driver, clipboard_xpath)

            return soup, soup2, clipboard

        except TimeoutException:
            _log.error(f"Timed out waiting for element specified by {xpath!r} to be present")
            raise


@timed("getting JSON with Selenium")
def get_selenium_json(url: str) -> Json:
    """Get JSON data at ``url`` using Selenium WebDriver.
    """
    with webdriver.Chrome() as driver:
        _log.info(f"Webdriving using Chrome to: '{url}'...")
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, "lxml")
        return json.loads(soup.text)


@throttled(DEFAULT_THROTTLING)
def throttled_dynamic_soup_by_xpath(
        url: str, xpath: str, click=False, consent_xpath="", clipboard_xpath="",
        timeout=SELENIUM_TIMEOUT) -> tuple[BeautifulSoup, BeautifulSoup | None, str | None]:
    return get_dynamic_soup(url, xpath, click, consent_xpath, clipboard_xpath, timeout)


def accept_consent(driver: WebDriver, xpath: str, timeout=SELENIUM_TIMEOUT) -> None:
    """Accept consent by clicking element located by ``xpath`` with the passed Chrome
    webdriver.

    If the located element is not present, this function just returns doing nothing. Otherwise,
    the located element is clicked and the driver waits for its disappearance.

    Args:
        driver: a Chrome webdriver object
        xpath: XPath to locate the consent button to be clicked
        timeout: wait this much for appearance or disappearance of the located element
    """
    _log.info("Attempting to close consent pop-up (if present)...")
    # locate and click the consent button if present
    try:
        consent_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath)))
        consent_button.click()
        _log.info("Consent button clicked")
    except TimeoutException:
        _log.info("No need for accepting. Consent window not found")
        return None

    # wait for the consent window to disappear
    try:
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.XPATH, xpath)))
        _log.info("Consent pop-up closed")
    except TimeoutException:
        driver.quit()
        _log.error("Timed out waiting for consent pop-up to disappear")
        raise


def accept_consent_without_wait(
        driver: WebDriver, xpath: str, timeout=SELENIUM_TIMEOUT) -> None:
    """Accept consent by clicking element located by ``xpath`` with the passed Chrome
    webdriver. Don't wait for the consent window to disappear.

    If the located element is not present, this function just returns doing nothing. Otherwise,
    the located element is clicked and the function returns without waiting.

    Args:
        driver: a Chrome webdriver object
        xpath: XPath to locate the consent button to be clicked
        timeout: wait this much for appearance of the located element
    """
    _log.info("Attempting to close consent pop-up (if present)...")
    # locate and click the consent button if present
    try:
        consent_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath)))
        consent_button.click()
        _log.info("Consent button clicked")
    except TimeoutException:
        _log.info("No need for accepting. Consent window not found")
        return None


def click_for_clipboard(
        driver: WebDriver, xpath: str, delay=0.5, timeout=SELENIUM_TIMEOUT / 2) -> str:
    """Click element located by ``xpath`` with the passed Chrome webdriver and return clipboard
    contents.

    This function assumes that clicking the located element causes an OS clipboard to be populated.

    If consent XPath is specified (it should point to a clickable consent button), then its
    presence first is checked and, if confirmed, consent is clicked before attempting any other
    action.

    Args:
        driver: a Chrome webdriver object
        xpath: XPath to locate the main element
        delay: delay in seconds to wait for clipboard to be populated
        timeout: timeout used in attempted actions

    Returns:
        string clipboard content
    """
    _log.info("Attempting to click an element to populate clipboard...")

    try:
        copy_element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath)))
        copy_element.click()
        _log.info(f"Copy-to-clipboard element clicked")
        time.sleep(delay)
        return pyperclip.paste()

    except TimeoutException:
        driver.quit()
        _log.error(f"Timed out waiting for element specified by {xpath!r} to be present")
        raise


def _wait_for_elements(
        driver: WebDriver, xpath: str, *halt_xpaths: str,
        timeout=SELENIUM_TIMEOUT) -> WebElement | None:
    """Wait for elements specified by ``xpath`` and ``halt_xpaths`` to be present in the current
    page.

    If ``xpath`` element is located return it. If any element designated by``halt_xpaths`` is
    located return `None`.

    Args:
        driver: a Chrome webdriver object
        xpath: XPath to locate the main element
        halt_xpaths: XPaths to locate elements that should halt the wait
        timeout: timeout used in attempted actions
    """
    if halt_xpaths:
        WebDriverWait(driver, timeout).until(
        EC.any_of(
            EC.presence_of_element_located((By.XPATH, xpath)),
            *[EC.presence_of_element_located((By.XPATH, xp)) for xp in halt_xpaths]
        ))

        # check which element was found
        elements = driver.find_elements(By.XPATH, xpath)
        if elements:
            return elements[0]

        _log.warning("Halting element found")
        return None

    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath)))


def scroll_down(driver: WebDriver, element: WebElement | None = None, pixel_offset: int = 0) -> None:
    """Scroll down to the element specified or to the bottom of the page.
    """
    if element:
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
    elif pixel_offset:
        driver.execute_script(f"window.scrollBy(0, {pixel_offset});")
    else:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")


def scroll_with_mouse_wheel(
        driver: WebDriver, delta_y: int, element: WebElement | None = None) -> None:
    element = element or driver.find_element(By.TAG_NAME, "body")
    action = ActionChains(driver)
    action.move_to_element(element).click_and_hold().move_by_offset(0, delta_y).release().perform()


def scroll_down_with_arrows(driver, times=5) -> None:
    body = driver.find_element(By.TAG_NAME, "body")
    for _ in range(times):
        body.send_keys(Keys.ARROW_DOWN)
        driver.implicitly_wait(0.5)  # small wait between scrolls
