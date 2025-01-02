"""

    mtg.utils.scrape.py
    ~~~~~~~~~~~~~~~~~~~
    Utilities for scraping.

    @author: z33k

"""
import contextlib
import json
import logging
import random
import re
import time
import urllib.parse
from collections import namedtuple
from functools import wraps
from typing import Callable

import brotli
import requests
from bs4 import BeautifulSoup
from bs4.dammit import EncodingDetector
from requests import Response
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError
from urllib3 import Retry

from mtg import Json
from mtg.utils import ParsingError, timed
from mtg.utils.check_type import type_checker

_log = logging.getLogger(__name__)
REQUESTS_TIMEOUT = 15.0  # seconds
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
        url: str, postdata: Json | None = None, handle_http_errors=True,
        request_timeout=REQUESTS_TIMEOUT,
        **requests_kwargs) -> Response | None:
    _log.info(f"Requesting: '{url}'...")
    global http_requests_count
    if postdata:
        response = requests.post(url, json=postdata, **requests_kwargs)
    else:
        response = requests.get(url, timeout=request_timeout, **requests_kwargs)
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
def getsoup(
        url: str, headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        request_timeout=REQUESTS_TIMEOUT) -> BeautifulSoup | None:
    """Return BeautifulSoup object based on ``url``.

    Args:
        url: URL string
        headers: a dictionary of headers to add to the request
        params: requests' query parameters
        request_timeout: request timeout in seconds

    Returns:
        a BeautifulSoup object or None on client-side errors
    """
    response = timed_request(url, headers=headers, params=params, request_timeout=request_timeout)
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
def throttled_soup(url: str, headers: dict[str, str] | None = None) -> BeautifulSoup | None:
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
    url = match.group("url").rstrip("])}/\u2060").removesuffix("...").removesuffix("..")
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


def strip_url_params(url: str, keep_endpoint=True, keep_fragment=True) -> str:
    """Strip URL parameters from ``url``.

    https://www.youtube.com/watch?v=93gF1q7ey84 ==> https://www.youtube.com
    https://deckstats.net/?lng=en ==> https://deckstats.net

    Args:
        url: URL to be stripped
        keep_endpoint: whether to keep any endpoint coming before parameters (part between "?" and the last "/", e.g.: "watch" in YT URLs)
        keep_fragment: whether to keep any fragment coming after parameters (last part indicated by '#', e.g.: "#deck_Walker735" in https://www.mtgo.com/decklist/pauper-challenge-32-2024-11-0312703226#deck_Walker735)
    """
    fragment = ""
    if "#" in url:
        url, fragment = url.rsplit("#", maxsplit=1)
        fragment = "#" + fragment
    if "?" in url:
        url, _ = url.split("?", maxsplit=1)
        if not keep_endpoint and "/" in url:
            first, _ = url.rsplit("/", maxsplit=1)
            if first not in ("https://", "http://"):
                url = first
    url = url + fragment if keep_fragment else url
    return url.removesuffix("/")


def extract_url_endpoint(url: str) -> str:
    """Extract endpoint from ``url`` (part between "?" (if present) and the last "/", e.g.: "watch"
    in YT URLs).
    """
    url = url.removesuffix("/")
    if "?" in url:
        url, _ = url.split("?", maxsplit=1)
    if "/" in url:
        _, endpoint = url.rsplit("/", maxsplit=1)
        return endpoint
    return ""


def url_decode(encoded: str) -> str:
    """Decode URL-encoded string.

    Example:
        ""Virtue+of+Loyalty+%2F%2F+Ardenvale+Fealty"" ==> "Virtue of Loyalty // Ardenvale Fealty"
    """
    return urllib.parse.unquote(encoded.replace('+', ' '))
