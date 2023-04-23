"""

    mtgcards.yt.py
    ~~~~~~~~~~~~~~
    Handle YouTube data.

    @author: z33k

"""
import itertools
import re
from collections import defaultdict, Counter
from datetime import datetime
from decimal import Decimal
from functools import cached_property
from typing import DefaultDict, Dict, List, Optional, Set, Tuple, Type

import gspread
import requests
from contexttimer import Timer
from scrapetube import get_channel
from pytube import YouTube
from youtubesearchpython import Channel as YtspChannel

from mtgcards.const import Json
from mtgcards.scryfall import formats as scryfall_formats
from mtgcards.scryfall import format_cards, Deck
from mtgcards.utils import getrepr
from mtgcards.yt.parsers import UrlParser
from mtgcards.yt.parsers.arena import ArenaParser
from mtgcards.yt.parsers.aetherhub import AetherHubParser
from mtgcards.yt.parsers.goldfish import GoldfishParser
from mtgcards.yt.parsers.moxfield import MoxfieldParser
from mtgcards.yt.parsers.mtgazone import MtgaZoneParser
from mtgcards.yt.parsers.streamdecker import StreamdeckerParser
from mtgcards.yt.parsers.tcgplayer import TcgPlayerParser
from mtgcards.yt.parsers.untapped import UntappedParser


def channels() -> Dict[str, str]:
    """Retrieve a channel addresses mapping from a private Google Sheet spreadsheet.

    Mind that this operation takes about 2 seconds to complete.

    :return: a dictionary of channel names mapped to their addresses
    """
    creds_file = "scraping_service_account.json"
    client = gspread.service_account(filename=creds_file)
    spreadsheet = client.open("mtga_yt")
    worksheet = spreadsheet.worksheet("channels")
    names = worksheet.col_values(1, value_render_option="UNFORMATTED_VALUE")[1:]
    addresses = worksheet.col_values(3, value_render_option="UNFORMATTED_VALUE")[1:]
    return dict((name, address) for name, address in zip(names, addresses))


class Video:
    """YouTube video showcasing a MtG deck with its most important metadata.
    """
    URL_TEMPLATE = "https://www.youtube.com/watch?v={}"

    # decklist hooks
    AETHERHUB_HOOK = "aetherhub.com/Deck/"
    GOLDFISH_HOOK = "mtggoldfish.com/deck/"
    MOXFIELD_HOOK = "moxfield.com/decks/"
    MTGAZONE_HOOK = "mtgazone.com/user-decks/"
    STREAMDECKER_HOOK = "streamdecker.com/deck/"
    TCGPLAYER_HOOK = "decks.tcgplayer.com/"
    UNTAPPED_HOOKS = {"mtga.untapped.gg", "/deck/"}

    SHORTENER_HOOKS = {"bit.ly/", "tinyurl.com/", "cutt.ly/", "rb.gy/", "shortcm.li/", "tiny.cc/",
                       "snip.ly/", "qti.ai/", "dub.sh/", "lyksoomu.com/", "zws.im/", "t.ly/"}

    formats = scryfall_formats()

    @property
    def id(self) -> str:
        return self._id

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

    @cached_property
    def _desc_lines(self) -> List[str]:
        return [line.strip() for line in self.description.split("\n")]

    @property
    def links(self) -> List[str]:
        return self._links

    @property
    def shortened_links(self) -> Set[str]:
        return {link for link in self.links if any(hook in link for hook in self.SHORTENER_HOOKS)}

    @property
    def format(self) -> str:
        return self._format

    @property
    def deck(self) -> Optional[Deck]:
        return self._deck

    def __init__(self, video_id: str) -> None:
        """Initialize.

        :param video_id: unique string identifying a YouTube video (the part after `v=` in the URL)
        """
        self._id = video_id
        self._pytube_data = YouTube(self.URL_TEMPLATE.format(self.id))
        self._format_soup: DefaultDict[str, List[str]] = defaultdict(list)
        self._extract_formats(self.title)
        self._links, self._arena_lines = self._parse_lines()
        self._format = self._get_format()
        self._format_cards = format_cards(self._format)
        self._deck = self._get_deck()

    def __repr__(self) -> str:
        return getrepr(self.__class__, ("title", self.title), ("deck", self.deck))

    def _extract_formats(self, line: str) -> None:
        words = [word.lower() for word in line.strip().split()]
        formats = [fmt for fmt in self.formats if any(fmt in word for word in words)]
        for fmt in formats:
            self._format_soup[fmt].append(fmt)

    def _get_format(self) -> str:
        # if format soup has been populated, take the most common item
        if self._format_soup:
            two_best = Counter(itertools.chain(*self._format_soup.values())).most_common(2)
            two_best = [pair[0] for pair in two_best]
            if len(two_best) == 2 and all(fmt in ("brawl", "historic") for fmt in two_best):
                return "historicbrawl"
            return two_best[0]
        # if not, fall back to default
        return "standard"

    def _parse_lines(self) -> Tuple[List[str], List[str]]:
        links, arena_lines = [], []
        for line in self._desc_lines:
            self._extract_formats(line)
            url = exctract_url(line)
            if url:
                links.append(url)
            else:
                if ArenaParser.is_arena_line(line):
                    arena_lines.append(line)
        return links, arena_lines

    @classmethod
    def _process_hooks(cls, links: List[str]) -> Dict[Type[UrlParser], str]:
        parsersmap = {}
        for link in links:
            if not parsersmap.get(AetherHubParser) and cls.AETHERHUB_HOOK in link:
                parsersmap[AetherHubParser] = link
            elif not parsersmap.get(GoldfishParser) and cls.GOLDFISH_HOOK in link:
                parsersmap[GoldfishParser] = link
            elif not parsersmap.get(MoxfieldParser) and cls.MOXFIELD_HOOK in link:
                parsersmap[MoxfieldParser] = link
            elif not parsersmap.get(MtgaZoneParser) and cls.MTGAZONE_HOOK in link:
                parsersmap[MtgaZoneParser] = link
            elif not parsersmap.get(StreamdeckerParser) and cls.STREAMDECKER_HOOK in link:
                parsersmap[StreamdeckerParser] = link
            elif not parsersmap.get(TcgPlayerParser) and cls.TCGPLAYER_HOOK in link:
                parsersmap[TcgPlayerParser] = link
            elif (not parsersmap.get(UntappedParser)
                  and all(hook in link for hook in cls.UNTAPPED_HOOKS)):
                parsersmap[UntappedParser] = link
        return parsersmap

    def _process_urls(self, urls: List[str]) -> Optional[Deck]:
        parsersmap = self._process_hooks(urls)
        for parser_type, url in parsersmap.items():
            deck = parser_type(url, self._format_cards).deck
            if deck:
                return deck
        return None

    def _get_deck(self) -> Optional[Deck]:
        # 1st stage: Arena lines
        if self._arena_lines:
            deck = ArenaParser(self._arena_lines, self._format_cards).deck
            if deck:
                return deck
        # 2nd stage: regular URLs
        deck = self._process_urls(self.links)
        if deck:
            return deck
        # 3rd stage: shortened URLs
        shortened_urls = [link for link in self.links
                          if any(hook in link for hook in self.SHORTENER_HOOKS)]
        unshortened_urls = [unshorten(url) for url in shortened_urls]
        return self._process_urls(unshortened_urls)


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
        super().__init__([Video(data["videoId"]) for data in videos])
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
    print(f"Unshortening: '{url}'...")
    with Timer() as t:
        session = requests.Session()  # so connections are recycled
        resp = session.head(url, allow_redirects=True)
    print(f"Request completed in {t.elapsed:.3f} seconds.")
    return resp.url


def exctract_url(text: str, https=True) -> Optional[str]:
    """Extract (the firs occurance of) URL from ``text``.

    Pilfered from: https://stackoverflow.com/a/840110/4465708
    """
    pattern = r"(?P<url>https?://[^\s'\"]+)" if https else r"(?P<url>http?://[^\s'\"]+)"
    match = re.search(pattern, text)
    return match.group("url") if match else None
