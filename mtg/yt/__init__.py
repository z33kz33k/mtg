"""

    mtg.yt.py
    ~~~~~~~~~~~~~~
    Scrape YouTube.

    @author: z33k

"""
import itertools
import json
import logging
import re
import shutil
import urllib.error
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from functools import cached_property
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Callable, Generator, Iterable

import backoff
import httpcore
import httpx
import pytubefix
import pytubefix.exceptions
import scrapetube
from requests import HTTPError, ReadTimeout, Timeout
from selenium.common.exceptions import TimeoutException
from youtube_comment_downloader import SORT_BY_POPULAR, YoutubeCommentDownloader
from youtubesearchpython import Channel as YtspChannel

from mtg import FILENAME_TIMESTAMP_FORMAT, Json, OUTPUT_DIR, PathLike, SECRETS
from mtg.deck import Deck, SANITIZED_FORMATS
from mtg.deck.arena import ArenaParser, get_arena_lines, group_arena_lines
from mtg.deck.scrapers import DeckScraper, DeckTagsContainerScraper, DeckUrlsContainerScraper, \
    DecksJsonContainerScraper, HybridContainerScraper
from mtg.scryfall import all_formats
from mtg.utils import Counter, deserialize_dates, extract_float, find_longest_seqs, \
    from_iterable, getrepr, multiply_by_symbol, sanitize_filename, serialize_dates, timed
from mtg.utils.files import getdir
from mtg.utils.scrape import ScrapingError, extract_source, extract_url, \
    http_requests_counted, throttle_with_countdown, throttled, \
    timed_request, unshorten
from mtg.utils.scrape.dynamic import get_dynamic_soup
from mtg.utils.scrape.linktree import Linktree
from mtg.yt.data import CHANNELS_DIR, CHANNEL_URL_TEMPLATE, ChannelData, DataPath, \
    ScrapingSession, VIDEO_URL_TEMPLATE, find_channel_files, find_orphans, load_channel, \
    load_channels, prune_channel_data_file, retrieve_ids, sanitize_source

_log = logging.getLogger(__name__)


GOOGLE_API_KEY = SECRETS["google"]["api_key"]  # not used anywhere
DEAD_THRESHOLD = 2500  # days (ca. 7 yrs) - only used in gsheet to trim dead from abandoned
MAX_VIDEOS = 400


def back_up_channel_files(chid: str, *files: PathLike) -> None:
    now = datetime.now()
    timestamp = f"{now.year}{now.month:02}{now.day:02}"
    backup_root = getdir(OUTPUT_DIR / "_archive" / "channels")
    backup_path, counter = backup_root / timestamp / chid, itertools.count(1)
    while backup_path.exists():
        backup_path = backup_root / timestamp /  f"{chid} ({next(counter)})"
    backup_dir = getdir(backup_path)
    for f in files:
        f = Path(f)
        dst = backup_dir / f.name
        _log.info(f"Backing-up '{f}' to '{dst}'...")
        shutil.copy(f, dst)


def _process_videos(channel_id: str, *video_ids: str, skip_earlier_scraped_deck_urls=True) -> None:
    files = find_channel_files(channel_id, *video_ids)
    if not files:
        return
    back_up_channel_files(channel_id, *files)
    if scrape_channel_videos(
            channel_id, *video_ids, skip_earlier_scraped_deck_urls=skip_earlier_scraped_deck_urls):
        for f in files:
            prune_channel_data_file(f, *video_ids)


def rescrape_missing_decklists() -> None:
    """Re-scrape those YT videos that contain decklists that are missing from global decklists
    repositories.
    """
    decklist_paths = {p for lst in find_orphans().values() for p in lst}
    channels = defaultdict(set)
    for path in [DataPath.from_path(p) for p in decklist_paths]:
        channels[path.channel_id].add(path.video_id)

    if not channels:
        _log.info("No videos found that needed re-scraping")
        return

    for i, (channel_id, video_ids) in enumerate(channels.items(), start=1):
        _log.info(f"Re-scraping {i}/{len(channels)} channel for missing decklists data...")
        _process_videos(channel_id, *video_ids, skip_earlier_scraped_deck_urls=False)


def rescrape_videos(
        *chids: str, video_filter: Callable[[dict], bool] = lambda _: True) -> None:
    """Re-scrape videos across all specified channels. Optionally, define a video-filtering
    predicate.

    The default for scraping is all known channels and all their videos.

    Args:
        *chids: channel IDs
        video_filter: video-filtering predicate
    """
    chids = chids or retrieve_ids()
    channels = defaultdict(list)
    for chid in chids:
        ch = load_channel(chid)
        vids = [v["id"] for v in ch.videos if video_filter(v)]
        if vids:
            channels[chid].extend(vids)

    if not channels:
        _log.info("No videos found that needed re-scraping")
        return

    for i, (channel_id, video_ids) in enumerate(channels.items(), start=1):
        _log.info(f"Re-scraping {len(video_ids)} video(s) of {i}/{len(channels)} channel...")
        # NOTE: disabling 'skip_earlier_scraped_deck_urls' has an upside of no accidental data
        # loss (when decks scraped in the previous video scrape are skipped and then pruned) and
        # a serious downside of many redundant scrapes. Overall, enabling seems to bring better
        # results
        _process_videos(channel_id, *video_ids)


@http_requests_counted("channel videos scraping")
@timed("channel videos scraping", precision=1)
def scrape_channel_videos(
        channel_id: str, *video_ids: str, skip_earlier_scraped_deck_urls=True) -> bool:
    """Scrape specified videos of a YouTube channel in a session.

    Scraped channel's data is saved in a .json file and session ensures decklists are saved
    in global decklists repositories.

    Args:
        channel_id: ID of a channel to scrape
        *video_ids: IDs of videos to scrape
        skip_earlier_scraped_deck_urls: whether to skip previously scraped decklist URLs
    """
    with ScrapingSession() as session:
        total_videos, total_decks = 0, 0
        try:
            ch = Channel(
                channel_id, *session.get_failed(channel_id),
                skip_earlier_scraped_deck_urls=skip_earlier_scraped_deck_urls)
            text = Channel.get_url_and_title(ch.id, ch.title)
            _log.info(f"Scraping {len(video_ids)} video(s) from channel {text}...")
            ch.scrape_videos(*video_ids)
            session.update_failed(ch.id, *ch.already_failed_deck_urls)
            if ch.data:
                dst = getdir(CHANNELS_DIR / channel_id)
                ch.dump(dst)
                total_videos += len(ch.videos)
                total_decks += len(ch.decks)
                for deck in ch.decks:
                    session.update_regular(deck.decklist_id, deck.decklist)
                    session.update_extended(deck.decklist_extended_id, deck.decklist_extended)
        except Exception as err:
            _log.exception(f"Scraping of channel {channel_id!r} failed with: '{err}'")
            return False

        _log.info(f"Scraped {total_decks} deck(s) from {total_videos} video(s)")
    return True


@http_requests_counted("channels scraping")
@timed("channels scraping", precision=1)
def scrape_channels(
        *chids: str,
        videos=25,
        only_earlier_than_last_scraped=True) -> None:
    """Scrape YouTube channels as specified in a session.

    Each scraped channel's data is saved in a .json file and session ensures decklists are saved
    in global decklists repositories.

    Args:
        chids: IDs of channels to scrape
        videos: number of videos to scrape per channel
        only_earlier_than_last_scraped: if True, only scrape videos earlier than the last one scraped
    """
    with ScrapingSession() as session:
        current_videos, total_videos = 0, 0
        total_channels, total_decks = 0, 0
        for i, id_ in enumerate(chids, start=1):
            try:
                ch = Channel(
                    id_, *session.get_failed(id_),
                    only_earlier_than_last_scraped=only_earlier_than_last_scraped)
                text = Channel.get_url_and_title(ch.id, ch.title)
                _log.info(f"Scraping channel {i}/{len(chids)}: {text}...")
                ch.scrape(videos)
                session.update_failed(ch.id, *ch.already_failed_deck_urls)
                if ch.data:
                    dst = getdir(CHANNELS_DIR / id_)
                    ch.dump(dst)
                    current_videos += len(ch.videos)
                    total_videos += len(ch.videos)
                    total_channels += 1
                    total_decks += len(ch.decks)
                    for deck in ch.decks:
                        session.update_regular(deck.decklist_id, deck.decklist)
                        session.update_extended(deck.decklist_extended_id, deck.decklist_extended)
            except Exception as err:
                _log.exception(f"Scraping of channel {id_!r} failed with: '{err}'. Skipping...")
            if current_videos > MAX_VIDEOS:
                current_videos = 0
                _log.info(f"Throttling for 5 minutes before the next batch...")
                throttle_with_countdown(5 * 60)

        _log.info(
            f"Scraped {total_decks} deck(s) from {total_videos} video(s) from {total_channels} "
            f"channel(s)")


def scrape_fresh(
        videos=25, only_earlier_than_last_scraped=True, only_deck_fresh=True) -> None:
    """Scrape those YouTube channels saved in a private Google Sheet that are not active,
    dormant nor abandoned.
    """
    ids = []
    for id_ in retrieve_ids():
        try:
            data = load_channel(id_)
        except FileNotFoundError:
            data = None
        if not data:
            ids.append(id_)
        elif data.is_fresh:
            if only_deck_fresh and not data.is_deck_fresh:
                continue
            ids.append(id_)
    text = "fresh and deck-fresh" if only_deck_fresh else "fresh"
    _log.info(f"Scraping {len(ids)} {text} channel(s)...")
    scrape_channels(
        *ids, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_active(
        videos=25, only_earlier_than_last_scraped=True, only_deck_fresh=True) -> None:
    """Scrape those YouTube channels saved in a private Google Sheet that are active.
    """
    ids = []
    for id_ in retrieve_ids():
        try:
            data = load_channel(id_)
        except FileNotFoundError:
            data = None
        if data and data.is_active:
            if only_deck_fresh and not data.is_deck_fresh:
                continue
            ids.append(id_)
    text = "active and deck-fresh" if only_deck_fresh else "active"
    _log.info(f"Scraping {len(ids)} {text} channel(s)...")
    scrape_channels(
        *ids, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_dormant(
        videos=25, only_earlier_than_last_scraped=True, only_deck_fresh=True) -> None:
    """Scrape those YouTube channels saved in a private Google Sheet that are dormant.
    """
    ids = []
    for id_ in retrieve_ids():
        try:
            data = load_channel(id_)
        except FileNotFoundError:
            data = None
        if data and data.is_dormant:
            if only_deck_fresh and not data.is_deck_fresh:
                continue
            ids.append(id_)
    text = "dormant and deck-fresh" if only_deck_fresh else "dormant"
    _log.info(f"Scraping {len(ids)} {text} channel(s)...")
    scrape_channels(
        *ids, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_abandoned(
        videos=25, only_earlier_than_last_scraped=True, only_deck_fresh=True) -> None:
    """Scrape those YouTube channels saved in a private Google Sheet that are abandoned.
    """
    ids = []
    for id_ in retrieve_ids():
        try:
            data = load_channel(id_)
        except FileNotFoundError:
            data = None
        if data and data.is_abandoned:
            if only_deck_fresh and not data.is_deck_fresh:
                continue
            ids.append(id_)
    text = "abandoned and deck-fresh" if only_deck_fresh else "abandoned"
    _log.info(f"Scraping {len(ids)} {text} channel(s)...")
    scrape_channels(
        *ids, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_deck_stale(
        videos=25, only_earlier_than_last_scraped=True, only_fresh_or_active=True) -> None:
    """Scrape those YouTube channels saved in a private Google Sheet that are considered
    deck-stale.
    """
    ids = []
    for id_ in retrieve_ids():
        try:
            data = load_channel(id_)
        except FileNotFoundError:
            data = None
        if data and data.is_deck_stale:
            if only_fresh_or_active and not (data.is_fresh or data.is_active):
                continue
            ids.append(id_)
    text = "deck-stale and fresh/active" if only_fresh_or_active else "deck-stale"
    _log.info(f"Scraping {len(ids)} {text} channel(s)...")
    scrape_channels(
        *ids, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_very_deck_stale(
        videos=25, only_earlier_than_last_scraped=True, only_fresh_or_active=True) -> None:
    """Scrape those YouTube channels saved in a private Google Sheet that are considered
    very deck-stale.
    """
    ids = []
    for id_ in retrieve_ids():
        try:
            data = load_channel(id_)
        except FileNotFoundError:
            data = None
        if data and data.is_very_deck_stale:
            if only_fresh_or_active and not (data.is_fresh or data.is_active):
                continue
            ids.append(id_)
    text = "very deck-stale and fresh/active" if only_fresh_or_active else "very deck-stale"
    _log.info(f"Scraping {len(ids)} {text} channel(s)...")
    scrape_channels(
        *ids, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_excessively_deck_stale(
        videos=25, only_earlier_than_last_scraped=True, only_fresh_or_active=True) -> None:
    """Scrape those YouTube channels saved in a private Google Sheet that are considered
    excessively deck-stale.
    """
    ids = []
    for id_ in retrieve_ids():
        try:
            data = load_channel(id_)
        except FileNotFoundError:
            data = None
        if data and data.is_excessively_deck_stale:
            if only_fresh_or_active and not (data.is_fresh or data.is_active):
                continue
            ids.append(id_)
    text = "excessively deck-stale and fresh/active" if only_fresh_or_active else (
        "excessively deck-stale")
    _log.info(f"Scraping {len(ids)} {text} channel(s)...")
    scrape_channels(
        *ids, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


class Video:
    """YouTube video showcasing a MtG deck with its most important metadata.
    """
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
        "pxf.io",  # e.g. tcgplayer.pxf.io affiliate referral link
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
    _THROTTLED = (
        "aetherhub.com",
        "deckstats.net",
        "hareruyamtg.com"
        "moxfield.com",
        "mtggoldfish.com",
        "tappedout.net",
    )

    @property
    def id(self) -> str:
        return self._id

    @property
    def url(self) -> str:
        return VIDEO_URL_TEMPLATE.format(self.id)

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
    def decks(self) -> list[Deck]:
        return self._decks

    @property
    def metadata(self) -> Json:
        metadata = {}
        if self._derived_format:
            metadata["format"] = self._derived_format
        if self._derived_name:
            metadata["name"] = self._derived_name
        if self.author:
            metadata["author"] = self.author
        if self.publish_time:
            metadata["date"] = self.publish_time.date()
        return metadata

    @property
    def failed_deck_urls(self) -> set[str]:
        return self._failed_deck_urls

    def __init__(
            self, video_id: str, already_scraped_deck_urls: Iterable[str] = (),
            already_failed_deck_urls: Iterable[str] = ()) -> None:
        """Initialize.

        Args:
            video_id: unique string identifying a YouTube video (the part after `v=` in the URL)
            already_scraped_deck_urls: URLs of decks that have already been scraped within a channel
            already_failed_deck_urls: URLs of decks that have already failed to be scraped
        """
        self._already_scraped_deck_urls = set(already_scraped_deck_urls)
        self._already_failed_deck_urls = set(already_failed_deck_urls)
        self._failed_deck_urls = set()
        self._process(video_id)

    @throttled(1.25, 0.25)
    def _process(self, video_id):
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

    def _parse_linktree(self) -> list[str]:
        links = []
        for link in self.links:
            if Linktree.is_linktree_url(link):
                new_links = [l for l in Linktree(link).data.links if l not in self.links]
                _log.info(f"Parsed {len(new_links)} new link(s) from: {link!r}")
                links.extend(new_links)
            else:
                links.append(link)
        return links

    @timed("gathering video data")
    def _scrape(self):
        self._get_pytube_data()
        self._format_soup = self._get_format_soup()
        self._derived_format = self._derive_format()
        self._derived_name = self._derive_name()
        self._links, self._arena_lines = self._parse_lines(*self._desc_lines)
        self._links = self._parse_linktree()
        self._decks = self._collect(self._links, self._arena_lines)
        if not self._decks:  # try with author's comment
            comment_lines = self._get_comment_lines()
            if comment_lines:
                links, arena_lines = self._parse_lines(*comment_lines)
                self._decks = self._collect(links, arena_lines)

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
        backoff.expo,
        (Timeout, HTTPError, RemoteDisconnected, ScrapingError, urllib.error.HTTPError),
        max_time=300)
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
        if sanitized_fmt := from_iterable(SANITIZED_FORMATS, lambda k: k in line.lower()):
            return [SANITIZED_FORMATS[sanitized_fmt]]
        words = [word.lower() for word in line.strip().split()]
        return [fmt for fmt in all_formats() if any(fmt in word for word in words)]

    def _get_format_soup(self) -> defaultdict[str, list[str]]:
        fmt_soup = defaultdict(list)
        for line in [self.title, *self._desc_lines]:
            for fmt in self._extract_formats(line):
                fmt_soup[fmt].append(fmt)
        return fmt_soup

    def _derive_format(self) -> str | None:
        # first, check the keywords
        if self.keywords:
            keywords = [kw.lower() for kw in self.keywords]
            if sanitized_fmt := from_iterable(SANITIZED_FORMATS, lambda k: k in keywords):
                return SANITIZED_FORMATS[sanitized_fmt]
            if fmt := from_iterable(all_formats(), lambda k: k in keywords):
                return fmt
        # if format soup has been populated, take the most common item
        if self._format_soup:
            two_best = Counter(itertools.chain(*self._format_soup.values())).most_common(2)
            two_best = [pair[0] for pair in two_best]
            if len(two_best) == 2 and all(fmt in ("brawl", "standard") for fmt in two_best):
                return "standardbrawl"
            return two_best[0]
        # if not, return None
        return None

    def _derive_name(self) -> str | None:
        if not self.keywords:
            return None
        # identify title parts that are also parts of keywords
        kw_unwanted = {"mtg", "#mtg", "magic", "#magic"}
        kw_soup = {w.lower().lstrip("#") for kw in self.keywords for w in kw.strip().split()
                   if w.lower() not in kw_unwanted}
        indices = []
        title_unwanted = {"gameplay"}
        title_words = [w for w in self.title.strip().split() if w.lower() not in title_unwanted]
        for i, word in enumerate([tw.lower() for tw in title_words]):
            if word in kw_soup:
                indices.append(i)
        if len(indices) < 2:
            return None
        # look for the longest sequence of identified indices
        seqs = find_longest_seqs(indices)
        if len(seqs) > 1:
            if len(seqs[0]) < 2:
                return None
            seq = from_iterable(
                seqs, lambda s: " ".join(title_words[i] for i in s).lower() in kw_soup)
            if not seq:
                return None
        else:
            seq = seqs[0]
        # check final conditions
        if len(seq) < 2:
            return None
        if len(seq) == 2 and any(title_words[i].lower() in all_formats() for i in seq):
            return None
        return " ".join(title_words[i] for i in seq)

    @classmethod
    def _parse_lines(cls, *lines) -> tuple[list[str], list[str]]:
        links, other_lines = [], []
        for line in lines:
            cls._extract_formats(line)
            url = extract_url(line)
            if url:
                links.append(url)
            else:
                other_lines.append(line)
        return links, get_arena_lines(*other_lines)

    def _process_deck(self, link: str) -> Deck | None:
        if scraper := DeckScraper.from_url(link, self.metadata):
            try:
                if deck := scraper.scrape(throttled=any(site in link for site in self._THROTTLED)):
                    return deck
                self._already_failed_deck_urls.add(link.lower().removesuffix("/"))
                self._failed_deck_urls.add(link.lower().removesuffix("/"))
            except ReadTimeout:
                _log.warning(f"Back-offed scraping of {link!r} failed with read timeout")
                return None

        elif any(h in link for h in self.PASTEBIN_LIKE_HOOKS):
            if "gist.github.com/" in link and not link.endswith("/raw"):
                link = f"{link}/raw"
            response = timed_request(link)
            if response:
                try:
                    return ArenaParser(response.text.splitlines(), self.metadata).parse()
                except ValueError as ve:
                    _log.warning(f"Failed to parse Arena decklist from: {link!r}: {ve}")
        return None

    @timed("comments lookup")
    def _get_comment_lines(self) -> list[str]:
        downloader = YoutubeCommentDownloader()
        try:
            comments = downloader.get_comments_from_url(self.url, sort_by=SORT_BY_POPULAR)
        except (RuntimeError, json.JSONDecodeError):
            return []
        if not comments:
            return []
        author_comments = [c for c in comments if c["channel"] == self.channel_id]
        return [line for c in author_comments for line in c["text"].splitlines()]

    def _process_urls(self, *urls: str) -> list[Deck]:
        decks = []
        for url in urls:
            if url.lower().removesuffix("/") in {
                u.lower().removesuffix("/") for u in self._already_scraped_deck_urls}:
                _log.info(f"Skipping already scraped deck URL: {url!r}...")
                continue
            if url.lower().removesuffix("/") in self._already_failed_deck_urls:
                _log.info(f"Skipping already failed deck URL: {url!r}...")
                continue
            self._sources.add(extract_source(url))
            if deck := self._process_deck(url):
                deck_name = f"{deck.name!r} deck" if deck.name else "Deck"
                _log.info(f"{deck_name} scraped successfully")
                decks.append(deck)
                if deck_url := deck.metadata.get("url"):
                    self._already_scraped_deck_urls.add(deck_url)

        return decks

    def _collect(self, links: list[str], arena_lines: list[str]) -> list[Deck]:
        decks: set[Deck] = set()

        # 1st stage: regular URLs
        decks.update(self._process_urls(*links))

        # 2nd stage: shortened URLs
        shortened_urls = [link for link in links
                          if any(hook in link for hook in self.SHORTENER_HOOKS)]
        if shortened_urls:
            unshortened_urls = [unshorten(url) for url in shortened_urls]
            self._unshortened_links = [url for url in unshortened_urls if url]
            decks.update(self._process_urls(*self.unshortened_links))

        # 3rd stage: Arena lines
        if arena_lines:
            self._sources.add("arena.decklist")
            for decklist in group_arena_lines(*arena_lines):
                if len(decklist) > 2:
                    if deck := ArenaParser(decklist, self.metadata).parse():
                        deck_name = f"{deck.name!r} deck" if deck.name else "Deck"
                        _log.info(f"{deck_name} scraped successfully")
                        decks.add(deck)

        # 4th stage: deck containers
        for link in [*links, *self._unshortened_links]:
            if scraper := DeckUrlsContainerScraper.from_url(
                    link, self.metadata) or HybridContainerScraper.from_url(link, self.metadata):
                container_decks, failed_urls = scraper.scrape(
                    self._already_scraped_deck_urls, self._already_failed_deck_urls)
                decks.update(container_decks)
                self._failed_deck_urls.update(failed_urls)
            elif scraper := DecksJsonContainerScraper.from_url(
                    link, self.metadata) or DeckTagsContainerScraper.from_url(link, self.metadata):
                if link in self._already_scraped_deck_urls:
                    _log.info(f"Skipping already scraped {scraper.short_name()} URL: {link!r}...")
                    continue
                container_decks = scraper.scrape()
                if container_decks:
                    decks.update(container_decks)
                else:
                    self._failed_deck_urls.add(link)

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
            "decks": [json.loads(d.json, object_hook=deserialize_dates) for d in self.decks],
        }
        return json.dumps(data, indent=4, ensure_ascii=False, default=serialize_dates)

    def dump(self, dstdir: PathLike = "", filename="") -> None:
        """Dump to a .json file.

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            filename: optionally, a custom filename (if not provided a default is used)
        """
        dstdir = dstdir or OUTPUT_DIR / "json"
        dstdir = getdir(dstdir)
        timestamp = self.publish_time.strftime(FILENAME_TIMESTAMP_FORMAT)
        filename = filename or f"{self.author}_{timestamp}_video"
        dst = dstdir / f"{sanitize_filename(filename)}.json"
        _log.info(f"Exporting video to: '{dst}'...")
        dst.write_text(self.json, encoding="utf-8")


class Channel:
    """YouTube channel showcasing MtG decks.
    """
    _CONSENT_XPATH = "//button[@aria-label='Accept all']"
    _XPATH = "//span[contains(., 'subscribers')]"

    @property
    def id(self) -> str:
        return self._id

    @property
    def url(self) -> str:
        return CHANNEL_URL_TEMPLATE.format(self.id)

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

    @property
    def already_failed_deck_urls(self) -> set[str]:
        return self._already_failed_deck_urls

    def __init__(
            self, channel_id: str, *already_failed_deck_urls: str,
            only_earlier_than_last_scraped=True, skip_earlier_scraped_deck_urls=True) -> None:
        self._id, self._already_failed_deck_urls = channel_id, set(already_failed_deck_urls)
        self._only_earlier_than_last = only_earlier_than_last_scraped
        self._title, self._description, self._tags = None, None, None
        self._subscribers, self._scrape_time, self._videos = None, None, []
        self._ytsp_data, self._data = None, None
        try:
            self._earlier_data = load_channel(self.id)
            self._title = self._earlier_data.title
            self._already_scraped_deck_urls = {
                *self._earlier_data.deck_urls} if skip_earlier_scraped_deck_urls else set()
        except FileNotFoundError:
            self._earlier_data = None
            self._already_scraped_deck_urls = set()

    def get_unscraped_video_ids(self, limit=10) -> list[str]:
        scraped_ids = [v["id"] for v in self.earlier_data.videos] if self.earlier_data else []
        if not scraped_ids:
            last_scraped_id = None
        else:
            last_scraped_id = scraped_ids[0] if self._only_earlier_than_last else None

        video_ids, scraped_ids = [], set(scraped_ids)
        count = 0
        for vid in self.video_ids(limit=limit):
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

    def video_ids(self, limit=10) -> Generator[str, None, None]:
        try:
            for ch_data in scrapetube.get_channel(channel_id=self.id, limit=limit):
                yield ch_data["videoId"]
        except OSError:
            raise ValueError(f"Invalid channel ID: {self.id!r}")
        except json.decoder.JSONDecodeError:
            raise ScrapingError(
                "scrapetube failed with JSON error. This channel probably doesn't exist "
                "anymore")

    @staticmethod
    def get_url_and_title(channel_id: str, title: str) -> str:
        url = CHANNEL_URL_TEMPLATE.format(channel_id)
        return f"{url!r} ({title})" if title else f"{url!r}"

    def _scrape_videos(self, *video_ids: str) -> None:
        self._scrape_time = datetime.now()
        text = self.get_url_and_title(self.id, self.title)
        _log.info(f"Scraping channel: {text}, {len(video_ids)} video(s)...")
        self._videos = []
        for i, vid in enumerate(video_ids, start=1):
            _log.info(
                f"Scraping video {i}/{len(video_ids)}: 'https://www.youtube.com/watch?v={vid}'...")
            try:
                video = Video(vid, self._already_scraped_deck_urls, self.already_failed_deck_urls)
            except pytubefix.exceptions.VideoPrivate:
                _log.warning(f"Skipping private video: 'https://www.youtube.com/watch?v={vid}'...")
                continue
            self._videos.append(video)
            self._already_scraped_deck_urls.update({d.url for d in video.decks if d.url})
            self._already_failed_deck_urls.update(video.failed_deck_urls)
        try:
            self._ytsp_data = self._get_ytsp() if self._id else None
            self._description = self._ytsp_data.result.get("description") if self._id else None
            self._title = self._ytsp_data.result.get("title") if self._id else None
            self._tags = self._ytsp_data.result.get("tags") if self._id else None
            self._subscribers = self._parse_subscribers() if self._id else None
        except TypeError:
            _log.warning(
                "YTSP failed with TypeError. The channel is probably missing some tab and its "
                "description and tags will be set to 'None'.")
        if not self._subscribers:
            self._subscribers = self.videos[0].channel_subscribers
            if self._subscribers is None:
                self._subscribers = self._scrape_subscribers_with_selenium()
        if not self._title:
            self._title = self._scrape_title_with_selenium()
        self._data = ChannelData(
            id=self.id,
            title=self.title,
            description=self.description,
            tags=self.tags,
            subscribers=self.subscribers,
            scrape_time=self.scrape_time,
            videos=[json.loads(v.json, object_hook=deserialize_dates) for v in self.videos],
        )
        text = self.get_url_and_title(self.id, self.title)
        sources = [d.metadata.get("source") for v in self.videos for d in v.decks]
        sources = sorted({sanitize_source(s) for s in sources if s})
        if sources:
            text += f" [{', '.join(sources)}]"
        _log.info(f"Scraped *** {len(self.decks)} deck(s) *** in total for {text}")

    @timed("channel scraping", precision=2)
    def scrape_videos(self, *video_ids: str) -> None:
        self._scrape_videos(*video_ids)

    @timed("channel scraping", precision=2)
    def scrape(self, limit=10) -> None:
        video_ids = self.get_unscraped_video_ids(limit)
        text = self.get_url_and_title(self.id, self.title)
        if not video_ids:
            _log.info(f"Channel data for {text} already up to date")
            return
        self._scrape_videos(*video_ids)

    def __repr__(self) -> str:
        return getrepr(
            self.__class__,
            ("id", self.id),
            ("title", self.title),
            ("videos", len(self.videos)),
            ("decks", len(self.decks)),
            ("scrape_time", str(self.scrape_time)),
        )

    @backoff.on_exception(
        backoff.expo, (Timeout, HTTPError, RemoteDisconnected, ReadTimeout, httpx.ReadTimeout,
                       httpcore.ReadTimeout), max_time=300)
    def _get_ytsp(self) -> YtspChannel:
        return YtspChannel(self.id)

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
        try:
            soup, _, _ = get_dynamic_soup(self.url, self._XPATH, consent_xpath=self._CONSENT_XPATH)
            text = soup.find("span", string=lambda t: t and "subscribers" in t).text.removesuffix(
                " subscribers")
            number = extract_float(text)
            if text and text[-1] in {"K", "M", "B", "T"}:
                return multiply_by_symbol(number, text[-1])
            return int(number)
        # looking for subscribers is futile if there's only one (or none) :)
        except TimeoutException:
            return 1

    def _scrape_title_with_selenium(self) -> str | None:
        try:
            soup, _, _ = get_dynamic_soup(
                self.url, self._XPATH.replace("subscribers", "subscriber"),
                consent_xpath=self._CONSENT_XPATH)
            text_tag = soup.find(
                "span", class_=lambda c: c and "yt-core-attributed-string" in c,
                dir="auto", role="text")
            return text_tag.text.strip() if text_tag is not None else None
        except TimeoutException:
            _log.warning(f"Failed to scrape channel's title with Selenium")
            return None

    @property
    def json(self) -> str | None:
        if not self.data:
            return None
        return json.dumps(asdict(self.data), indent=4, ensure_ascii=False, default=serialize_dates)

    def dump(self, dstdir: PathLike = "", filename="") -> None:
        """Dump to a .json file.

        Args:
            dstdir: optionally, the destination directory (if not provided CWD is used)
            filename: optionally, a custom filename (if not provided a default is used)
        """
        if not self.json:
            _log.info("Nothing to dump")
            return
        dstdir = dstdir or OUTPUT_DIR / "json"
        dstdir = getdir(dstdir)
        timestamp = self.scrape_time.strftime(FILENAME_TIMESTAMP_FORMAT)
        filename = filename or f"{self.id}___{timestamp}_channel"
        dst = dstdir / f"{sanitize_filename(filename)}.json"
        _log.info(f"Exporting channel to: '{dst}'...")
        dst.write_text(self.json, encoding="utf-8")
