"""

    mtg.gstate.py
    ~~~~~~~~~~~~~
    Global state managers.

    @author: z33k

"""
import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from mtg.utils.check_type import type_checker
from mtg.utils.files import getfile


_log = logging.getLogger(__name__)


class UrlsStateManager:  # singleton
    """State manager for already scraped and failed URLs.
    """
    @property
    def current_channel(self) -> str:
        return self.__current_channel

    @current_channel.setter
    @type_checker(str, is_method=True)
    def current_channel(self, value: str) -> None:
        self.__current_channel = value

    @property
    def current_video(self) -> str:
        return self.__current_video

    @current_video.setter
    @type_checker(str, is_method=True)
    def current_video(self, value: str) -> None:
        self.__current_video = value

    @property
    def ignore_scraped(self) -> bool:
        return self.__ignore_scraped

    @ignore_scraped.setter
    @type_checker(bool, is_method=True)
    def ignore_scraped(self, value: bool) -> None:
        self.__ignore_scraped = value

    @property
    def ignore_scraped_within_current_video(self) -> bool:
        return self.__ignore_scraped_within_current_video

    @ignore_scraped_within_current_video.setter
    @type_checker(bool, is_method=True)
    def ignore_scraped_within_current_video(self, value: bool) -> None:
        self.__ignore_scraped_within_current_video = value

    @property
    def failed(self) -> dict[str, set[str]]:
        return dict(self._failed)

    @property
    def failed_count(self) -> int:
        return sum(len(v) for v in self._failed.values())

    _initialized = False

    def __init__(self) -> None:
        if not UrlsStateManager._initialized:
            # pilfered this neat singleton solution from: https://stackoverflow.com/a/64545504/4465708
            self.__class__.__new__ = lambda _: self
            # init state
            self._scraped: dict[str, set[str]] = {}  # maps 'channel_id/video_id' path to set of URLs
            self._failed: dict[str, set[str]] = {}  # maps 'channel_id' to set of URLs
            self.current_channel, self.current_video = "", ""
            self.ignore_scraped, self.ignore_scraped_within_current_video = False, False
            self._initial_failed_count = 0
            UrlsStateManager._initialized = True

    def _get_scraped(self, channel_id: str, video_id="") -> set[str]:
        if channel_id and video_id:
            return self._scraped.get(f"{channel_id}/{video_id}", set())
        return self._scraped.get(channel_id, set())

    # used by the ScrapingSession/Channel to load initial global state from disk
    def update_scraped(self, data: dict[str, set[str]]) -> None:
        self._scraped.update(
            {k: {url.removesuffix("/").lower() for url in v} for k, v in data.items()})

    def update_failed(self, data: dict[str, set[str]]) -> None:
        self._failed.update(
            {k: {url.removesuffix("/").lower() for url in v} for k, v in data.items()})

    def load_failed(self, failed_urls_repo: str) -> None:
        if self._initial_failed_count:
            _log.warning("Failed URLs already loaded")
            return
        failed_urls_repo = getfile(failed_urls_repo)
        self._failed = {k: set(v) for k, v in json.loads(failed_urls_repo.read_text(
                encoding="utf-8")).items()}
        self._initial_failed_count = self.failed_count
        _log.info(
            f"Loaded {self._initial_failed_count:,} decklist URL(s) that previously failed from "
            f"the global repository")

    def dump_failed(self, failed_urls_repo: str) -> None:
        failed_urls_repo = Path(failed_urls_repo)
        failed_urls_repo.write_text(
            json.dumps({k: sorted(v) for k, v in self.failed.items()}, indent=4,
                       ensure_ascii=False), encoding="utf-8")
        _log.info(
            f"Total of {self.failed_count - self._initial_failed_count:,} newly failed decklist "
            f"URLs added to the global repository to be avoided in the future")

    # used by the scraping session on finish
    def reset(self) -> None:
        self._scraped, self._failed = {}, {}
        self.current_channel, self.current_video = "", ""
        self.ignore_scraped = False
        self.ignore_scraped_within_current_video = False

    # used by URL-based scrapers
    def add_scraped(self, url: str) -> None:
        self._scraped.setdefault(self.current_channel, set()).add(url.removesuffix("/").lower())
        self._scraped.setdefault(
            f"{self.current_channel}/{self.current_video}",
            set()).add(url.removesuffix("/").lower())

    def add_failed(self, url: str) -> None:
        self._failed.setdefault(self.current_channel, set()).add(url.removesuffix("/").lower())

    def _is_scraped_within(self, url: str, channel_id="", video_id="") -> bool:
        if self.ignore_scraped:
            return False
        return url.removesuffix("/").lower() in self._get_scraped(channel_id, video_id)

    def is_scraped(self, url: str) -> bool:
        url = url.removesuffix("/").lower()
        if self.ignore_scraped_within_current_video and self._is_scraped_within(
            url, self.current_channel, self.current_video):
            return False
        return self._is_scraped_within(url, self.current_channel)

    def is_failed(self, url: str) -> bool:
        return url.removesuffix("/").lower() in self._failed.get(self.current_channel, set())


@contextmanager
def ignore_already_scraped_urls() -> Generator[UrlsStateManager, None, None]:
    usm = UrlsStateManager()
    usm.ignore_scraped = True
    yield usm
    usm.ignore_scraped = False


@contextmanager
def ignore_already_scraped_urls_within_current_video() -> Generator[UrlsStateManager, None, None]:
    usm = UrlsStateManager()
    usm.ignore_scraped_within_current_video = True
    yield usm
    usm.ignore_scraped_within_current_video = False

