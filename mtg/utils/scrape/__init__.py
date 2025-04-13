"""

    mtg.utils.scrape.__init__.py
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
from datetime import date, datetime
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Iterator, Self

import backoff
import brotli
import requests
from bs4 import BeautifulSoup, Tag
from bs4.dammit import EncodingDetector
from requests import Response
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError
from urllib3 import Retry
from wayback import WaybackClient
from wayback.exceptions import MementoPlaybackError, WaybackRetryError, WaybackException

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


def handle_brotli(response: Response, return_json: bool = False) -> str | Json:
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


def request_json(url: str, handle_http_errors=True, **requests_kwargs) -> Json:
    response = timed_request(url, handle_http_errors=handle_http_errors, **requests_kwargs)
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


def get_next_sibling_tag(tag: Tag) -> Tag | None:
    for sibling in tag.next_siblings:
        if isinstance(sibling, Tag):
            return sibling
    return None


def get_previous_sibling_tag(tag: Tag) -> Tag | None:
    for sibling in tag.previous_siblings:
        if isinstance(sibling, Tag):
            return sibling
    return None


@dataclass
class Throttling:
    delay: float
    offset: float

    def __mul__(self, factor: float) -> Self:
        return Throttling(self.delay * factor, self.offset * factor)

    def __imul__(self, factor) -> Self:
        return Throttling(self.delay * factor, self.offset * factor)

    def __iter__(self) -> Iterator[float]:
        return iter((self.delay, self.offset))


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
    url = match.group("url").rstrip(",])}/\u2060").removesuffix("...").removesuffix("..")
    if url.count("https://") > 1:
        return "https://" + [part for part in url.split("https://") if part][0]
    elif url.count("http://") > 1:
        return "http://" + [part for part in url.split("http://") if part][0]
    elif all(not url.startswith(t) for t in ("https://", "http://")) or len(url) < 10:
        return None
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
        tag: Tag, start_hook: str, end_hook: str,
        end_processor: Callable[[str], str] | None = None,
        left_split_on_start_hook=False) -> Json | None:
    """Dissect JSON from JavaScript in ``tag``.
    """
    if tag.name == "script":
        script_tag = tag
    else:
        script_tag = tag.find("script", string=lambda s: s and start_hook in s and end_hook in s)
    if not script_tag:
        return None
    text = script_tag.text
    if left_split_on_start_hook:
        _, first = text.split(start_hook, maxsplit=1)
    else:
        *_, first = text.split(start_hook)
    second, *_ = first.split(end_hook)
    if end_processor:
        second = end_processor(second)
    return json.loads(second)


def strip_url_query(url: str, keep_fragment=False) -> str:
    """Strip query parameters from the URL.

    https://www.youtube.com/watch?v=93gF1q7ey84 ==> https://www.youtube.com/watch
    https://deckstats.net/?lng=en ==> https://deckstats.net

    Args:
        url: URL to be stripped
        keep_fragment: whether to keep the fragment part of the URL

    Returns:
        URL with query parameters removed
    """
    # split the URL into its components
    parsed_url = urllib.parse.urlsplit(url)

    # reconstruct the URL without query parameters
    stripped_url = urllib.parse.urlunsplit((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path.removesuffix('/'),  # remove any trailing slash
        '',  # remove query
        parsed_url.fragment if keep_fragment else ''  # keep or remove fragment
    ))

    return stripped_url.removesuffix("/")


def trim_url(url: str, level=0, keep_scheme=False) -> str:
    """Trim URL to domain (level=0) or any subfolders after it (level>0).
    """
    if not "/" in url:
        return url
    if url.startswith("https://"):
        scheme = "https://"
    elif url.startswith("http://"):
        scheme = "http://"
    else:
        scheme = ""
    url = url.removeprefix("https://").removeprefix("http://").removesuffix("/")
    parts = url.split("/")
    trimmed, *rest = parts
    if not rest:
        return scheme + trimmed if keep_scheme else trimmed
    while rest and level > 0:
        if "(" in rest:
            return trimmed + "/" + rest
        trimmed += "/" + rest.pop(0)
        level -= 1
    return scheme + trimmed if keep_scheme else trimmed


def url_decode(encoded: str) -> str:
    """Decode URL-encoded string.

    Example:
        ""Virtue+of+Loyalty+%2F%2F+Ardenvale+Fealty"" ==> "Virtue of Loyalty // Ardenvale Fealty"
    """
    return urllib.parse.unquote(encoded.replace('+', ' '))


MONTHS = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December'
]


def parse_non_english_month_date(date_text: str, *months: str) -> date:
    """Parse a datetime.date object from a date text containing a non-English month.

    Args:
        date_text: date text to be parsed
        months: non-English month names (from January to December)
    """
    if not len(months) == 12:
        raise ValueError(f"Expected 12 months, got {len(months)}")
    month_smap = {m1.title(): m2 for m1, m2 in zip(months, MONTHS)}
    day, month, year = date_text.split()
    day = day.strip('.')
    if month in MONTHS:
        english_month = month
    else:
        # convert month to English
        english_month = month_smap.get(month)
        if not english_month:
            raise ValueError(f"Unknown month: {month}")
    # create a date string in a format that can be parsed by strptime
    english_date_string = f"{day} {english_month} {year}"
    # parse the date
    return datetime.strptime(english_date_string, "%d %B %Y").date()


def prepend_url(url: str, prefix="") -> str:
    """Prepend ``url`` with prefix provided (only if needed).
    """
    if prefix:
        return f"{prefix}{url}" if not (url.startswith(prefix) or url.startswith("http")) else url
    return url


def get_links(
        *tags: Tag, css_selector="", url_prefix="", query_stripped=False,
        **bs_options) -> list[str]:
    """Get all links from provided tags.

        Args:
            *tags: variable number of BeautifulSoup tags containing links
            css_selector: CSS selector to obtain links from a tag
            url_prefix: prefix to add to relative URLs
            query_stripped: whether to strip the query part of the URL
            **bs_options: options to pass to BeautifulSoup's find_all() method for better filtering
        """
    links = set()
    for tag in tags:
        if css_selector:
            links |= {t.attrs["href"].removesuffix("/") for t in tag.select(css_selector)}
        else:
            bs_options = bs_options or {"href": lambda h: h}
            links |= {t.attrs["href"].removesuffix("/") for t in tag.find_all("a", **bs_options)}
    links = {prepend_url(l, url_prefix) for l in links} if url_prefix else links
    links = {strip_url_query(l) for l in links} if query_stripped else links
    return sorted(links)


def _wayback_predicate(soup: BeautifulSoup | None) -> bool:
    if soup and "Error connecting to database" in str(soup):
        _log.warning(
            "Problems with connecting to Internet Archive's database. Re-trying with backoff...")
        return True
    return False


@timed("getting wayback soup")
@backoff.on_predicate(
    backoff.expo,
    predicate=_wayback_predicate,
    jitter=None,
    max_tries=7
)
def get_wayback_soup(url: str) -> BeautifulSoup | None:
    """Get BeautifulSoup object for a URL from Wayback Machine.
    """
    try:
        client = WaybackClient()
        _log.info(f"Searching for {url!r} in Wayback Machine...")
        if memento := next(client.search(url, limit=-1, fast_latest=True), None):
            try:
                response = client.get_memento(memento, exact=False)
            except MementoPlaybackError:
                _log.warning(f"Wayback Machine memento for {url!r} could not be retrieved")
                return None
            return BeautifulSoup(response.text, "lxml")
        return None
    except (WaybackException, WaybackRetryError) as e:
        _log.warning(f"Wayback Machine failed with: {e}")
        return None
