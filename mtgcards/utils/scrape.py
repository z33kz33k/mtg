"""

    mtgcards.utils.scrape.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Utilities for scraping.

    @author: z33k

"""
import logging
import time
from functools import wraps
from typing import Callable, Dict, Optional, Union

import requests
from requests.exceptions import HTTPError
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from mtgcards.const import Json, REQUEST_TIMEOUT
from mtgcards.utils import timed
from mtgcards.utils.check_type import type_checker


_log = logging.getLogger(__name__)


class ScrapingError(IOError):
    """Raised whenever scraping produces unexpected results.
    """


http_requests_count = 0


@timed("request")
def timed_request(
        url: str, postdata: Optional[Json] = None, return_json=False,
        **requests_kwargs) -> Union[list[Json], Json, str]:
    _log.info(f"Retrieving data from: '{url}'...")
    global http_requests_count
    if postdata:
        response = requests.post(url, json=postdata, **requests_kwargs)
    else:
        response = requests.get(url, **requests_kwargs)
    http_requests_count += 1
    if return_json:
        return response.json()
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
    response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
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


def get_dynamic_soup_by_xpath(
        url: str, xpath: str, timeout=10.0, click=False, consent_xpath="") -> BeautifulSoup:
    """Return BeautifulSoup object from dynamically rendered page source at ``url`` using Selenium
    WebDriver that waits for presence of an element specified by ``xpath`.

    If specified, attempt at clicking the located element first is made. If consent XPath is
    specified (it should point to a clickable consent button), then its presence first is
    checked and, if confirmed, consent is clicked before attempting any other specified action.

    Args:
        url: dynamic webpage URL
        xpath: XPath to locate the main element
        timeout: timeout used in attempted actions
        click: main element is clicked before returning the soup
        consent_xpath: XPath to locate a consent button (if present)

    Returns:
        BeautifulSoup object from dynamically loaded page source
    """
    driver = webdriver.Chrome()
    _log.info(f"Webdriving using Chrome to: '{url}'...")
    driver.get(url)

    if consent_xpath:
        accept_consent(driver, consent_xpath, timeout / 2)

    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath)))
        _log.info(f"Page has been loaded and element specified by {xpath!r} is present")
        if click:
            element.click()
            WebDriverWait(driver, timeout).until(EC.element_to_be_selected(element))
        soup = BeautifulSoup(driver.page_source, "lxml")
        return soup
    except TimeoutException:
        _log.error(f"Timed out waiting for element specified by {xpath!r} to be present.")
        raise
    finally:
        driver.quit()


def accept_consent(driver: WebDriver, xpath: str, timeout=5.0) -> WebDriver:
    """Accept consent by clicking element pointed by ``xpath`` with the passed Chrome
    webdriver.

    If the located element is not present, this function just returns doing nothing. Otherwise,
    the button is clicked and the driver waits for its disappearance than returns itself.

    Args:
        driver: a Chrome webdriver object
        xpath: XPath to locate the consent button to be clicked
        timeout: wait this much for disappearance of the located element

    Returns:
        the passed webdriver object
    """
    # locate and click the consent button if present
    try:
        consent_button = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath)))
        consent_button.click()
        _log.info("Consent button clicked")
    except TimeoutException:
        _log.info("No need for accepting. Consent window not found")
        return driver

    # wait for the consent window to disappear
    try:
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.XPATH, xpath)))
        _log.info("Consent window disappeared")
    except TimeoutException:
        driver.quit()
        _log.error("Timed out waiting for consent window to disappear")
        raise

