"""

    mtg.yt.ptfix
    ~~~~~~~~~~~~
    Try to retrieve video details from pytubefix data more robustly than pytubefix does.

    @author: z33k

"""
import contextlib
from dataclasses import dataclass
from datetime import datetime

import pytubefix
import pytubefix.exceptions
from bs4 import BeautifulSoup

from mtg.utils import extract_int
from mtg.utils.json import Node
from mtg.utils.scrape import parse_keywords_from_tag


@dataclass
class PytubeData:
    author: str
    description: str
    title: str
    keywords: list[str]
    views: int


class PytubefixError(OSError):
    """Raised on pytubefix failing to retrieve expected data.
    """


class PytubeWrapper:
    """Wrap `pytubefix.YouTube` object to retrieve video details data more robustly than it does.
    """
    @property
    def publish_time(self) -> datetime:
        return self._pytube.publish_date

    @property
    def channel_id(self) -> str:
        return self._pytube.channel_id

    @property
    def embed_html(self) -> str:
        return self._pytube.embed_html

    @property
    def watch_html(self) -> str:
        return self._pytube.watch_html

    @property
    def data(self) -> PytubeData | None:
        return self._data

    def __init__(self, pytube: pytubefix.YouTube) -> None:
        self._pytube, self._data = pytube, None
        if not self._pytube.vid_info:
            raise PytubefixError(
                f"pytubefix 'vid_info' dict unavailable for video: {self._pytube.watch_url!r}")
        if not self._pytube.vid_details:
            raise PytubefixError(
                f"pytubefix 'vid_details' dict unavailable for video: {self._pytube.watch_url!r}")
        if not self._pytube.channel_id:
            raise PytubefixError(
                f"Channel ID unavailable for video: {self._pytube.watch_url!r}")
        self._nvi, self._nvd = Node(self._pytube.vid_info), Node(self._pytube.vid_details)

    def _retrieve_author(self) -> str:
        with contextlib.suppress(KeyError, pytubefix.exceptions.PytubeFixError):
            if self._pytube.author is not None and self._pytube.author != "unknown":
                return self._pytube.author
        path = "['videoOwnerRenderer']['title']['simpleText']"
        if author := self._nvd.find_by_path(path, mode="end"):
            return author.data
        raise PytubefixError(f"Unable to retrieve author data for: {self._pytube.watch_url!r}")

    def _retrieve_description(self) -> str:
        with contextlib.suppress(KeyError, pytubefix.exceptions.PytubeFixError):
            if self._pytube.description is not None and self._pytube.description != "unknown":
                return self._pytube.description
        path = "['shortDescription']"
        if desc := self._nvi.find_by_path(path, mode="end"):
            return desc.data
        if desc := self._nvd.find_by_path(path, mode="end"):
            return desc.data
        path = "['attributedDescription']['content']"
        if desc := self._nvi.find_by_path(path, mode="end"):
            return desc.data
        if desc := self._nvd.find_by_path(path, mode="end"):
            return desc.data
        path = "['descriptionBodyText']['runs'][0]['text']"
        if desc := self._nvd.find_by_path(path, mode="end"):
            return desc.data
        raise PytubefixError(f"Unable to retrieve description data for: {self._pytube.watch_url!r}")

    def _retrieve_title(self) -> str:
        with contextlib.suppress(KeyError, pytubefix.exceptions.PytubeFixError):
            if self._pytube.title is not None and self._pytube.title != "unknown":
                return self._pytube.title
        path = "['videoDescriptionHeaderRenderer']['title']['runs'][0]['text']"
        if title := self._nvd.find_by_path(path, mode="end"):
            return title.data
        raise PytubefixError(f"Unable to retrieve title data for: {self._pytube.watch_url!r}")

    def _retrieve_keywords(self) -> list[str]:
        keywords = self._pytube.vid_info.get('videoDetails', {}).get('keywords')
        if isinstance(keywords, list):
            return keywords
        soup = BeautifulSoup(self.watch_html, "lxml")
        if kw_tag := soup.find("meta", {'name': 'keywords'}):
            return parse_keywords_from_tag(kw_tag)
        soup = BeautifulSoup(self.embed_html, "lxml")
        if kw_tag := soup.find("meta", {'name': 'keywords'}):
            return parse_keywords_from_tag(kw_tag)
        raise PytubefixError(f"Unable to retrieve keywords data for: {self._pytube.watch_url!r}")

    def _retrieve_views(self) -> int:
        with contextlib.suppress(KeyError, pytubefix.exceptions.PytubeFixError):
            if self._pytube.views is not None and self._pytube.views != "unknown":
                return self._pytube.views
        higher_path = "['videoMetadataRenderer']['viewCount']['videoViewCountRenderer']['viewCount']"
        if higher_node := self._nvd.find_by_path(higher_path, mode="end"):
            if "simpleText" in higher_node.data:
                data = higher_node.data["simpleText"]
                return extract_int(data) if data != "No views" else 0
            # views have status 'waiting'
            if node := higher_node.find_by_path("['runs'][0]['text']", mode="end"):
                return extract_int(node.data) if node.data != "No views" else 0
            # members-only video
            if higher_node.data == {}:
                return 0
        path = "['videoDescriptionHeaderRenderer']['views']['simpleText']"
        if node := self._nvd.find_by_path(path, mode="end"):
            return extract_int(node.data) if node.data != "No views" else 0
        if self._nvd.find(
                lambda n: isinstance(n.data, str) and n.data in ("Members only", "Members first")):
            return 0
        # no views
        if node := self._nvd.find_by_path("['videoMetadataRenderer']['viewCountText']", mode="end"):
            if node.data == {}:
                return 0
        raise PytubefixError(f"Unable to retrieve views data for: {self._pytube.watch_url!r}")

    def retrieve(self) -> None:
        author = self._retrieve_author()
        desc = self._retrieve_description()
        title = self._retrieve_title()
        keywords = self._retrieve_keywords()
        views = self._retrieve_views()
        self._data = PytubeData(author, desc, title, keywords, views)
