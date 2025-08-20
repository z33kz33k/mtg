"""

    mtg.utils.linktree
    ~~~~~~~~~~~~~~~~~~
    linktr.ee scraper based on: https://github.com/Touexe/LinkTreeScraper and heavily adapted to
    suit my needs.

    MIT License

    Copyright (c) 2021 Tou

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

"""
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import backoff
from requests import ReadTimeout, HTTPError, ConnectionError

from mtg import Json
from mtg.utils.scrape import ScrapingError, fetch_soup, strip_url_query, fetch

_log = logging.getLogger(__name__)


@dataclass
class Linktree:
    username : str | None
    url : str
    id : int
    is_active : bool | None
    created_at: datetime | None
    updated_at: datetime | None
    avatar_image : str | None
    description : str | None
    links : list[str]


class LinktreeScraper:
    HEADERS = {
        "origin": "https://linktr.ee",
        "referer": "https://linktr.ee",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "
                      "like Gecko) Chrome/91.0.4472.77 Safari/537.36"
    }

    @property
    def url(self) -> str:
        return self._url

    @property
    def data(self) -> Linktree:
        return self._data

    def __init__(self, url: str) -> None:
        if not self.is_linktree_url(url):
            raise ValueError(f"Not a linktr.ee URL: {url!r}")
        self._url = strip_url_query(url)
        self._json_data = self._get_json()
        try:
            self._account_id = self._json_data["account"]["id"]
        except KeyError:
            raise ScrapingError(
                "Account ID missing from JSON data", scraper=type(self), url=self.url)
        self._links = self._get_links()
        self._data = self._get_data()

    @staticmethod
    def is_linktree_url(url: str) -> bool:
        return "linktr.ee/" in url.lower()

    @backoff.on_exception(backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def _get_json(self) -> Json:
        soup = fetch_soup(self.url, self.HEADERS)
        if not soup:
            raise ScrapingError(scraper=type(self), url=self.url)
        user_info_tag = soup.find('script', id="__NEXT_DATA__")
        if user_info_tag is None:
            raise ScrapingError("Data <script> tag not found", scraper=type(self), url=self.url)
        return json.loads(user_info_tag.contents[0])["props"]["pageProps"]

    def _uncensor_links(self, *link_ids : int) -> list[str]:
        if not link_ids:
            return []

        data = {
            "accountId": self._account_id,
            "validationInput": {
                "acceptedSensitiveContent": [*link_ids]
            },
            "requestSource": {
                "referrer": None
            }
        }
        url = "https://linktr.ee/api/profiles/validation/gates"
        try:
            resp = fetch(url, postdata=data, headers=self.HEADERS)
            return [link["url"] for link in resp.json()["links"]]
        except Exception as e:
            _log.warning(f"linktr.ee links uncensoring failed with: {e!r}")
            return []

    def _get_links(self) -> list[str]:
        json_links = self._json_data["links"]

        links = []
        censored_link_ids = []

        for link_data in json_links:
            url = link_data["url"]

            if link_data["type"] == "COMMERCE_PAY":
                continue

            if not url and link_data["locked"]:
                censored_link_ids.append(link_data["id"])
                continue

            if url:
                links.append(url)

        links.extend(self._uncensor_links(*censored_link_ids))
        return links


    def _get_data(self)-> Linktree:
        data = self._json_data["account"]
        created, updated = data.get("createdAt"), data.get("updatedAt")

        return Linktree(
            data.get("username"),
            self.url,
            self._account_id,
            data.get("isActive"),
            datetime.fromtimestamp(created / 1000, UTC) if created else None,
            datetime.fromtimestamp(updated / 1000, UTC) if updated else None,
            data.get("profilePictureUrl"),
            data.get("description"),
            self._links
        )
