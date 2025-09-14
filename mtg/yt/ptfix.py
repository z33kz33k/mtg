"""

    mtg.yt.ptfix
    ~~~~~~~~~~~~
    Try to retrieve video metadata from pytubefix data more robustly than pytubefix does.

    @author: z33k

"""
import contextlib
from dataclasses import dataclass

import pytubefix
import pytubefix.exceptions
from bs4 import BeautifulSoup

from mtg.utils.json import Node


@dataclass(frozen=True)
class PytubeData:
    author: str
    description: str
    title: str
    keywords: list[str]
    views: int


class PytubefixError(OSError):
    """Raised on pytubefix failing to retrieve expected data.
    """


class Retriever:
    def __init__(self, pytube: pytubefix.YouTube) -> None:
        self._pytube = pytube
        if not self._pytube.vid_info:
            raise PytubefixError(
                f"pytubefix 'vid_info' dict unavailable for video: {self._pytube.watch_url!r}")
        if not self._pytube.vid_details:
            raise PytubefixError(
                f"pytubefix 'vid_details' dict unavailable for video: {self._pytube.watch_url!r}")
        self._nvi, self._nvd = Node(self._pytube.vid_info), Node(self._pytube.vid_details)

    def _retrieve_author(self) -> str:
        if self._pytube.author is not None and self._pytube.author != "unknown":
            return self._pytube.author
        path = "['owner']['videoOwnerRenderer']['title']['simpleText']"
        if author := self._nvi.find_by_path(path, mode="end"):
            return author.data
        if author := self._nvd.find_by_path(path, mode="end"):
            return author.data
        raise PytubefixError(f"Unable to retrieve author data for: {self._pytube.watch_url!r}")

    def _retrieve_description(self) -> str:
        with contextlib.suppress(KeyError):
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
        if desc := self._nvi.find_by_path(path, mode="end"):
            return desc.data
        if desc := self._nvd.find_by_path(path, mode="end"):
            return desc.data
        raise PytubefixError(f"Unable to retrieve description data for: {self._pytube.watch_url!r}")

    def _retrieve_title(self) -> str:
        with contextlib.suppress(KeyError, pytubefix.exceptions.PytubeFixError):
            if self._pytube.title is not None and self._pytube.title != "unknown":
                return self._pytube.title
        path = "['videoDescriptionHeaderRenderer']['title']['runs'][0]['text']"
        if title := self._nvi.find_by_path(path, mode="end"):
            return title.data
        if title := self._nvd.find_by_path(path, mode="end"):
            return title.data
        raise PytubefixError(f"Unable to retrieve title data for: {self._pytube.watch_url!r}")

    # def _retrieve_keywords(self) -> list[str]:
    #     keywords = self._pytube.vid_info.get('videoDetails', {}).get('keywords')
    #     if isinstance(keywords, list):
    #         return keywords
    #     soup = BeautifulSoup(self._pytube.watch_url, "lxml")
    #     if kw_tag := soup.find("meta", {'name': 'keywords'}):
    #         return [kw.strip() for kw in kw_tag['content'].split(',')]
    #     raise PytubefixError(f"Unable to retrieve keywords data for: {self._pytube.watch_url!r}")
