"""

    mtg.global.py
    ~~~~~~~~~~~~~
    Global state managers.

    @author: z33k

"""
from mtg.utils.check_type import type_checker


class UrlsStateManager:  # singleton
    """State manager for already scraped and failed URLs.
    """
    @property
    def current_channel(self) -> str:
        return self.__current_channel

    @current_channel.setter
    @type_checker(str, is_method=True, none_allowed=True)
    def current_channel(self, value: str | None) -> None:
        self.__current_channel = value

    @property
    def current_video(self) -> str:
        return self.__current_video

    @current_video.setter
    @type_checker(str, is_method=True, none_allowed=True)
    def current_video(self, value: str | None) -> None:
        self.__current_video = value

    def __init__(self) -> None:
        # pilfered this neat singleton solution from: https://stackoverflow.com/a/64545504/4465708
        self.__class__.__new__ = lambda _: self
        # init state
        self._scraped: dict[str, set[str]] = {}  # maps 'channel_id/video_id' path to set of URLs
        self._failed: dict[str, set[str]] = {}  # maps 'channel_id' to set of URLs
        self.current_channel, self.current_video = None, None

    def _get_scraped(self, channel_id="", video_id="") -> set[str]:
        if channel_id and video_id:
            return self._scraped.get(f"{channel_id}/{video_id}", set())
        if channel_id:
            return set(
                url for k, v in self._scraped.items() if k.startswith(channel_id) for url in v)
        if video_id:
            return set(
                url for k, v in self._scraped.items() if k.endswith(video_id) for url in v)
        return set(url for k, v in self._scraped.items() for url in v)

    def _get_failed(self, channel_id="") -> set[str]:
        return set(
            url for k, v in self._failed.items() if k == channel_id or not channel_id for url in v)

    # used by the scraping session to load initial global state from disk
    def update_scraped(self, data: dict[str, set[str]]) -> None:
        self._scraped.update(data)

    def update_failed(self, data: dict[str, set[str]]) -> None:
        self._failed.update(data)

    # used by the scraping session on finish
    def reset(self) -> None:
        self._scraped, self._failed = {}, {}
        self.current_channel, self.current_video = None, None

    # used by URL-based scrapers
    def add_scraped(self, url: str) -> None:
        self._scraped.setdefault(f"{self.current_channel}/{self.current_video}", set()).add(url)

    def add_failed(self, url: str) -> None:
        self._failed.setdefault(self.current_channel, set()).add(url)

    def is_scraped(self, url: str, channel_id="", video_id="") -> bool:
        return url in self._get_scraped(channel_id, video_id)

    def is_failed(self, url: str, channel_id="") -> bool:
        return url in self._get_failed(channel_id)

