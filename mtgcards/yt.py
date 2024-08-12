"""

    mtgcards.yt.py
    ~~~~~~~~~~~~~~
    Handle YouTube data.

    @author: z33k

"""
import itertools
import json
import logging
import re
from collections import Counter, defaultdict, OrderedDict
from datetime import date, datetime
from decimal import Decimal
from functools import cached_property
from typing import Generator

import pytubefix
import scrapetube
from contexttimer import Timer
from youtubesearchpython import Channel as YtspChannel

from mtgcards.const import Json
from mtgcards.decks import Deck
from mtgcards.decks.aetherhub import AetherhubScraper
from mtgcards.decks.arena import ArenaParser, get_arena_lines
from mtgcards.decks.cardhoarder import CardhoarderScraper
from mtgcards.decks.goldfish import GoldfishScraper
from mtgcards.decks.moxfield import MoxfieldScraper
from mtgcards.decks.mtgazone import MtgaZoneScraper
from mtgcards.decks.mtgtop8 import MtgTop8Scraper
from mtgcards.decks.streamdecker import StreamdeckerScraper
from mtgcards.decks.tappedout import TappedoutScraper
from mtgcards.decks.tcgplayer import NewPageTcgPlayerScraper, OldPageTcgPlayerScraper
from mtgcards.decks.untapped import UntappedProfileDeckScraper, UntappedRegularDeckScraper
from mtgcards.scryfall import all_formats
from mtgcards.utils import extract_float, getrepr, timed
from mtgcards.utils.gsheets import extend_gsheet_rows_with_cols, retrieve_from_gsheets_cols
from mtgcards.utils.scrape import extract_source, extract_url, get_dynamic_soup_by_xpath, \
    timed_request, unshorten

_log = logging.getLogger(__name__)


# TODO: other fields (only when all rows get populated), export to JSON
def channels() -> Generator[tuple[str, str], None, None]:
    """Yield a tuple (channel name, channel addresses) from a private Google Sheet spreadsheet.

    Mind that this operation takes about 4 seconds to complete.
    """
    names, addresses = retrieve_from_gsheets_cols("mtga_yt", "channels", (1, 3), start_row=2)
    for name, address in zip(names, addresses):
        yield name, address


def batch_update(start_row=2, batch_size: int | None = None) -> None:
    """Batch update "channels" Google Sheets worksheet.

    Args:
        start_row: start row of the worksheet
        batch_size: number of rows to update ('None' (default) means all rows from start_row)
    """
    if start_row < 2:
        raise ValueError("Start row must not be lesser than 2")
    if batch_size is not None and batch_size < 1:
        raise ValueError("Batch size must be a positive integer or None")
    _log.info(f"Batch updating {batch_size} channel row(s)...")
    data = []
    if batch_size is None:
        items = [*channels()][start_row - 2:]
    else:
        start_idx, end_idx = start_row - 2, start_row - 2 + batch_size
        items = itertools.islice(channels(), start_idx, end_idx)

    for _, url in items:
        try:
            ch = Channel(url)
            data.append([
                url,
                ch.scrape_date.strftime("%Y-%m-%d"),
                ch.staleness,
                ch.posting_interval,
                len(ch),
                len(ch.decks),
                ch.total_views,
                ch.views_per_sub or "N/A",
                ch.subscribers or "N/A",
                ", ".join(ch.sources),
                ", ".join(ch.deck_sources)
            ])
        except json.decoder.JSONDecodeError:
            _log.warning(
                f"scrapetube failed with JSON error for channel {url!r}. It probably doesn't "
                f"exist anymore. Skipping...")
            data.append(
                ["NOT AVAILABLE", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                 "N/A"])

    extend_gsheet_rows_with_cols("mtga_yt", "channels", data, start_row=start_row, start_col=5)


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
    def date(self) -> date:
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
        if self._channel_subscribers:
            metadata["video"]["channel_subscribers"] = self._channel_subscribers
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
        self._unshortened_links: list[str] = []
        self._scrape()

    @timed("gathering video data")
    def _scrape(self):
        self._get_pytube_data()
        self._format_soup = self._get_format_soup()
        self._derived_format = self._derive_format()
        self._links, self._arena_lines = self._parse_lines()
        self._decks = self._collect()

    def __repr__(self) -> str:
        return getrepr(
            self.__class__,
            ("title", self.title),
            ("deck", len(self.decks)),
            ("date", str(self.date)),
            ("views", self.views)
        )

    def _get_pytube(self) -> pytubefix.YouTube:
        return pytubefix.YouTube(self.url)

    def _extract_subscribers(self) -> int | None:
        pattern = r'(\d+(?:\.\d+)?)\s*([KMB]?)\s*subscribers'
        match = re.search(pattern, self._pytube.embed_html)

        if match:
            # extract the number and suffix from the match
            number = float(match.group(1))
            suffix = match.group(2)

            # convert the number based on the suffix
            if suffix == 'K':
                return int(number * 1_000)
            elif suffix == 'M':
                return int(number * 1_000_000)
            elif suffix == 'B':
                return int(number * 1_000_000_000)
            return int(number)

        return None

    def _get_pytube_data(self) -> None:
        self._author = self._pytube.author
        self._description = self._pytube.description
        self._title = self._pytube.title
        self._keywords = self._pytube.keywords
        self._date = self._pytube.publish_date.date()
        self._views = self._pytube.views
        self._channel_id = self._pytube.channel_id
        self._channel_subscribers = self._extract_subscribers()

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
        links, other_lines = [], []
        deck_lines, sideboard_lines = [], []
        for i, line in enumerate(self._desc_lines):
            self._extract_formats(line)
            url = extract_url(line)
            if url:
                links.append(url)
            else:
                if line == "Deck":
                    deck_lines.append(line)
                elif line == "Sideboard":
                    sideboard_lines.append(line)
                # prevent parsing two decklists as one
                if not len(deck_lines) > 1 and not len(sideboard_lines) > 1:
                    other_lines.append(line)
        return links, [*get_arena_lines(*other_lines)]

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
        elif MtgaZoneScraper.is_deck_url(link):
            return MtgaZoneScraper(link, self.metadata).deck
        elif CardhoarderScraper.is_deck_url(link):
            return CardhoarderScraper(link, self.metadata).deck
        elif TappedoutScraper.is_deck_url(link):
            return TappedoutScraper(link, self.metadata).deck
        elif MtgTop8Scraper.is_deck_url(link):
            return MtgTop8Scraper(link, self.metadata).deck
        elif OldPageTcgPlayerScraper.is_deck_url(link):
            return OldPageTcgPlayerScraper(link, self.metadata).deck
        elif NewPageTcgPlayerScraper.is_deck_url(link):
            return NewPageTcgPlayerScraper(link, self.metadata).deck
        elif any(h in link for h in self.PASTEBIN_LIKE_HOOKS):
            lines = timed_request(link).splitlines()
            arena_lines = [*get_arena_lines(*lines)]
            if arena_lines:
                return ArenaParser(arena_lines, self.metadata).deck
        return None

    def _process_urls(self, urls: list[str]) -> list[Deck]:
        decks = []
        for url in urls:
            self._sources.add(extract_source(url))
            try:
                if deck := self._scrape_deck(url):
                    decks.append(deck)
            except Exception as e:
                _log.exception(f"Deck scraping failed with: {e}")
        return decks

    def _collect(self) -> list[Deck]:
        decks = set()

        # 1st stage: regular URLs
        decks.update(self._process_urls(self.links))

        # 2nd stage: shortened URLs
        if not decks:
            shortened_urls = [link for link in self.links
                              if any(hook in link for hook in self.SHORTENER_HOOKS)]
            if shortened_urls:
                self._unshortened_urls = [unshorten(url) for url in shortened_urls]
                decks.update(self._process_urls(self._unshortened_urls))

        # 3rd stage: Arena lines
        if self._arena_lines:
            self._sources.add("arena.decklist")
            if deck := ArenaParser(self._arena_lines, self.metadata).deck:
                decks.add(deck)

        return sorted(decks)


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
    def decks(self) -> list[Deck]:
        return [d for v in self for d in v.decks]

    @property
    def deck_sources(self) -> list[str]:
        return sorted({d.source for d in self.decks})

    @property
    def sources(self) -> list[str]:
        return sorted(self._sources)

    @property
    def staleness(self) -> int | None:
        return (date.today() - self[0].date).days if self else None

    @property
    def total_views(self) -> int:
        return sum(v.views for v in self)

    @property
    def views_per_sub(self) -> float | None:
        return self.total_views / self.subscribers if self.subscribers else None

    @property
    def scrape_date(self) -> date:
        return self._scrape_time.date()

    @property
    def span(self) -> int | None:
        return (self[0].date - self[-1].date).days if self else None

    @property
    def posting_interval(self) -> float | None:
        return self.span / len(self) if self else None

    def __init__(self, url: str, limit=10) -> None:
        with Timer() as t:
            self._scrape_time = datetime.now()
            _log.info(f"Scraping channel: {url!r}, {limit} video(s)...")
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
            if not self._subscribers:
                self._subscribers = self[0].metadata["video"].get(
                    "channel_subscribers") if self else None
                if self._subscribers is None:
                    self._subscribers = self._scrape_subscribers_with_selenium()
            self._sources = {s for v in self for s in v.sources}
        _log.info(f"Completed channel scraping in {t.elapsed:.2f} second(s)")

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
        elif "B" in text:
            subscribers *= 1_000_000_000
        return int(subscribers)

    def _scrape_subscribers_with_selenium(self) -> int:
        consent_xpath = "//button[@aria-label='Accept all']"
        xpath = "//span[contains(., 'subscribers')]"
        soup, _, _ = get_dynamic_soup_by_xpath(self.url, xpath, consent_xpath=consent_xpath)
        text = soup.find("span", string=lambda t: t and "subscribers" in t).text.removesuffix(
            " subscribers")
        number = extract_float(text)
        if text and text[-1] in {"K", "M", "B"}:
            if text[-1] == 'K':
                return int(number * 1_000)
            elif text[-1] == 'M':
                return int(number * 1_000_000)
            elif text[-1] == 'B':
                return int(number * 1_000_000_000)
        return int(number)
