"""

    mtgcards.yt.py
    ~~~~~~~~~~~~~~
    Handle YouTube data.

    @author: z33k

"""
import itertools
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from functools import cached_property
from typing import Type

import gspread
import pytubefix
import requests
import scrapetube
from contexttimer import Timer
from youtubesearchpython import Channel as YtspChannel

from mtgcards.scryfall import formats
from mtgcards.decks import Deck, DeckParser
from mtgcards.decks.aetherhub import AetherHubParser
from mtgcards.decks.arena import ArenaParser, is_empty, is_playset
from mtgcards.decks.goldfish import GoldfishParser
from mtgcards.decks.moxfield import MoxfieldParser
from mtgcards.decks.mtgazone import MtgaZoneParser
from mtgcards.decks.streamdecker import StreamdeckerParser
from mtgcards.decks.tcgplayer import TcgPlayerParser
from mtgcards.decks.untapped import UntappedParser
from mtgcards.utils import getrepr, timed, timed_request


_log = logging.getLogger(__name__)


def channels() -> dict[str, str]:
    """Retrieve a channel addresses mapping from a private Google Sheet spreadsheet.

    Mind that this operation takes about 2 seconds to complete.

    Returns:
        a dictionary of channel names mapped to their addresses
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

    SHORTENER_HOOKS = {
        "bit.ly/",
        "tinyurl.com/",
        "cutt.ly/",
        "rb.gy/",
        "shortcm.li/",
        "tiny.cc/",
        "snip.ly/",
        "qti.ai/",
        "dub.sh/",
        "lyksoomu.com/",
        "zws.im/",
        "t.ly/"
    }

    PASTEBIN_LIKE_HOOKS = {
        "bitbin.it",
        "bpa.st",
        "cl1p.net",
        "codebeautify.org",
        "codeshare.io",
        "commie.io",
        "controlc.com",
        "cutapaste.net",
        "defuse.ca/pastebin.htm",
        "dotnetfiddle.net",
        "dpaste.com",
        "dpaste.org",
        "everfall.com/paste/",
        "friendpaste.com",
        "gist.github.com",
        "hastebin.com",
        "ide.geeksforgeeks.org",
        "ideone.com",
        "ivpaste.com",
        "jpst.it",
        "jsbin.com",
        "jsfiddle.net",
        "jsitor.com",
        "justpaste.it",
        "justpaste.me",
        "kpaste.net",
        "n0paste.tk",
        "nekobin.com",
        "notes.io",
        "p.ip.fi",
        "paste-bin.xyz",
        "paste.centos.org",
        "paste.debian.net",
        "paste.ee",
        "paste.jp",
        "paste.mozilla.org",
        "paste.ofcode.org",
        "paste.opensuse.org",
        "paste.org.ru",
        "paste.rohitab.com",
        "paste.sh",
        "paste2.org",
        "pastebin.ai",
        "pastebin.com",
        "pastebin.fi",
        "pastebin.fr",
        "pastebin.osuosl.org",
        "pastecode.io",
        "pasted.co",
        "pasteio.com",
        "pastelink.net",
        "pastie.org",
        "privatebin.net",
        "pst.innomi.net",
        "quickhighlighter.com",
        "termbin.com",
        "tny.cz",
        "tutpaste.com",
        "vpaste.net",
        "www.paste.lv",
        "www.paste4btc.com",
        "www.pastebin.pt",
    }

    @property
    def id(self) -> str:
        return self._id

    @property
    def author(self) -> str:
        return self._author

    @property
    def description(self) -> str:
        return self._description

    @property
    def keywords(self) -> list[str]:
        return self._keywords

    @property
    def publish_date(self) -> datetime:
        return self._publish_date

    @property
    def title(self) -> str:
        return self._title

    @property
    def views(self) -> int:
        return self._views

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @cached_property
    def _desc_lines(self) -> list[str]:
        return [line.strip() for line in self.description.split("\n")] if self.description else []

    @property
    def links(self) -> list[str]:
        return self._links

    @property
    def shortened_links(self) -> set[str]:
        return {link for link in self.links if any(hook in link for hook in self.SHORTENER_HOOKS)}

    @property
    def format(self) -> str:
        return self._format

    @property
    def deck(self) -> Deck | None:
        return self._deck

    def __init__(self, video_id: str) -> None:
        """Initialize.

        Args:
            video_id: unique string identifying a YouTube video (the part after `v=` in the URL)
        """
        self._id = video_id
        self._pytube = self._get_pytube()
        # description and title is also available in scrapetube data on Channel level
        self._author, self._description, self._title = None, None, None
        self._keywords, self._publish_date, self._views = None, None, None
        self._get_pytube_data()
        self._format_soup = self._get_format_soup()
        self._links, self._arena_lines = self._parse_lines()
        self._format = self._get_format()
        self._deck = self._get_deck()

    def __repr__(self) -> str:
        return getrepr(self.__class__, ("title", self.title), ("deck", self.deck))

    def _get_pytube(self) -> pytubefix.YouTube:
        return pytubefix.YouTube(self.URL_TEMPLATE.format(self.id))

    def _get_pytube_data(self) -> None:
        self._author = self._pytube.author
        self._description = self._pytube.description
        self._title = self._pytube.title
        self._keywords = self._pytube.keywords
        self._publish_date = self._pytube.publish_date
        self._views = self._pytube.views
        self._channel_id = self._pytube.channel_id

    @staticmethod
    def _extract_formats(line: str) -> list[str]:
        words = [word.lower() for word in line.strip().split()]
        return [fmt for fmt in formats() if any(fmt in word for word in words)]

    def _get_format_soup(self) -> defaultdict[str, list[str]]:
        fmt_soup = defaultdict(list)
        for line in [self.title, *self._desc_lines]:
            for fmt in self._extract_formats(line):
                fmt_soup[fmt].append(fmt)
        return fmt_soup

    def _get_format(self) -> str:
        # if format soup has been populated, take the most common item
        if self._format_soup:
            two_best = Counter(itertools.chain(*self._format_soup.values())).most_common(2)
            two_best = [pair[0] for pair in two_best]
            if len(two_best) == 2 and all(fmt in ("brawl", "standard") for fmt in two_best):
                return "standardbrawl"
            return two_best[0]
        # if not, fall back to default
        return "standard"

    @staticmethod
    def is_arena(line: str) -> bool:
        if line == "Deck":
            return True
        elif line == "Commander":
            return True
        elif line == "Companion":
            return True
        elif line == "Sideboard":
            return True
        elif is_playset(line):
            return True
        return False

    def _parse_lines(self) -> tuple[list[str], list[str]]:
        links, arena_lines = [], []
        for i, line in enumerate(self._desc_lines):
            self._extract_formats(line)
            url = extract_url(line)
            if url:
                links.append(url)
            elif is_empty(line):
                if i != len(self._desc_lines) - 1 and is_playset(self._desc_lines[i + 1]):
                    arena_lines.append(line)
            elif self.is_arena(line):
                arena_lines.append(line)
        return links, arena_lines

    @classmethod
    def _process_hooks(cls, links: list[str]) -> dict[Type[DeckParser], str]:
        parsers_map = {}
        for link in links:
            if not parsers_map.get(AetherHubParser) and cls.AETHERHUB_HOOK in link:
                parsers_map[AetherHubParser] = link
            elif not parsers_map.get(GoldfishParser) and cls.GOLDFISH_HOOK in link:
                parsers_map[GoldfishParser] = link
            elif not parsers_map.get(MoxfieldParser) and cls.MOXFIELD_HOOK in link:
                parsers_map[MoxfieldParser] = link
            elif not parsers_map.get(MtgaZoneParser) and cls.MTGAZONE_HOOK in link:
                parsers_map[MtgaZoneParser] = link
            elif not parsers_map.get(StreamdeckerParser) and cls.STREAMDECKER_HOOK in link:
                parsers_map[StreamdeckerParser] = link
            elif not parsers_map.get(TcgPlayerParser) and cls.TCGPLAYER_HOOK in link:
                parsers_map[TcgPlayerParser] = link
            elif (not parsers_map.get(UntappedParser)
                  and all(hook in link for hook in cls.UNTAPPED_HOOKS)):
                parsers_map[UntappedParser] = link
            elif not parsers_map.get("pastebin-like") and any(
                    h in link for h in cls.PASTEBIN_LIKE_HOOKS):
                parsers_map["pastebin-like"] = link
        return parsers_map

    def _process_urls(self, urls: list[str]) -> Deck | None:
        parsers_map = self._process_hooks(urls)
        deck = None
        for parser_type, url in parsers_map.items():
            if parser_type == "pastebin-like":
                lines = timed_request(url).splitlines()
                lines = [l for l in lines if self.is_arena(l) or is_empty(l)]
                if lines:
                    deck = ArenaParser(lines, fmt=self._format).deck
            else:
                deck = parser_type(url, self._format).deck
            if deck:
                return deck
        return None

    def _get_deck(self) -> Deck | None:
        # 1st stage: Arena lines
        if self._arena_lines:
            deck = ArenaParser(self._arena_lines, self._format).deck
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
    def id(self) -> str | None:
        return self._id

    @property
    def title(self) -> str | None:
        return self._title

    @property
    def description(self) -> str | None:
        return self._description

    @property
    def tags(self) -> list[str] | None:
        return self._tags

    @property
    def subscribers(self) -> int | None:
        return self._subscribers

    def __init__(self, url: str, limit=10) -> None:
        try:
            videos = [*scrapetube.get_channel(channel_url=url, limit=limit)]
        except OSError:
            raise ValueError(f"Invalid URL: {url!r}")
        super().__init__([Video(data["videoId"]) for data in videos])
        self._url = url
        self._id = self[0].channel_id if self else None
        self._ytsp_data = YtspChannel(self.id) if self._id else None
        self._description = self._ytsp_data.result.get("description") if self._id else None
        self._title = self._ytsp_data.result.get("title") if self._id else None
        self._tags = self._ytsp_data.result.get("tags") if self._id else None
        self._subscribers = self._parse_subscribers() if self._id else None

    def _parse_subscribers(self) -> int | None:
        if not self._id:
            return None
        text = self._ytsp_data.result["subscribers"]["simpleText"]
        if not text:
            return None
        number = text.rstrip(" subscribers").rstrip("KM")
        subscribers = Decimal(number)
        if "K" in text:
            subscribers *= 1000
        elif "M" in text:
            subscribers *= 1_000_000
        return int(subscribers)


@timed("unshortening")
def unshorten(url: str) -> str:
    """Unshorten URL shortened by services like bit.ly, tinyurl.com etc.

    Pilfered from: https://stackoverflow.com/a/28918160/4465708
    """
    session = requests.Session()  # so connections are recycled
    resp = session.head(url, allow_redirects=True)
    return resp.url


def extract_url(text: str, https=True) -> str | None:
    """Extract (the first occurrence of) URL from ``text``.

    Pilfered from: https://stackoverflow.com/a/840110/4465708
    """
    pattern = r"(?P<url>https?://[^\s'\"]+)" if https else r"(?P<url>http?://[^\s'\"]+)"
    match = re.search(pattern, text)
    return match.group("url") if match else None
