"""

    mtg.utils.scrape.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Utilities for scraping.

    @author: z33k

"""
import contextlib
import json
import logging
import random
import re
import time
from collections import namedtuple
from functools import wraps
from typing import Callable, Dict, Optional

import brotli
import pyperclip
import requests
from bs4 import BeautifulSoup
from bs4.dammit import EncodingDetector
from requests import Response
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib3 import Retry

from mtg import Json
from mtg.utils import ParsingError, timed
from mtg.utils.check_type import type_checker

_log = logging.getLogger(__name__)
REQUESTS_TIMEOUT = 15.0  # seconds
SELENIUM_TIMEOUT = 20.0  # seconds
DEFAULT_THROTTLING = 1.0  # seconds


class ScrapingError(ParsingError):
    """Raised whenever scraping produces unexpected results.
    """


http_requests_count = 0


def handle_brotli(response: Response, return_json: bool = False) -> str | Json | list[Json]:
    if response.headers.get("Content-Encoding") == "br":
        with contextlib.suppress(brotli.error):
            decompressed = brotli.decompress(response.content)
            if return_json:
                return json.loads(decompressed)
            return decompressed
    return response.text


@timed("request")
@type_checker(str)
def timed_request(
        url: str, postdata: Optional[Json] = None, handle_http_errors=True,
        **requests_kwargs) -> Response | None:
    _log.info(f"Requesting: '{url}'...")
    global http_requests_count
    if postdata:
        response = requests.post(url, json=postdata, **requests_kwargs)
    else:
        response = requests.get(url, timeout=REQUESTS_TIMEOUT, **requests_kwargs)
    http_requests_count += 1
    if handle_http_errors:
        if str(response.status_code)[0] in ("4", "5"):
            msg = f"Request failed with: '{response.status_code} {response.reason}'"
            if response.status_code in (502, 503, 504):
                raise HTTPError(msg)
            _log.warning(msg)
            return None

    return response


def request_json(url: str, **requests_kwargs) -> Json | list[Json]:
    response = timed_request(url, **requests_kwargs)
    if not response:
        return {}
    return response.json() if response.text else {}


@type_checker(str)
def getsoup(url: str, headers: Dict[str, str] | None = None) -> BeautifulSoup | None:
    """Return BeautifulSoup object based on ``url``.

    Args:
        url: URL string
        headers: a dictionary of headers to add to the request

    Returns:
        a BeautifulSoup object or None on client-side errors
    """
    response = timed_request(url, headers=headers)
    if not response or not response.text:
        return None
    http_encoding = response.encoding if 'charset' in response.headers.get(
        'content-type', '').lower() else None
    html_encoding = EncodingDetector.find_declared_encoding(response.content, is_html=True)
    encoding = html_encoding or http_encoding
    return BeautifulSoup(response.content, "lxml", from_encoding=encoding)


Throttling = namedtuple("Throttling", "delay offset")


def throttle(delay: float, offset=0.0) -> None:
    if offset:
        delay = round(random.uniform(delay - offset / 2, delay + offset / 2), 3)
    _log.info(f"Throttling for {delay} seconds...")
    time.sleep(delay)


def throttle_with_countdown(delay_seconds: int) -> None:
    for i in range(delay_seconds, 0, -1):
        print(f"Waiting {i} seconds before next batch...", end="\r")
        time.sleep(1)
    print("Ready for next batch!")


def throttled(delay: float, offset=0.0) -> Callable:
    """Add throttling delay after the decorated operation.

    Args:
        delay: throttling delay in fraction of seconds
        offset: randomization offset of the delay in fraction of seconds

    Returns:
        the decorated function
    """
    def decorate(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            throttle(delay, offset)
            return result
        return wrapper
    return decorate


@throttled(DEFAULT_THROTTLING)
def throttled_soup(url: str, headers: Dict[str, str] | None = None) -> BeautifulSoup | None:
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


@timed("unshortening")
def unshorten(url: str) -> str | None:
    """Unshorten URL shortened by services like bit.ly, tinyurl.com etc.

    courtesy of Phind AI
    """
    # set up retry mechanism
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    try:
        # set a reasonable timeout
        timeout = 10

        # add a User-Agent header to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # perform GET request instead of HEAD
        resp = session.get(url, allow_redirects=True, timeout=timeout, headers=headers)

        # check if the final URL is different from the original
        if resp.url != url:
            return resp.url
        else:
            # if no redirect occurred, try to parse the HTML for potential JavaScript redirects
            match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', resp.text)
            if match:
                return match.group(1)

        return None

    except requests.exceptions.SSLError:
        _log.warning(f"Unshortening of {url!r} failed with SSL error")
        return None
    except requests.exceptions.TooManyRedirects:
        _log.warning(f"Unshortening of {url!r} failed due too many redirections")
        return None
    except requests.exceptions.RequestException as e:
        _log.warning(f"Unshortening of {url!r} failed with : {str(e)}")
        return None


def extract_url(text: str, https=True) -> str | None:
    """Extract (the first occurrence of) URL from ``text``.

    Pilfered from: https://stackoverflow.com/a/840110/4465708
    """
    pattern = r"(?P<url>https?://[^\s'\"]+)" if https else r"(?P<url>http?://[^\s'\"]+)"
    match = re.search(pattern, text)
    if not match:
        return None
    url = match.group("url").rstrip("])}/")
    if url.count("https://") > 1:
        return "https://" + [part for part in url.split("https://") if part][0]
    elif url.count("http://") > 1:
        return "http://" + [part for part in url.split("http://") if part][0]
    return url


def extract_source(url: str) -> str:
    """Extract source domain from ``url``.
    """
    parts = [p for p in url.split("/") if p]
    source = parts[1] if "http" in parts[0] else parts[0]
    if "?" in source:
        source, _ = source.split("?", maxsplit=1)
    return source


def dissect_js(
        soup: BeautifulSoup, start_hook: str, end_hook: str,
        end_processor: Callable[[str], str] | None = None) -> Json | None:
    """Dissect JSON from JavaScript in ``soup``.
    """
    script_tag = soup.find("script", string=lambda s: s and start_hook in s and end_hook in s)
    if not script_tag:
        return None
    text = script_tag.text
    *_, first = text.split(start_hook)
    second, *_ = first.split(end_hook)
    if end_processor:
        second = end_processor(second)
    return json.loads(second)


def strip_url_params(url: str, with_endpoint=True) -> str:
    """Strip URL parameters from ``url``.

    https://www.youtube.com/watch?v=93gF1q7ey84 ==> https://www.youtube.com
    https://deckstats.net/?lng=en ==> https://deckstats.net

    Args:
        url: URL to be stripped
        with_endpoint: whether to strip any endpoint coming before parameters (part between "?" and the last "/", e.g.: "watch" in YT URLs)
    """
    if "?" in url:
        url, _ = url.split("?", maxsplit=1)
        if with_endpoint and "/" in url:
            first, _ = url.rsplit("/", maxsplit=1)
            if first not in ("https://", "http://"):
                url = first
    return url.removesuffix("/")


# SELENIUM


@timed("getting dynamic soup")
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
                    _accept_consent(driver, consent_xpath)
                else:
                    _accept_consent_without_wait(driver, consent_xpath)

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


@throttled(DEFAULT_THROTTLING)
def throttled_dynamic_soup_by_xpath(
        url: str, xpath: str, click=False, consent_xpath="", clipboard_xpath="",
        timeout=SELENIUM_TIMEOUT) -> tuple[BeautifulSoup, BeautifulSoup | None, str | None]:
    return get_dynamic_soup(url, xpath, click, consent_xpath, clipboard_xpath, timeout)


def _accept_consent(driver: WebDriver, xpath: str, timeout=SELENIUM_TIMEOUT) -> None:
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


def _accept_consent_without_wait(
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

