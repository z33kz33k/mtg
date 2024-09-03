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
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import cached_property
from http.client import RemoteDisconnected
from operator import attrgetter, itemgetter
from typing import Generator, Iterator

import backoff
import pytubefix
import scrapetube
from httpx import ReadTimeout
from requests import HTTPError, Timeout
from selenium.common.exceptions import TimeoutException
from youtubesearchpython import Channel as YtspChannel

from mtgcards import FILENAME_TIMESTAMP_FORMAT, Json, OUTPUT_DIR, PathLike
from mtgcards.deck import Deck
from mtgcards.deck.arena import ArenaParser, get_arena_lines
from mtgcards.deck.scrapers.aetherhub import AetherhubScraper
from mtgcards.deck.scrapers.archidekt import ArchidektScraper
from mtgcards.deck.scrapers.cardhoarder import CardhoarderScraper
from mtgcards.deck.scrapers.cardsrealm import CardsrealmScraper
from mtgcards.deck.scrapers.deckstats import DeckstatsScraper
from mtgcards.deck.scrapers.flexslot import FlexslotScraper
from mtgcards.deck.scrapers.goldfish import GoldfishScraper
from mtgcards.deck.scrapers.manastack import ManaStackScraper
from mtgcards.deck.scrapers.manatraders import ManatradersScraper
from mtgcards.deck.scrapers.melee import MeleeGgScraper
from mtgcards.deck.scrapers.moxfield import MoxfieldScraper
from mtgcards.deck.scrapers.mtgarenapro import MtgArenaProScraper
from mtgcards.deck.scrapers.mtgazone import MtgaZoneScraper
from mtgcards.deck.scrapers.mtgdecksnet import MtgDecksNetScraper
from mtgcards.deck.scrapers.mtgtop8 import MtgTop8Scraper
from mtgcards.deck.scrapers.penny import PennyDreadfulMagicScraper
from mtgcards.deck.scrapers.scryfall import ScryfallScraper
from mtgcards.deck.scrapers.starcitygames import StarCityGamesScraper
from mtgcards.deck.scrapers.streamdecker import StreamdeckerScraper
from mtgcards.deck.scrapers.traders import MtgoTradersScraper
from mtgcards.deck.scrapers.tappedout import TappedoutScraper
from mtgcards.deck.scrapers.tcgplayer import NewPageTcgPlayerScraper, OldPageTcgPlayerScraper
from mtgcards.deck.scrapers.untapped import UntappedProfileDeckScraper, UntappedRegularDeckScraper
from mtgcards.scryfall import all_formats
from mtgcards.utils import deserialize_dates, extract_float, getrepr, multiply_by_symbol, \
    sanitize_filename, serialize_dates, timed
from mtgcards.utils.files import getdir
from mtgcards.utils.gsheets import extend_gsheet_rows_with_cols, retrieve_from_gsheets_cols
from mtgcards.utils.scrape import extract_source, extract_url, get_dynamic_soup_by_xpath, \
    http_requests_counted, throttled, timed_request, unshorten
from utils.scrape import ScrapingError, throttle_with_countdown

_log = logging.getLogger(__name__)


CHANNELS_DIR = OUTPUT_DIR / "channels"
DORMANT_STALENESS = 30 * 3  # days
ABANDONED_STALENESS = 30 * 12  # days
DECK_STALENESS = 50  # videos


@dataclass
class ChannelData:
    url: str
    id: str | None
    title: str | None
    description: str | None
    tags: list[str] | None
    subscribers: int
    scrape_time: datetime
    videos: list[dict]

    @property
    def decks(self) -> list[dict]:
        return [d for v in self.videos for d in v["decks"]]

    @property
    def sources(self) -> list[str]:
        return sorted({s for v in self.videos for s in v["sources"]})

    @property
    def deck_sources(self) -> Counter:
        return Counter(d["metadata"]["source"] for d in self.decks)

    @property
    def deck_formats(self) -> Counter:
        return Counter(d["metadata"]["format"] for d in self.decks if d["metadata"].get("format"))

    @property
    def staleness(self) -> int | None:
        return (date.today() - self.videos[0]["publish_time"].date()).days if self.videos else None

    @property
    def deck_staleness(self) -> int:
        """Return number of last scraped videos without a deck.
        """
        if not self.decks:
            return len(self.videos)
        video_ids = [v["id"] for v in self.videos]
        deck_ids = [v["id"] for v in self.videos if v["decks"]]
        return len(self.videos[:video_ids.index(deck_ids[0])])

    @property
    def span(self) -> int | None:
        if self.videos:
            return (self.videos[0]["publish_time"].date() - self.videos[-1]["publish_time"].date(
                )).days
        return None

    @property
    def posting_interval(self) -> float | None:
        return self.span / len(self.videos) if self.videos else None

    @property
    def total_views(self) -> int:
        return sum(v["views"] for v in self.videos)

    @property
    def subs_activity(self) -> float | None:
        """Return ratio of subscribers needed to generate one video view in inverted relation to 10
        subscribers, if available.

        The greater this number the more active the subscribers. 1 means 10 subscribers are
        needed to generate one video view. 2 means 5 subscribers are needed to generate one
        video view, 10 means 1 subscriber is needed one and so on.
        """
        avg_views = self.total_views / len(self.videos)
        return 10 / (self.subscribers / avg_views) if self.subscribers else None

    @property
    def decks_per_video(self) -> float | None:
        if not self.videos:
            return None
        return len(self.decks) / len(self.videos)


def retrieve_urls() -> list[str]:
    """Retrieve channel URLs from a private Google Sheet spreadsheet.

    Mind that this operation takes about 4 seconds to complete.
    """
    return retrieve_from_gsheets_cols("mtga_yt", "channels", (3, ), start_row=2)[0]


def channels_batch(start_row=2, batch_size: int | None = None) -> Iterator[str]:
    if start_row < 2:
        raise ValueError("Start row must not be lesser than 2")
    if batch_size is not None and batch_size < 1:
        raise ValueError("Batch size must be a positive integer or None")
    txt = f" {batch_size}" if batch_size else ""
    _log.info(f"Batch updating{txt} channels...")
    start_idx = start_row - 2
    end_idx = None if batch_size is None else start_row - 2 + batch_size
    return itertools.islice(retrieve_urls(), start_idx, end_idx)


def load_channel(channel_url: str) -> ChannelData:
    """Load all earlier scraped data for a channel designated by the provided URL.
    """
    channel_dir = getdir(CHANNELS_DIR / Channel.url2handle(channel_url.rstrip("/")))
    _log.info(f"Loading channel data from: '{channel_dir}'...")
    files = [f for f in channel_dir.iterdir() if f.is_file() and f.suffix.lower() == ".json"]
    if not files:
        raise FileNotFoundError(f"No channel files found at: '{channel_dir}'")
    channels = []
    for file in files:
        channel = json.loads(file.read_text(encoding="utf-8"), object_hook=deserialize_dates)
        channels.append(ChannelData(**channel))
    channels.sort(key=attrgetter("scrape_time"), reverse=True)

    seen, videos = set(), []
    for video in itertools.chain(*[c.videos for c in channels]):
        if video["id"] in seen:
            continue
        seen.add(video["id"])
        videos.append(video)
    videos.sort(key=itemgetter("publish_time"), reverse=True)

    return ChannelData(
        url=channels[0].url,
        id=channels[0].id,
        title=channels[0].title,
        description=channels[0].description,
        tags=channels[0].tags,
        subscribers=channels[0].subscribers,
        scrape_time=channels[0].scrape_time,
        videos=videos,
    )


def load_channels() -> Generator[ChannelData, None, None]:
    """Load channel data for all channels recorded in a private Google Sheet.
    """
    for url in retrieve_urls():
        yield load_channel(url)


def update_gsheet() -> None:
    """Update "channels" Google Sheets worksheet.
    """
    data = []
    for url in retrieve_urls():
        try:
            ch = load_channel(url)
            formats = sorted(ch.deck_formats.items(), key=itemgetter(1), reverse=True)
            formats = [pair[0] for pair in formats]
            deck_sources = sorted(ch.deck_sources.items(), key=itemgetter(1), reverse=True)
            deck_sources = [pair[0] for pair in deck_sources]
            data.append([
                url,
                ch.scrape_time.date().strftime("%Y-%m-%d"),
                ch.staleness if ch.staleness is not None else "N/A",
                ch.posting_interval if ch.posting_interval is not None else "N/A",
                len(ch.videos),
                len(ch.decks),
                ch.deck_staleness,
                ch.total_views,
                ch.subs_activity if ch.subs_activity is not None else "N/A",
                ch.decks_per_video or 0,
                ch.subscribers or "N/A",
                ", ".join(formats),
                ", ".join(deck_sources),
                ", ".join(ch.sources),
            ])
        except FileNotFoundError:
            _log.warning(f"Channel data for {url!r} not found. Skipping...")
            data.append(
                ["NOT AVAILABLE", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                 "N/A"])
        except AttributeError as err:
            _log.warning(f"Corrupted Channel data for {url!r}: {err}. Skipping...")
            data.append(
                ["NOT AVAILABLE", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                 "N/A"])

    extend_gsheet_rows_with_cols("mtga_yt", "channels", data, start_row=2, start_col=5)


@http_requests_counted("channels scraping")
@timed("channels scraping", precision=1)
def scrape_channels(
        *urls: str,
        videos=25,
        only_earlier_than_last_scraped=True) -> None:
    """Scrape YouTube channels specified in private Google Sheet. Save the scraped data as .json
    files.

    Args:
        urls: URLs of channels to scrape
        videos: number of videos to scrape per channel
        only_earlier_than_last_scraped: if True, only scrape videos earlier than the last one scraped
    """
    count, total_count = 0, 0
    for i, url in enumerate(urls, start=1):
        try:
            ch = Channel(url, only_earlier_than_last_scraped=only_earlier_than_last_scraped)
            _log.info(f"Scraping channel {i}/{len(urls)}: {ch.handle!r}...")
            ch.scrape(videos)
            if ch.data:
                dst = getdir(CHANNELS_DIR / ch.handle)
                ch.dump(dst)
                count += len(ch.videos)
                total_count += len(ch.videos)
        except ScrapingError as se:
            _log.warning(f"Scraping of channel {url!r} failed with: '{se}'. Skipping...")
        if count > 500:
            count = 0
            _log.info(f"Throttling for 5 minutes before the next batch...")
            throttle_with_countdown(5 * 60)

    _log.info(f"Scraped {total_count} video(s) from {len(urls)} channel(s)")


def scrape_non_dormant(
        videos=25, only_earlier_than_last_scraped=True, only_non_deck_stale=True) -> None:
    """Scrape these YouTube channels specified in private Google Sheet that are not dormant. Save
    the scraped data as .json files.
    """
    urls = []
    for url in retrieve_urls():
        try:
            data = load_channel(url)
        except FileNotFoundError:
            data = None
        if not data:
            urls.append(url)
        elif not data.staleness:
            urls.append(url)
        elif data.staleness <= DORMANT_STALENESS:
            if only_non_deck_stale and data.deck_staleness > DECK_STALENESS:
                continue
            urls.append(url)
    text = "non-dormant and non-deck-stale" if only_non_deck_stale else "non-dormant"
    _log.info(f"Scraping {len(urls)} {text} channel(s)...")
    scrape_channels(
        *urls, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_non_abandoned(
        videos=25, only_earlier_than_last_scraped=True, only_non_deck_stale=True) -> None:
    """Scrape these YouTube channels specified in private Google Sheet that are not abandoned. Save
    the scraped data as .json files.
    """
    urls = []
    for url in retrieve_urls():
        try:
            data = load_channel(url)
        except FileNotFoundError:
            data = None
        if not data:
            urls.append(url)
        elif not data.staleness:
            urls.append(url)
        elif data.staleness <= ABANDONED_STALENESS:
            if only_non_deck_stale and data.deck_staleness > DECK_STALENESS:
                continue
            urls.append(url)
    text = "non-abandoned and non-deck-stale" if only_non_deck_stale else "non-abandoned"
    _log.info(f"Scraping {len(urls)} {text} channel(s)...")
    scrape_channels(
        *urls, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_dormant(
        videos=25, only_earlier_than_last_scraped=True, only_non_deck_stale=True) -> None:
    """Scrape these YouTube channels specified in private Google Sheet that are dormant. Save
    the scraped data as .json files.
    """
    urls = []
    for url in retrieve_urls():
        try:
            data = load_channel(url)
        except FileNotFoundError:
            data = None
        if data and data.staleness and ABANDONED_STALENESS >= data.staleness > DORMANT_STALENESS:
            if only_non_deck_stale and data.deck_staleness > DECK_STALENESS:
                continue
            urls.append(url)
    _log.info(f"Scraping {len(urls)} dormant channel(s)...")
    scrape_channels(
        *urls, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_abandoned(
        videos=25, only_earlier_than_last_scraped=True, only_non_deck_stale=True) -> None:
    """Scrape these YouTube channels specified in private Google Sheet that are abandoned. Save
    the scraped data as .json files.
    """
    urls = []
    for url in retrieve_urls():
        try:
            data = load_channel(url)
        except FileNotFoundError:
            data = None
        if data and data.staleness and data.staleness > ABANDONED_STALENESS:
            if only_non_deck_stale and data.deck_staleness > DECK_STALENESS:
                continue
            urls.append(url)
    _log.info(f"Scraping {len(urls)} abandoned channel(s)...")
    scrape_channels(
        *urls, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_deck_stale(videos=25, only_earlier_than_last_scraped=True) -> None:
    """Scrape these YouTube channels specified in private Google Sheet that are considered
    deck-stale. Save the scraped data as .json files.
    """
    urls = []
    for url in retrieve_urls():
        try:
            data = load_channel(url)
        except FileNotFoundError:
            data = None
        if data and data.deck_staleness > DECK_STALENESS:
            urls.append(url)
    _log.info(f"Scraping {len(urls)} deck-stale channel(s)...")
    scrape_channels(
        *urls, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def get_aggregate_deck_data() -> tuple[Counter, Counter]:
    """Get aggregated deck data across all channels.
    """
    decks = [d for ch in load_channels() for d in ch.decks]
    sources = []
    for d in decks:
        src = d["metadata"]["source"]
        src = src.removeprefix("www.") if src.startswith("www.") else src
        if "tcgplayer" in src:
            _, *parts = src.split(".")
            src = ".".join(parts)
        elif MeleeGgScraper.ALT_DOMAIN in src:
            src = "melee.gg"
        sources.append(src)
    source_counter = Counter(sources)
    format_counter = Counter([d["metadata"]["format"] for d in decks if d["metadata"].get("format")])
    return source_counter, format_counter


class Video:
    """YouTube video showcasing a MtG deck with its most important metadata.
    """
    URL_TEMPLATE = "https://www.youtube.com/watch?v={}"

    SHORTENER_HOOKS = {
        "73.nu/",
        "bit.ly/",
        "bitly.kr/",
        "bl.ink/",
        "bli.nk/",
        "buff.ly/",
        "clicky.me/",
        "cutt.ly/",
        "dub.co/",
        "dub.sh/",
        "fox.ly/",
        "gg.gg/",
        "han.gl/",
        "is.gd/",
        "kurzelinks.de/",
        "kutt.it/",
        "lstu.fr/",
        "lyksoomu.com/",
        "lyn.bz/",
        "name.com/",
        "oe.cd/",
        "ow.ly/",
        "qti.ai/",
        "rb.gy/",
        "rebrandly.com/",
        "reduced.to/",
        "rip.to/",
        "san.aq/",
        "short.io/",
        "shortcm.li/",
        "shorten-url.com/",
        "shorturl.at/",
        "snip.ly/",
        "sor.bz/",
        "spoo.me/",
        "switchy.io/",
        "t.ly/",
        "tinu.be/",
        "tiny.cc/",
        "tinyurl.com/",
        "urlr.me/",
        "urlzs.com/",
        "v.gd/",
        "vo.la/",
        "yaso.su/",
        "zlnk.com/",
        "zws.im/",
    }

    PASTEBIN_LIKE_HOOKS = {
        "bitbin.it/",
        "bpa.st/",
        "cl1p.net/",
        "codebeautify.org/",
        "codeshare.io/",
        "commie.io/",
        "controlc.com/",
        "cutapaste.net/",
        "defuse.ca/pastebin.htm/",
        "dotnetfiddle.net/",
        "dpaste.com/",
        "dpaste.org/",
        "everfall.com/paste/",
        "friendpaste.com/",
        "gist.github.com/",
        "hastebin.com/",
        "ide.geeksforgeeks.org/",
        "ideone.com/",
        "ivpaste.com/",
        "jpst.it/",
        "jsbin.com/",
        "jsfiddle.net/",
        "jsitor.com/",
        "justpaste.it/",
        "justpaste.me/",
        "kpaste.net/",
        "n0paste.tk/",
        "nekobin.com/",
        "notes.io/",
        "p.ip.fi/",
        "paste-bin.xyz/",
        "paste.centos.org/",
        "paste.debian.net/",
        "paste.ee/",
        "paste.jp/",
        "paste.mozilla.org/",
        "paste.ofcode.org/",
        "paste.opensuse.org/",
        "paste.org.ru/",
        "paste.rohitab.com/",
        "paste.sh/",
        "paste2.org/",
        "pastebin.ai/",
        "pastebin.com/",
        "pastebin.fi/",
        "pastebin.fr/",
        "pastebin.osuosl.org/",
        "pastecode.io/",
        "pasted.co/",
        "pasteio.com/",
        "pastelink.net/",
        "pastie.org/",
        "privatebin.net/",
        "pst.innomi.net/",
        "quickhighlighter.com/",
        "termbin.com/",
        "tny.cz/",
        "tutpaste.com/",
        "vpaste.net/",
        "www.paste.lv/",
        "www.paste4btc.com/",
        "www.pastebin.pt/",
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
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def keywords(self) -> list[str] | None:
        return sorted(self._keywords) if self._keywords else None

    @property
    def publish_time(self) -> datetime:
        return self._publish_time

    @property
    def views(self) -> int:
        return self._views

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @property
    def channel_subscribers(self) -> int | None:
        return self._channel_subscribers

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
    def sources(self) -> list[str]:
        return sorted(self._sources)

    @property
    def derived_format(self) -> str:
        return self._derived_format

    @property
    def decks(self) -> list[Deck]:
        return self._decks

    @property
    def metadata(self) -> Json:
        return {"format": self.derived_format} if self.derived_format else {}

    def __init__(self, video_id: str) -> None:
        """Initialize.

        Args:
            video_id: unique string identifying a YouTube video (the part after `v=` in the URL)
        """
        self._process(video_id)

    @throttled(2, 0.45)
    def _process(self, video_id):
        _log.info(f"Scraping video: 'https://www.youtube.com/watch?v={video_id}'...")
        self._id = video_id
        try:
            self._pytube = self._get_pytube()
        except (RemoteDisconnected, ScrapingError) as e:
            _log.warning(
                f"`pytube` had a hiccup ({e}). Retrying with backoff (60 seconds max)...")
            self._pytube = self._get_pytube_with_backoff()
        # description and title is also available in scrapetube data on Channel level
        self._author, self._description, self._title = None, None, None
        self._keywords, self._publish_time, self._views = None, None, None
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
            ("decks", len(self.decks)),
            ("publish_time", str(self.publish_time)),
            ("views", self.views)
        )

    def _get_pytube(self) -> pytubefix.YouTube:
        data = pytubefix.YouTube(self.url, use_oauth=True, allow_oauth_cache=True)
        if not data.publish_date:
            raise ScrapingError("pytube data missing publish date")
        return data

    @backoff.on_exception(
        backoff.expo, (Timeout, HTTPError, RemoteDisconnected, ScrapingError), max_time=300)
    def _get_pytube_with_backoff(self) -> pytubefix.YouTube:
        return self._get_pytube()

    def _extract_subscribers(self) -> int | None:
        pattern = r'(\d+(?:\.\d+)?)\s*([KMB]?)\s*subscribers'
        match = re.search(pattern, self._pytube.embed_html)

        if match:
            # extract the number and suffix from the match
            number = float(match.group(1))
            suffix = match.group(2)
            return multiply_by_symbol(number, suffix)

        return None

    def _get_pytube_data(self) -> None:
        self._author = self._pytube.author
        self._description = self._pytube.description
        self._title = self._pytube.title
        self._keywords = self._pytube.keywords
        self._publish_time = self._pytube.publish_date
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
                    if not len(deck_lines) > 1:
                        other_lines.append(line)
                elif line == "Sideboard":
                    sideboard_lines.append(line)
                    if not len(sideboard_lines) > 1:
                        other_lines.append(line)
                # prevent parsing two decklists as one
                elif not len(deck_lines) > 1 and not len(sideboard_lines) > 1:
                    other_lines.append(line)
        return links, [*get_arena_lines(*other_lines)]

    def _scrape_deck(self, link: str) -> Deck | None:
        if AetherhubScraper.is_deck_url(link):
            return AetherhubScraper(link, self.metadata, throttled=True).deck
        elif ArchidektScraper.is_deck_url(link):
            return ArchidektScraper(link, self.metadata).deck
        elif CardhoarderScraper.is_deck_url(link):
            return CardhoarderScraper(link, self.metadata).deck
        elif CardsrealmScraper.is_deck_url(link):
            return CardsrealmScraper(link, self.metadata).deck
        elif DeckstatsScraper.is_deck_url(link):
            return DeckstatsScraper(link, self.metadata).deck
        elif FlexslotScraper.is_deck_url(link):
            return FlexslotScraper(link, self.metadata).deck
        elif GoldfishScraper.is_deck_url(link):
            return GoldfishScraper(link, self.metadata, throttled=True).deck
        elif ManaStackScraper.is_deck_url(link):
            return ManaStackScraper(link, self.metadata).deck
        elif ManatradersScraper.is_deck_url(link):
            return ManatradersScraper(link, self.metadata).deck
        elif MeleeGgScraper.is_deck_url(link):
            return MeleeGgScraper(link, self.metadata).deck
        elif MoxfieldScraper.is_deck_url(link):
            return MoxfieldScraper(link, self.metadata, throttled=True).deck
        elif MtgaZoneScraper.is_deck_url(link):
            return MtgaZoneScraper(link, self.metadata).deck
        elif MtgArenaProScraper.is_deck_url(link):
            return MtgArenaProScraper(link, self.metadata).deck
        elif MtgDecksNetScraper.is_deck_url(link):
            return MtgDecksNetScraper(link, self.metadata).deck
        elif MtgoTradersScraper.is_deck_url(link):
            return MtgoTradersScraper(link, self.metadata).deck
        elif MtgTop8Scraper.is_deck_url(link):
            return MtgTop8Scraper(link, self.metadata).deck
        elif NewPageTcgPlayerScraper.is_deck_url(link):
            return NewPageTcgPlayerScraper(link, self.metadata).deck
        elif OldPageTcgPlayerScraper.is_deck_url(link):
            return OldPageTcgPlayerScraper(link, self.metadata).deck
        elif PennyDreadfulMagicScraper.is_deck_url(link):
            return PennyDreadfulMagicScraper(link, self.metadata).deck
        elif StarCityGamesScraper.is_deck_url(link):
            return StarCityGamesScraper(link, self.metadata).deck
        elif ScryfallScraper.is_deck_url(link):
            return ScryfallScraper(link, self.metadata).deck
        elif StreamdeckerScraper.is_deck_url(link):
            return StreamdeckerScraper(link, self.metadata).deck
        elif TappedoutScraper.is_deck_url(link):
            return TappedoutScraper(link, self.metadata, throttled=True).deck
        elif UntappedProfileDeckScraper.is_deck_url(link):
            return UntappedProfileDeckScraper(link, self.metadata).deck
        elif UntappedRegularDeckScraper.is_deck_url(link):
            return UntappedRegularDeckScraper(link, self.metadata).deck
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
            # TODO: decide if scraping a video (or channel for that matter)
            #  with such a hiccup should be allowed
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

    @property
    def json(self) -> str:
        data = {
            "id": self.id,
            "url": self.url,
            "author": self.author,
            "title": self.title,
            "description": self.description,
            "keywords": self.keywords,
            "publish_time": self.publish_time,
            "views": self.views,
            "sources": self.sources,
            "derived_format": self.derived_format,
            "decks": [json.loads(d.json, object_hook=deserialize_dates) for d in self.decks],
        }
        return json.dumps(data, indent=4, ensure_ascii=False, default=serialize_dates)

    def dump(self, dstdir: PathLike = "", name="") -> None:
        """Dump to a .json file.

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            name: optionally, a custom name for the exported video (if not provided a default name is used)
        """
        dstdir = dstdir or OUTPUT_DIR / "json"
        dstdir = getdir(dstdir)
        timestamp = self.publish_time.strftime(FILENAME_TIMESTAMP_FORMAT)
        name = name or f"{self.author}_{timestamp}_video"
        dst = dstdir / f"{sanitize_filename(name)}.json"
        _log.info(f"Exporting video to: '{dst}'...")
        dst.write_text(self.json, encoding="utf-8")


class Channel:
    """YouTube channel showcasing MtG decks.
    """
    @property
    def url(self) -> str:
        return self._url.rstrip("/")

    @property
    def handle(self) -> str:
        return self.url2handle(self.url)

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
        return sorted(set(self._tags)) if self._tags else None

    @property
    def subscribers(self) -> int | None:
        return self._subscribers

    @property
    def scrape_time(self) -> datetime | None:
        return self._scrape_time

    @property
    def videos(self) -> list[Video]:
        return self._videos

    @property
    def decks(self) -> list[Deck]:
        return [d for v in self.videos for d in v.decks]

    @property
    def data(self) -> ChannelData | None:
        return self._data

    @property
    def earlier_data(self) -> ChannelData | None:
        return self._earlier_data

    def __init__(self, url: str, only_earlier_than_last_scraped=True) -> None:
        self._url, self._only_earlier_than_last = url, only_earlier_than_last_scraped
        self._id, self._title, self._description, self._tags = None, None, None, None
        self._subscribers, self._scrape_time, self._videos = None, None, []
        self._ytsp_data, self._data = None, None
        try:
            self._earlier_data = load_channel(self.url)
        except FileNotFoundError:
            self._earlier_data = None

    def get_unscraped_ids(self, limit=10) -> list[str]:
        scraped_ids = [v["id"] for v in self.earlier_data.videos] if self.earlier_data else []
        if not scraped_ids:
            last_scraped_id = None
        else:
            last_scraped_id = scraped_ids[0] if self._only_earlier_than_last else None

        video_ids, scraped_ids = [], set(scraped_ids)
        count = 0
        for vid in self.video_ids(self.url, limit=limit):
            count += 1
            if vid == last_scraped_id:
                break
            elif vid not in scraped_ids:
                video_ids.append(vid)

        if not count:
            raise ScrapingError(
                "scrapetube failed to yield any video IDs. Are you sure the channel has a 'Videos' "
                "tab?")

        return video_ids

    @timed("channel scraping", precision=2)
    def scrape(self, limit=10) -> None:
        video_ids = self.get_unscraped_ids(limit)
        if not video_ids:
            _log.info(f"Channel data for {self.handle!r} already up to date")
            return
        self._scrape_time = datetime.now()
        _log.info(f"Scraping channel: {self.url!r}, {len(video_ids)} video(s)...")
        self._videos = [Video(vid) for vid in video_ids]
        self._id = self.videos[0].channel_id if self else None
        try:
            self._ytsp_data = self._get_ytsp() if self._id else None
        except ReadTimeout:
            self._ytsp_data = self._get_ytsp_with_backoff()
        self._description = self._ytsp_data.result.get("description") if self._id else None
        self._title = self._ytsp_data.result.get("title") if self._id else None
        self._tags = self._ytsp_data.result.get("tags") if self._id else None
        self._subscribers = self._parse_subscribers() if self._id else None
        if not self._subscribers:
            self._subscribers = self.videos[0].channel_subscribers
            if self._subscribers is None:
                self._subscribers = self._scrape_subscribers_with_selenium()
        self._data = ChannelData(
            url=self.url,
            id=self.id,
            title=self.title,
            description=self.description,
            tags=self.tags,
            subscribers=self.subscribers,
            scrape_time=self.scrape_time,
            videos=[json.loads(v.json, object_hook=deserialize_dates) for v in self.videos],
        )

    @staticmethod
    def video_ids(url: str, limit=10) -> Generator[str, None, None]:
        try:
            for ch_data in scrapetube.get_channel(channel_url=url, limit=limit):
                yield ch_data["videoId"]
        except OSError:
            raise ValueError(f"Invalid URL: {url!r}")
        except json.decoder.JSONDecodeError:
            raise ScrapingError(
                "scrapetube failed with JSON error. This channel probably doesn't exist "
                "anymore")

    def __repr__(self) -> str:
        return getrepr(
            self.__class__,
            ("handle", self.handle),
            ("videos", len(self.videos)),
            ("decks", len(self.decks)),
            ("scrape_time", str(self.scrape_time)),
        )

    @staticmethod
    def url2handle(url: str) -> str:
        if "@" not in url and "/c/" not in url:
            raise ValueError(f"Not a channel URL: {url!r}")
        _, handle = url.rsplit("/", maxsplit=1)
        if "/c/" in url:
            handle = f"c_{handle}"
        return handle

    def _get_ytsp(self) -> YtspChannel:
        return YtspChannel(self.id)

    @backoff.on_exception(
        backoff.expo, (Timeout, HTTPError, RemoteDisconnected, ReadTimeout), max_time=300)
    def _get_ytsp_with_backoff(self) -> YtspChannel:
        return self._get_ytsp()

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
        try:
            soup, _, _ = get_dynamic_soup_by_xpath(self.url, xpath, consent_xpath=consent_xpath)
            text = soup.find("span", string=lambda t: t and "subscribers" in t).text.removesuffix(
                " subscribers")
            number = extract_float(text)
            if text and text[-1] in {"K", "M", "B", "T"}:
                return multiply_by_symbol(number, text[-1])
            return int(number)
        except TimeoutException:  # looking for "subscribers" is futile if there's only one :)
            return 1

    @property
    def json(self) -> str:
        return json.dumps(asdict(self.data), indent=4, ensure_ascii=False, default=serialize_dates)

    def dump(self, dstdir: PathLike = "", name="") -> None:
        """Dump to a .json file.

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            name: optionally, a custom name for the exported video (if not provided a default name is used)
        """
        dstdir = dstdir or OUTPUT_DIR / "json"
        dstdir = getdir(dstdir)
        timestamp = self.scrape_time.strftime(FILENAME_TIMESTAMP_FORMAT)
        handle = self.handle.removeprefix("@").removeprefix("c_")
        name = name or f"{handle}_{timestamp}_channel"
        dst = dstdir / f"{sanitize_filename(name)}.json"
        _log.info(f"Exporting channel to: '{dst}'...")
        dst.write_text(self.json, encoding="utf-8")
