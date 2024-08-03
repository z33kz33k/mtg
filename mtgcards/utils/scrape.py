"""

    mtgcards.utils.scrape.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Utilities for scraping.

    @author: z33k

"""
import json
import logging
import time
from functools import wraps
from typing import Callable, Dict, Optional, Union

import brotli
import pyperclip
import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mtgcards.const import Json
from mtgcards.utils import timed
from mtgcards.utils.check_type import type_checker

_log = logging.getLogger(__name__)
REQUESTS_TIMEOUT = 15.0  # seconds
SELENIUM_TIMEOUT = 10.0  # seconds
DEFAULT_THROTTLING = 0.5  # seconds


class ScrapingError(IOError):
    """Raised whenever scraping produces unexpected results.
    """


http_requests_count = 0


@timed("request")
@type_checker(str)
def timed_request(
        url: str, postdata: Optional[Json] = None, return_json=False,
        **requests_kwargs) -> Union[list[Json], Json, str]:
    _log.info(f"Retrieving data from: '{url}'...")
    global http_requests_count
    if postdata:
        response = requests.post(url, json=postdata, **requests_kwargs)
    else:
        response = requests.get(url, timeout=REQUESTS_TIMEOUT, **requests_kwargs)
    http_requests_count += 1
    if str(response.status_code)[0] in ("4", "5"):
        msg = f"Request failed with: '{response.status_code} {response.reason}'"
        if response.status_code in (502, 503, 504):
            raise HTTPError(msg)
        _log.warning(msg)

    # handle brotli compression
    if response.headers.get("Content-Encoding") == "br":
        try:
            decompressed = brotli.decompress(response.content)
            if return_json:
                return json.loads(decompressed)
            return decompressed
        except brotli.error:
            pass

    if return_json:
        return response.json() if response.text else {}
    return response.text


@timed("request")
@type_checker(str)
def getsoup(url: str, headers: Dict[str, str] | None = None) -> BeautifulSoup:
    """Return BeautifulSoup object based on ``url``.

    Args:
        url: URL string
        headers: a dictionary of headers to add to the request

    Returns:
        a BeautifulSoup object
    """
    _log.info(f"Requesting: {url!r}...")
    global http_requests_count
    response = requests.get(url, timeout=REQUESTS_TIMEOUT, headers=headers)
    http_requests_count += 1
    if str(response.status_code)[0] in ("4", "5"):
        msg = f"Request failed with: '{response.status_code} {response.reason}'"
        if response.status_code in (502, 503, 504):
            raise HTTPError(msg)
        _log.warning(msg)
    return BeautifulSoup(response.text, "lxml")


def throttle(delay: float | Callable[..., float]) -> None:
    amount = delay() if callable(delay) else delay
    _log.info(f"Throttling for {amount} seconds...")
    time.sleep(amount)


def throttled(delay: float | Callable[..., float]) -> Callable:
    """Add throttling delay after the decorated operation.

    Args:
        throttling delay in fraction of seconds

    Returns:
        the decorated function
    """
    def decorate(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            throttle(delay)
            return result
        return wrapper
    return decorate


@throttled(DEFAULT_THROTTLING)
def throttled_soup(url: str, headers: Dict[str, str] | None = None) -> BeautifulSoup:
    return getsoup(url, headers=headers)


def http_requests_counted(operation="") -> Callable:
    """Count HTTP requests done by the decorated operation.

    Args:
        name of the operation

    Returns:
        the decorated function
    """
    def decorate(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            global http_requests_count
            initial_count = http_requests_count
            result = func(*args, **kwargs)
            requests_made = http_requests_count - initial_count
            nonlocal operation
            operation = operation or f"{func.__name__!r}"
            _log.info(f"Needed {requests_made} HTTP request(s) to carry out {operation}")
            return result
        return wrapper
    return decorate


def extract_source(url: str) -> str:
    parts = [p for p in url.split("/") if p]
    return parts[1] if "http" in parts[0] else parts[0]


# SELENIUM


@timed("getting dynamic soup")
def get_dynamic_soup_by_xpath(
        url: str, xpath: str, click=False, consent_xpath="", clipboard_xpath="",
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
        click: if True, main element is clicked before returning the soups
        consent_xpath: XPath to locate a consent button (if present)
        clipboard_xpath: Xpath to locate a copy-to-clipboard button (if present)
        timeout: timeout used in attempted actions (consent timeout is halved)

    Returns:
        tuple of: BeautifulSoup object from dynamically loaded page source, second such object (if
        the located element was clicked), clipboard content (if copy-to-clipboard element was
        clicked)
    """
    driver = webdriver.Chrome()
    _log.info(f"Webdriving using Chrome to: '{url}'...")
    driver.get(url)

    if consent_xpath:
        accept_consent(driver, consent_xpath)

    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath)))
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
    finally:
        driver.quit()


@throttled(DEFAULT_THROTTLING)
def throttled_dynamic_soup_by_xpath(
        url: str, xpath: str, click=False, consent_xpath="", clipboard_xpath="",
        timeout=SELENIUM_TIMEOUT) -> tuple[BeautifulSoup, BeautifulSoup | None, str | None]:
    return get_dynamic_soup_by_xpath(url, xpath, click, consent_xpath, clipboard_xpath, timeout)


def accept_consent(driver: WebDriver, xpath: str, timeout=SELENIUM_TIMEOUT / 2) -> None:
    """Accept consent by clicking element located by ``xpath`` with the passed Chrome
    webdriver.

    If the located element is not present, this function just returns doing nothing. Otherwise,
    the located element is clicked and the driver waits for its disappearance.

    Args:
        driver: a Chrome webdriver object
        xpath: XPath to locate the consent button to be clicked
        timeout: wait this much for disappearance of the located element
    """
    _log.info("Attempting to close consent pop-up (if present)...")
    # locate and click the consent button if present
    try:
        consent_button = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath)))
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


def click_for_clipboard(driver: WebDriver, xpath: str, timeout=SELENIUM_TIMEOUT / 2) -> str:
    """Click element located by ``xpath`` with the passed Chrome webdriver and return clipboard
    contents.

    This function assumes that clicking the located element causes an OS clipboard to be populated.

    If consent XPath is specified (it should point to a clickable consent button), then its
    presence first is checked and, if confirmed, consent is clicked before attempting any other
    action.

    Args:
        driver: a Chrome webdriver object
        xpath: XPath to locate the main element
        timeout: timeout used in attempted actions (consent timeout is halved)

    Returns:
        BeautifulSoup object (or two such objects if located element was clicked) from dynamically
        loaded page source
    """
    _log.info("Attempting to click an element to populate clipboard...")

    try:
        copy_element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath)))
        copy_element.click()
        _log.info(f"Copy-to-clipboard element clicked")
        time.sleep(0.2)
        return pyperclip.paste()

    except TimeoutException:
        driver.quit()
        _log.error(f"Timed out waiting for element specified by {xpath!r} to be present")
        raise
