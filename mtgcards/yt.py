"""

    mtgcards.yt.py
    ~~~~~~~~~~~~~~
    Handle YouTube data.

    @author: z33k

"""
import re

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Set, Tuple

import requests
from scrapetube import get_channel
from pytube import YouTube
from youtubesearchpython import Channel as YtspChannel

from mtgcards.const import Json
from mtgcards.utils import getrepr


class ArenaLine:
    """A line of text in MtG Arena decklist format that denotes a card.

    Example:
        '4 Commit /// Memory (AKR) 54'
    """
    # matches '4 Commit /// Memory'
    PATTERN = re.compile(r"\d\s[A-Z][\w\s'&/-]+")
    # matches ''4 Commit /// Memory (AKR) 54''
    EXTENDED_PATTERN = re.compile(r"\d\s[A-Z][\w\s'&/-]+\([A-Z\d]{3}\)\s\d+")

    @property
    def raw_line(self) -> str:
        return self._raw_line

    @property
    def index(self) -> int:
        return self._index

    @property
    def is_extended(self) -> bool:
        return self._is_extended

    @property
    def quantity(self) -> int:
        return self._quantity

    @property
    def name(self) -> str:
        return self._name

    @property
    def setcode(self) -> Optional[str]:
        return self._setcode

    @property
    def collector_number(self) -> Optional[str]:
        return self._collector_number

    def __init__(self, line: str, idx: int) -> None:
        self._raw_line, self._index = line, idx
        self._is_extended = self.EXTENDED_PATTERN.match(line) is not None
        quantity, rest = line.split(maxsplit=1)
        self._quantity = int(quantity)
        if self.is_extended:
            self._name, rest = rest.split("(")
            self._name = self._name.strip()
            self._setcode, rest = rest.split(")")
            self._collector_number = rest.strip()
        else:
            self._name, self._setcode, self._collector_number = rest, None, None

    def __repr__(self) -> str:
        pairs = [("quantity", self.quantity), ("name", self.name)]
        if self.is_extended:
            pairs += [("setcode", self.setcode), ("collector_number", self.collector_number)]
        return getrepr(self.__class__, *pairs)


class Video:
    """YouTube video showcasing a MtG deck with its most important metadata.
    """
    URL_TEMPLATE = "https://www.youtube.com/watch?v={}"

    # decklist hooks
    AETHERHUB_HOOK = "aetherhub.com/Deck/"
    MOXFIELD_HOOK = "moxfield.com/decks/"
    GOLDFISH_HOOK = "mtggoldfish.com/deck/"
    TCGPLAYER_HOOK = "decks.tcgplayer.com/"
    UNTAPPED_HOOKS = {"mtga.untapped.gg", "/deck/"}

    SHORTENER_HOOKS = {"bit.ly/", "tinyurl.com/", "cutt.ly/", "rb.gy/", "shortcm.li/", "tiny.cc/",
                       "snip.ly/", "qti.ai/", "dub.sh/", "lyksoomu.com/", "zws.im/", "t.ly/"}

    @property
    def id(self) -> str:
        return self._scrapetube_data["videoId"]

    @property
    def author(self) -> str:
        return self._pytube_data.author

    @property
    def channel_id(self) -> str:
        return self._pytube_data.channel_id

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

    @property
    def _desc_lines(self) -> List[str]:
        return self.description.split("\n")

    @property
    def links(self) -> List[str]:
        return self._links

    @property
    def arena_lines(self) -> List[ArenaLine]:
        return self._arena_lines

    @property
    def shortened_links(self) -> Set[str]:
        return {link for link in self.links if any(hook in link for hook in self.SHORTENER_HOOKS)}

    def __init__(self, scrapetube_data: Json) -> None:
        self._scrapetube_data = scrapetube_data
        self._pytube_data = YouTube(self.URL_TEMPLATE.format(self.id))
        self._links, self._arena_lines = self._parse_lines()

    def _parse_lines(self) -> Tuple[List[str], List[ArenaLine]]:
        links, arena_lines = [], []
        for i, line in enumerate(self._desc_lines):
            url = exctract_url(line)
            if url:
                links.append(url)
            else:
                match = ArenaLine.PATTERN.match(line)
                if match:
                    arena_lines.append(ArenaLine(line, i))

        return links, arena_lines


class Channel(list):
    """A list of videos showcasing a MtG deck with its most important metadata.
    """
    @property
    def url(self) -> str:
        return self._url

    @property
    def id(self) -> Optional[str]:
        return self._id

    @property
    def title(self) -> Optional[str]:
        return self._title

    @property
    def tags(self) -> Optional[List[str]]:
        return self._tags

    @property
    def subscribers(self) -> Optional[int]:
        return self._subscribers

    def __init__(self, url: str, limit=10) -> None:
        try:
            videos = [*get_channel(channel_url=url, limit=limit)]
        except OSError:
            raise ValueError(f"Invalid URL: {url!r}")
        super().__init__([Video(data) for data in videos])
        self._url = url
        self._id = self[0].channel_id if self else None
        self._ytsp_data = YtspChannel(self.id) if self._id else None
        self._title = self._ytsp_data.result["title"] if self._id else None
        self._tags = self._ytsp_data.result["tags"] if self._id else None
        self._subscribers = self._parse_subscribers() if self._id else None

    def _parse_subscribers(self) -> int:
        text = self._ytsp_data.result["subscribers"]["simpleText"]
        number = text.rstrip(" subscribers").rstrip("KM")
        subscribers = Decimal(number)
        if "K" in text:
            subscribers *= 1000
        elif "M" in text:
            subscribers *= 1_000_000
        return int(subscribers)


def unshorten(url: str) -> str:
    """Unshorten URL shortened by services like bit.ly, tinyurl.com etc.

    Pilfered from: https://stackoverflow.com/a/28918160/4465708
    """
    session = requests.Session()  # so connections are recycled
    resp = session.head(url, allow_redirects=True)
    return resp.url


def exctract_url(text: str) -> Optional[str]:
    """Extract (the firs occurance of) URL from ``text``.

    Pilfered from: https://stackoverflow.com/a/840110/4465708
    """
    match = re.search(r"(?P<url>https?://[^\s'\"]+)", text)
    return match.group("url") if match else None
