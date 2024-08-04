"""

    mtgcards.yt.py
    ~~~~~~~~~~~~~~
    Handle YouTube data.

    @author: z33k

"""
import itertools
import logging
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from functools import cached_property

import gspread
import pytubefix
import scrapetube
from youtubesearchpython import Channel as YtspChannel

from mtgcards.const import Json
from mtgcards.decks import Deck
from mtgcards.decks.arena import ArenaParser, is_arena_line, is_empty, is_playset_line
from mtgcards.decks.cardhoarder import CardhoarderScraper
from mtgcards.decks.goldfish import GoldfishScraper
from mtgcards.decks.aetherhub import AetherhubScraper
from mtgcards.decks.moxfield import MoxfieldScraper
from mtgcards.decks.streamdecker import StreamdeckerScraper
from mtgcards.decks.tappedout import TappedoutScraper
from mtgcards.decks.untapped import UntappedProfileDeckScraper, UntappedRegularDeckScraper
from mtgcards.decks.mtgazone import MtgazoneScraper
from mtgcards.scryfall import all_formats
from mtgcards.utils import getrepr
from mtgcards.utils.scrape import extract_source, extract_url, timed_request, unshorten

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
    def url(self) -> str:
        return self.URL_TEMPLATE.format(self.id)

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
    def date(self) -> datetime:
        return self._date

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
    def unshortened_links(self) -> list[str]:
        return self._unshortened_links

    @property
    def derived_format(self) -> str:
        return self._derived_format

    @property
    def decks(self) -> list[Deck]:
        return self._decks

    @property
    def metadata(self) -> Json:
        metadata = {
            "author": self.author,
            "video": {
                "url": self.url,
                "title": self.title,
                "description": self.description,
                "keywords": self.keywords,
                "date": self.date,
                "views": self.views
            }
        }
        if self.derived_format:
            metadata["format"] = self.derived_format
        return metadata

    @property
    def sources(self) -> list[str]:
        return sorted(self._sources)

    def __init__(self, video_id: str) -> None:
        """Initialize.

        Args:
            video_id: unique string identifying a YouTube video (the part after `v=` in the URL)
        """
        self._id = video_id
        self._pytube = self._get_pytube()
        # description and title is also available in scrapetube data on Channel level
        self._author, self._description, self._title = None, None, None
        self._keywords, self._date, self._views = None, None, None
        self._sources = set()
        self._get_pytube_data()
        self._format_soup = self._get_format_soup()
        self._derived_format = self._derive_format()
        self._links, self._arena_lines = self._parse_lines()
        self._unshortened_links: list[str] = []
        self._decks = self._collect()

    def __repr__(self) -> str:
        return getrepr(self.__class__,
                       ("title", self.title),
                       ("deck", len(self.decks)),
                       ("date", str(self.date.date())),
                       ("views", self.views)
                       )

    def _get_pytube(self) -> pytubefix.YouTube:
        return pytubefix.YouTube(self.url)

    def _get_pytube_data(self) -> None:
        self._author = self._pytube.author
        self._description = self._pytube.description
        self._title = self._pytube.title
        self._keywords = self._pytube.keywords
        self._date = self._pytube.publish_date
        self._views = self._pytube.views
        self._channel_id = self._pytube.channel_id

    @staticmethod
    def _extract_formats(line: str) -> list[str]:
        words = [word.lower() for word in line.strip().split()]
        return [fmt for fmt in all_formats() if any(fmt in word for word in words)]

    def _get_format_soup(self) -> defaultdict[str, list[str]]:
        fmt_soup = defaultdict(list)
        for line in [self.title, *self._desc_lines]:
            for fmt in self._extract_formats(line):
                fmt_soup[fmt].append(fmt)
        return fmt_soup

    def _derive_format(self) -> str | None:
        # if format soup has been populated, take the most common item
        if self._format_soup:
            two_best = Counter(itertools.chain(*self._format_soup.values())).most_common(2)
            two_best = [pair[0] for pair in two_best]
            if len(two_best) == 2 and all(fmt in ("brawl", "standard") for fmt in two_best):
                return "standardbrawl"
            return two_best[0]
        # if not, fall back to default
        return None

    def _parse_lines(self) -> tuple[list[str], list[str]]:
        links, arena_lines = [], []
        for i, line in enumerate(self._desc_lines):
            self._extract_formats(line)
            url = extract_url(line)
            if url:
                links.append(url)
            elif is_empty(line):
                if i != len(self._desc_lines) - 1 and is_playset_line(self._desc_lines[i + 1]):
                    arena_lines.append(line)
            elif is_arena_line(line):
                arena_lines.append(line)
        return links, arena_lines

    def _scrape_deck(self, link: str) -> Deck | None:
        if GoldfishScraper.is_deck_url(link):
            return GoldfishScraper(link, self.metadata).deck
        elif AetherhubScraper.is_deck_url(link):
            return AetherhubScraper(link, self.metadata).deck
        elif MoxfieldScraper.is_deck_url(link):
            return MoxfieldScraper(link, self.metadata).deck
        elif StreamdeckerScraper.is_deck_url(link):
            return StreamdeckerScraper(link, self.metadata).deck
        elif UntappedProfileDeckScraper.is_deck_url(link):
            return UntappedProfileDeckScraper(link, self.metadata).deck
        elif UntappedRegularDeckScraper.is_deck_url(link):
            return UntappedRegularDeckScraper(link, self.metadata).deck
        elif MtgazoneScraper.is_deck_url(link):
            return MtgazoneScraper(link, self.metadata).deck
        elif CardhoarderScraper.is_deck_url(link):
            return CardhoarderScraper(link, self.metadata).deck
        elif TappedoutScraper.is_deck_url(link):
            return TappedoutScraper(link, self.metadata).deck
        elif any(h in link for h in self.PASTEBIN_LIKE_HOOKS):
            lines = timed_request(link).splitlines()
            lines = [l for l in lines if is_arena_line(l) or is_empty(l)]
            if lines:
                return ArenaParser(lines, self.metadata).deck
        return None

    def _process_urls(self, urls: list[str]) -> list[Deck]:
        decks = []
        for url in urls:
            self._sources.add(extract_source(url))
            if deck := self._scrape_deck(url):
                decks.append(deck)
        return decks

    def _collect(self) -> list[Deck]:
        decks = []

        # 1st stage: Arena lines
        if self._arena_lines:
            if deck := ArenaParser(self._arena_lines, self._derived_format).deck:
                decks.append(deck)
        # 2nd stage: regular URLs
        decks += self._process_urls(self.links)
        # 3rd stage: shortened URLs
        shortened_urls = [link for link in self.links
                          if any(hook in link for hook in self.SHORTENER_HOOKS)]
        if shortened_urls:
            self._unshortened_urls = [unshorten(url) for url in shortened_urls]
            decks += self._process_urls(self._unshortened_urls)

        return decks


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

    @property
    def most_recent(self) -> Video:
        return self[-1]

    @property
    def decks(self) -> list[Deck]:
        return [video.deck for video in self if video.deck]

    @property
    def sources(self) -> list[str]:
        return sorted(self._sources)

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
        self._sources = {s for v in self for s in v.sources}

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


