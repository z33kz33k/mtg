"""

    mtgcards.yt.py
    ~~~~~~~~~~~~~~
    Handle YouTube data.

    @author: z33k

"""
from datetime import datetime
from typing import List

from scrapetube import get_channel
from pytube import YouTube
from py_youtube import Data as PyYtData

from mtgcards.const import Json


class Video:
    URL_TEMPLATE = "https://www.youtube.com/watch?v={}"

    @property
    def id(self) -> str:
        return self._scrapetube_data["videoId"]

    @property
    def author(self) -> str:
        return self._pytube_data.author

    @property
    def description(self) -> str:
        return self._pytube_data.description

    @property
    def keywords(self) -> List[str]:
        return self._pytube_data.keywords

    @property
    def published_date(self) -> datetime:
        return self._pytube_data.publish_date

    @property
    def title(self) -> str:
        return self._pytube_data.title

    @property
    def views(self) -> int:
        return self._pytube_data.views

    def __init__(self, scrapetube_data: Json) -> None:
        self._scrapetube_data = scrapetube_data
        self._pytube_data = YouTube(self.URL_TEMPLATE.format(self.id))


class Channel(list):
    @property
    def subscribers(self) -> int:
        return self._subscribers

    def __init__(self, url: str, limit=30) -> None:
        try:
            videos = [*get_channel(channel_url=url, limit=limit)]
        except OSError:
            raise ValueError(f"Invalid URL: {url!r}")
        super().__init__([Video(data) for data in videos])
        self._pyyt_data = PyYtData(url).data()
        self._subscribers = self._parse_subscribers()

    def _parse_subscribers(self) -> int:
        text = self._pyyt_data["subscriber"].replace(",", ".")
        digits = [char for char in text if char.isdigit() or char == "."]
        subscribers = float("".join(digits))
        if "tys" in text:
            subscribers *= 1000
        return int(subscribers)





