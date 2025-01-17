"""

    mtg.gstate.py
    ~~~~~~~~~~~~~
    Global state managers.

    @author: z33k

"""
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from mtg import OUTPUT_DIR
from mtg.utils.check_type import type_checker
from mtg.utils.files import getfile
from mtg.utils.scrape import throttle_with_countdown

_log = logging.getLogger(__name__)
CHANNELS_DIR = OUTPUT_DIR / "channels"
REGULAR_DECKLISTS_FILE = CHANNELS_DIR / "regular_decklists.json"
EXTENDED_DECKLISTS_FILE = CHANNELS_DIR / "extended_decklists.json"
FAILED_URLS_FILE = CHANNELS_DIR / "failed_urls.json"


class _Singleton(ABC):
    _initialized = False

    def __init__(self) -> None:
        if not self.__class__._initialized:
            # pilfered this neat singleton solution from: https://stackoverflow.com/a/64545504/4465708
            self.__class__.__new__ = lambda _: self
            # init state
            self.reset()
            self.__class__._initialized = True

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError


class UrlsStateManager(_Singleton):
    """State manager for already scraped and failed URLs.

    Scraped URLs are stored within deck data and their initial state is loaded from there by third
    parties and only injected here via 'update_scraped()' method. This object tracks dynamically
    changing state afterward.

    Failed URLs on the other hand are stored in their own dedicated file and both this file's
    management and the dynamic state of the URLs are a responsibility of this object.
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

    def load_failed(self) -> None:
        if self._initial_failed_count:
            _log.warning("Failed URLs already loaded")
            return
        src = getfile(FAILED_URLS_FILE)
        self._failed = {k: set(v) for k, v in json.loads(src.read_text(
                encoding="utf-8")).items()}
        self._initial_failed_count = self.failed_count
        _log.info(
            f"Loaded {self._initial_failed_count:,} decklist URL(s) that previously failed from "
            f"the global repository")

    def dump_failed(self) -> None:
        dst = Path(FAILED_URLS_FILE)
        dst.write_text(
            json.dumps({k: sorted(v) for k, v in self.failed.items()}, indent=4,
                       ensure_ascii=False), encoding="utf-8")
        _log.info(
            f"Total of {self.failed_count - self._initial_failed_count:,} newly failed decklist "
            f"URLs added to the global repository to be avoided in the future")

    # used by the scraping session on finish
    def reset(self) -> None:  # override
        self._scraped: dict[str, set[str]] = {}  # maps 'channel_id/video_id' path to set of URLs
        self._failed: dict[str, set[str]] = {}  # maps 'channel_id' to set of URLs
        self.current_channel, self.current_video = "", ""
        self.ignore_scraped, self.ignore_scraped_within_current_video = False, False
        self._initial_failed_count = 0

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


class DecklistsStateManager(_Singleton):
    """State manager for decklists stored in separately from deck data.

    MTGO/Arena text format decklists mapped to their hash digest IDs are stored in two files: one
    for regular decklists and the second for decklists in 'extended' form (i.e. where each line
    specifies also a set code and card's collector number - this detail makes a deck specific in
    terms of card prints).

    Storing decklists in that way makes keeping only hash digests IDs (instead of whole
    decklists) in the deck data possible and, thus, cuts down data bloat due to decklists
    duplication across the scraped decks.
    """
    @property
    def regular(self) -> dict[str, str]:
        return dict(self._regular)

    @property
    def extended(self) -> dict[str, str]:
        return dict(self._extended)

    def reset(self) -> None:  # override
        self._regular: dict[str, str] = {}
        self._extended: dict[str, str] = {}
        self._initial_regular_count, self._initial_extended_count = 0, 0

    def load(self) -> None:
        if self._initial_regular_count or self._initial_extended_count:
            _log.warning("Decklists already loaded")
            return
        regular_src, extended_src = getfile(REGULAR_DECKLISTS_FILE), getfile(
            EXTENDED_DECKLISTS_FILE)
        self._regular = json.loads(regular_src.read_text(encoding="utf-8"))
        self._initial_regular_count = len(self._regular)
        _log.info(
            f"Loaded {self._initial_regular_count:,} regular decklist(s) from the global "
            f"repository")
        self._extended = json.loads(extended_src.read_text(encoding="utf-8"))
        self._initial_extended_count = len(self._extended)
        _log.info(
            f"Loaded {self._initial_extended_count:,} extended decklist(s) from the global "
            f"repository")

    def dump(self) -> None:
        regular_dst, extended_dst = Path(REGULAR_DECKLISTS_FILE), Path(EXTENDED_DECKLISTS_FILE)
        regular_count, extended_count = len(self._regular), len(self._extended)
        _log.info(f"Dumping {regular_count:,} decklist(s) to '{regular_dst}'...")
        regular_dst.write_text(
            json.dumps(self._regular, indent=4, ensure_ascii=False), encoding="utf-8")
        _log.info(f"Dumping {extended_count:,} decklist(s) to '{extended_dst}'...")
        extended_dst.write_text(
            json.dumps(self._extended, indent=4, ensure_ascii=False),encoding="utf-8")
        _log.info(
            f"Total of {regular_count - self._initial_regular_count:,} unique regular "
            f"decklist(s) added to the global repository")
        _log.info(
            f"Total of {extended_count - self._initial_extended_count:,} unique extended "
            f"decklist(s) added to the global repository")

    def add_regular(self, decklist_id: str, decklist: str) -> None:
        self._regular[decklist_id] = decklist

    def add_extended(self, decklist_id: str, decklist: str) -> None:
        self._extended[decklist_id] = decklist

    def retrieve(self, decklist_id: str) -> str | None:
        if not self._regular or not self._extended:
            _log.warning("No decklists. Are you sure you loaded them?")
        return self._regular.get(decklist_id) or self._extended.get(decklist_id)

    def prune(self, filter_: Callable[[str], bool]) -> None:
        """Prune all decklists that match the given filter.

        Args:
            filter_: a function that takes a decklist ID and returns a boolean.
        """
        self._regular = {k: v for k, v in self._regular.items() if not filter_(k)}
        self._extended = {k: v for k, v in self._extended.items() if not filter_(k)}


class CoolOffManager(_Singleton):
    """Keeps the things cool (with YT and pytube).
    """
    MAX_VIDEOS = 400

    @property
    def total_decks(self) -> int:
        return self._total_decks

    @property
    def total_videos(self) -> int:
        return self._total_videos

    @property
    def total_channels(self) -> int:
        return self._total_channels

    def reset(self) -> None:  # override
        self._total_decks, self._total_videos, self._total_channels = 0, 0, 0
        self._current_videos = 0

    def _cool_off(self) -> None:
        _log.info(f"Throttling for 5 minutes before the next batch...")
        throttle_with_countdown(5 * 60)
        self._current_videos = 0

    def bump_decks(self, decks: int) -> None:
        self._total_decks += decks

    def bump_channel(self) -> None:
        self._total_channels += 1

    def bump_video(self) -> None:
        self._total_videos += 1
        self._current_videos += 1
        if self._current_videos >= self.MAX_VIDEOS:
            self._cool_off()
