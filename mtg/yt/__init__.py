"""

    mtg.yt.__init__.py
    ~~~~~~~~~~~~~~~~~~
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
from typing import Callable, Generator

import backoff
import httpcore
import httpx
import pytubefix
import pytubefix.exceptions
import scrapetube
from bs4 import Tag
from requests import HTTPError, ReadTimeout, Timeout, ConnectionError
from selenium.common.exceptions import TimeoutException
from youtube_comment_downloader import SORT_BY_POPULAR, YoutubeCommentDownloader
from youtubesearchpython import Channel as YtspChannel

from mtg import FILENAME_TIMESTAMP_FORMAT, Json, OUTPUT_DIR, PathLike, SECRETS
from mtg.deck import Deck, SANITIZED_FORMATS
from mtg.deck.arena import ArenaParser, get_arena_lines, group_arena_lines
from mtg.deck.scrapers import DeckScraper, DeckTagsContainerScraper, DeckUrlsContainerScraper, \
    DecksJsonContainerScraper, HybridContainerScraper
from mtg.gstate import CoolOffManager, DecklistsStateManager, UrlsStateManager
from mtg.scryfall import all_formats
from mtg.utils import Counter, deserialize_dates, extract_float, find_longest_seqs, \
    from_iterable, getrepr, multiply_by_symbol, serialize_dates, timed
from mtg.utils.files import getdir, sanitize_filename
from mtg.utils.scrape import ScrapingError, dissect_js, extract_source, extract_url, \
    http_requests_counted, throttled, timed_request, unshorten
from mtg.utils.scrape.dynamic import get_dynamic_soup
from mtg.utils.scrape.linktree import Linktree
from mtg.yt.data import CHANNELS_DIR, CHANNEL_URL_TEMPLATE, ChannelData, DataPath, \
    ScrapingSession, VIDEO_URL_TEMPLATE, find_channel_files, find_orphans, retrieve_video_data, \
    load_channel, load_channels, prune_channel_data_file, retrieve_ids, sanitize_source

_log = logging.getLogger(__name__)


GOOGLE_API_KEY = SECRETS["google"]["api_key"]  # not used anywhere
DEAD_THRESHOLD = 2000  # days (ca. 5.5 yrs) - only used in gsheet to trim dead from abandoned


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


def _process_videos(channel_id: str, *video_ids: str) -> None:
    files = find_channel_files(channel_id, *video_ids)
    if not files:
        return
    back_up_channel_files(channel_id, *files)
    if scrape_channel_videos(channel_id, *video_ids):
        for f in files:
            prune_channel_data_file(f, *video_ids)


@http_requests_counted("re-scraping videos")
@timed("re-scraping videos", precision=1)
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

    with ScrapingSession() as session:
        manager = UrlsStateManager()
        manager.ignore_scraped = True
        for i, (channel_id, video_ids) in enumerate(channels.items(), start=1):
            _log.info(
                f"Re-scraping ==> {i}/{len(channels)} <== channel for missing decklists data...")
            _process_videos(channel_id, *video_ids)


@http_requests_counted("re-scraping videos")
@timed("re-scraping videos", precision=1)
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

    with ScrapingSession():
        manager = UrlsStateManager()
        manager.ignore_scraped_within_current_video, manager.ignore_failed = True, True
        for i, (channel_id, video_ids) in enumerate(channels.items(), start=1):
            _log.info(
                f"Re-scraping {len(video_ids)} video(s) of ==> {i}/{len(channels)} <== channel...")
            _process_videos(channel_id, *video_ids)


@http_requests_counted("channel videos scraping")
@timed("channel videos scraping", precision=1)
def scrape_channel_videos(channel_id: str, *video_ids: str) -> bool:
    """Scrape specified videos of a YouTube channel in a session.

    Scraped channel's data is saved in a .json file and session ensures decklists are saved
    in global decklists repositories.

    Args:
        channel_id: ID of a channel to scrape
        *video_ids: IDs of videos to scrape
    """
    try:
        ch = Channel(channel_id)
        text = Channel.get_url_and_title(ch.id, ch.title)
        _log.info(f"Scraping {len(video_ids)} video(s) from channel {text}...")
        ch.scrape_videos(*video_ids)
        if ch.data:
            dst = getdir(CHANNELS_DIR / channel_id)
            ch.dump(dst)
    except Exception as err:
        _log.exception(f"Scraping of channel {channel_id!r} failed with: '{err}'")
        return False

    return True


@http_requests_counted("channels scraping")
@timed("channels scraping", precision=1)
def scrape_channels(
        *chids: str,
        videos=25,
        only_newer_than_last_scraped=True) -> None:
    """Scrape YouTube channels as specified in a session.

    Each scraped channel's data is saved in a .json file and session ensures decklists are saved
    in global decklists repositories.

    Args:
        chids: IDs of channels to scrape
        videos: number of videos to scrape per channel
        only_newer_than_last_scraped: if True, only scrape videos newer than the last one scraped
    """
    with ScrapingSession() as session:
        for i, id_ in enumerate(chids, start=1):
            try:
                ch = Channel(id_)
                text = Channel.get_url_and_title(ch.id, ch.title)
                _log.info(f"Scraping channel {i}/{len(chids)}: {text}...")
                ch.scrape(videos, only_newer_than_last_scraped=only_newer_than_last_scraped)
                if ch.data:
                    dst = getdir(CHANNELS_DIR / id_)
                    ch.dump(dst)
            except Exception as err:
                _log.exception(f"Scraping of channel {id_!r} failed with: '{err}'. Skipping...")


def scrape_fresh(
        videos=50, only_newer_than_last_scraped=True, only_deck_fresh=True) -> None:
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
        *ids, videos=videos, only_newer_than_last_scraped=only_newer_than_last_scraped)


def scrape_active(
        videos=50, only_newer_than_last_scraped=True, only_deck_fresh=True) -> None:
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
        *ids, videos=videos, only_newer_than_last_scraped=only_newer_than_last_scraped)


def scrape_dormant(
        videos=50, only_newer_than_last_scraped=True, only_deck_fresh=True) -> None:
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
        *ids, videos=videos, only_newer_than_last_scraped=only_newer_than_last_scraped)


def scrape_abandoned(
        videos=50, only_newer_than_last_scraped=True, only_deck_fresh=True) -> None:
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
        *ids, videos=videos, only_newer_than_last_scraped=only_newer_than_last_scraped)


def scrape_deck_stale(
        videos=50, only_newer_than_last_scraped=True, only_fresh_or_active=True) -> None:
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
        *ids, videos=videos, only_newer_than_last_scraped=only_newer_than_last_scraped)


def scrape_very_deck_stale(
        videos=50, only_newer_than_last_scraped=True, only_fresh_or_active=True) -> None:
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
        *ids, videos=videos, only_newer_than_last_scraped=only_newer_than_last_scraped)


def scrape_excessively_deck_stale(
        videos=50, only_newer_than_last_scraped=True, only_fresh_or_active=True) -> None:
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
        *ids, videos=videos, only_newer_than_last_scraped=only_newer_than_last_scraped)


# TODO: async
class LinksExpander:
    """Expand links to prospective pages into lines eligible for deck-processing.

    Note: On 15th Jan 2025 there were only 108 `pastebin.com` and 2 `gist.github.com` links
    identified across 278,101 links scraped so far from YT videos' descriptions in total.
    """
    PASTEBIN_LIKE_HOOKS = {
        "gist.github.com/",
        "pastebin.com/",
    }
    OBSCURE_PASTEBIN_LIKE_HOOKS = {
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
    _PATREON_XPATH = "//div[contains(@class, 'sc-dtMgUX') and contains(@class, 'IEufa')]"
    _PATREON_XPATH2 = "//div[contains(@class, 'sc-b20d4e5f-0') and contains(@class, 'fbPSoT')]"
    _GOOGLE_DOC_XPATH = "//div[@id='docs-editor-container']"

    @property
    def expanded_links(self) -> list[str]:
        return self._expanded_links

    @property
    def gathered_links(self) -> list[str]:
        return self._gathered_links

    @property
    def lines(self) -> list[str]:
        return self._lines

    def __init__(self, *links: str) -> None:
        self._links = links
        self._urls_manager = UrlsStateManager()
        self._expanded_links, self._gathered_links, self._lines = [], [], []
        self._expand()

    @classmethod
    def is_pastebin_like_url(cls, url: str) -> bool:
        return any(h in url for h in cls.PASTEBIN_LIKE_HOOKS)

    @classmethod
    def is_obscure_pastebin_like_url(cls, url: str) -> bool:
        return any(h in url for h in cls.OBSCURE_PASTEBIN_LIKE_HOOKS)

    @backoff.on_exception(
        backoff.expo, (ConnectionError, HTTPError, ReadTimeout), max_time=60)
    def _expand(self) -> None:
        for link in self._links:
            if self._urls_manager.is_failed(link):
                _log.info(f"Skipping expansion of already failed URL: {link!r}...")
                continue
            if self.is_pastebin_like_url(link):
                _log.info(f"Expanding {link!r}...")
                self._expand_pastebin(link)
            elif self.is_obscure_pastebin_like_url(link):
                _log.warning(f"Obscure pastebin-like link found: {link!r}...")
            elif self.is_patreon_url(link):
                _log.info(f"Expanding {link!r}...")
                self._expand_patreon(link)
            elif self.is_google_doc_url(link):
                _log.info(f"Expanding {link!r}...")
                self._expand_google_doc(link)

    def _expand_pastebin(self, link: str) -> None:
        original_link = link
        if "gist.github.com/" in link and not link.endswith("/raw"):
            link = f"{link}/raw"
        elif "pastebin.com/" in link and "/raw/" not in link:
            link = link.replace("pastebin.com/", "pastebin.com/raw/")

        response = timed_request(link)
        if not response:
            self._urls_manager.add_failed(original_link)
            return

        lines = [l.strip() for l in response.text.splitlines()]
        self._lines += [l.strip() for l in response.text.splitlines()]
        _log.info(f"Expanded {len(lines)} Pastebin-like line(s)")
        self._expanded_links.append(original_link)

    @staticmethod
    def is_patreon_url(url: str) -> bool:
        return "patreon.com/posts/" in url.lower()

    def _get_patreon_text_tag(self, link: str) -> Tag | None:
        try:
            soup, _, _ = get_dynamic_soup(link, self._PATREON_XPATH, timeout=10)
            if not soup:
                _log.warning("Patreon post data not available")
                self._urls_manager.add_failed(link)
                return None
            return soup.find("div", class_=lambda c: c and "sc-dtMgUX" in c and 'IEufa' in c)
        except TimeoutException:
            try:
                soup, _, _ = get_dynamic_soup(link, self._PATREON_XPATH2)
                if not soup:
                    _log.warning("Patreon post data not available")
                    self._urls_manager.add_failed(link)
                    return None
                return soup.find(
                    "div", class_=lambda c: c and "sc-b20d4e5f-0" in c and 'fbPSoT' in c)
            except TimeoutException:
                _log.warning("Patreon post data not available")
                self._urls_manager.add_failed(link)
                return None

    def _expand_patreon(self, link: str) -> None:
        text_tag = self._get_patreon_text_tag(link)
        if not text_tag:
            return
        lines = [p_tag.text.strip() for p_tag in text_tag.find_all("p")]
        self._lines += lines
        _log.info(f"Expanded {len(lines)} Patreon line(s)")
        self._expanded_links.append(link)

    @staticmethod
    def is_google_doc_url(url: str) -> bool:
        return "docs.google.com/document/" in url.lower()

    def _expand_google_doc(self, link: str) -> None:
        # url = "https://docs.google.com/document/d/1Bnsd4M7n_8LHfN6uEJVxoRr72antIEIO9w4YOGKltiU/edit"
        try:
            soup, _, _ = get_dynamic_soup(link, self._GOOGLE_DOC_XPATH)
            if not soup:
                _log.warning("Google Docs document data not available")
                self._urls_manager.add_failed(link)
                return
        except TimeoutException:
            _log.warning("Google Docs document data not available")
            self._urls_manager.add_failed(link)
            return

        start = "DOCS_modelChunk = "
        end = "; DOCS_modelChunkLoadStart = "
        js = dissect_js(soup, start_hook=start, end_hook=end, left_split_on_start_hook=True)

        if not js:
            _log.warning("Google Docs document data not available")
            self._urls_manager.add_failed(link)
            return

        matched_text, links = None, []
        for i, d in enumerate(js):
            match d:
                case {"s": text} if i == 0:
                    matched_text = text.strip()
                case {"sm": {'lnks_link': {'ulnk_url': link}}}:
                    links.append(link)
                    self._gathered_links.append(link)
                case _:
                    pass

        lines = []
        if matched_text:
            lines = [l.strip() for l in matched_text.splitlines()]
            self._lines += lines

        _log.info(f"Expanded {len(lines)} Google Docs line(s) and gathered {len(links)} link(s)")


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
        "partner.tcgplayer.com/",  # TCGPlayer affiliate referral link
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
        return [line.strip() for line in self.description.splitlines()] if self.description else []

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

    def __init__(self, video_id: str) -> None:
        """Initialize.

        Args:
            video_id: unique string identifying a YouTube video (the part after `v=` in the URL)
        """
        self._urls_manager = UrlsStateManager()
        self._urls_manager.current_video = video_id
        self._decklists_manager = DecklistsStateManager()
        self._cooloff_manager = CoolOffManager()
        self._process(video_id)

    @throttled(1.25, 0.25)
    def _process(self, video_id: str) -> None:
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
        self._scrape()

    @timed("gathering video data")
    def _scrape(self) -> None:
        self._get_pytube_data()
        self._format_soup = self._get_format_soup()
        self._derived_format = self._derive_format()
        self._derived_name = self._derive_name()
        links, lines = self._parse_lines(*self._desc_lines)
        self._decks = self._collect(links, get_arena_lines(*lines))
        if not self._decks:  # try with author's comment
            comment_lines = self._get_comment_lines()
            if comment_lines:
                links, lines = self._parse_lines(*comment_lines)
                self._decks = self._collect(links, get_arena_lines(*lines))
        self._cooloff_manager.bump_decks(len(self.decks))

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
    def is_shortened_url(cls, url: str) -> bool:
        return any(h in url for h in cls.SHORTENER_HOOKS)

    @classmethod  # recursive
    def _parse_lines(cls, *lines, expand_links=True) -> tuple[list[str], list[str]]:
        links, other_lines = set(), []
        for line in lines:
            url = extract_url(line)
            if url:
                if cls.is_shortened_url(url):
                    url = unshorten(url) or url
                if Linktree.is_linktree_url(url):
                    try:
                        new_links = Linktree(url).data.links
                        _log.info(f"Parsed {len(new_links)} link(s) from: {url!r}")
                        links.update(new_links)
                    except (ConnectionError, HTTPError, ReadTimeout, ScrapingError) as err:
                        _log.warning(f"Parsing '{url!r}' failed with: {err}")
                else:
                    links.add(url)
            else:
                other_lines.append(line)

        if expand_links:
            expander = LinksExpander(*links)
            links = {l for l in links if l not in expander.expanded_links}
            links.update(expander.gathered_links)
            new_links, new_lines = cls._parse_lines(*expander.lines, expand_links=False)
            links.update(new_links)
            other_lines.extend(new_lines)

        return sorted(links), other_lines

    def _process_deck(self, link: str) -> Deck | None:
        deck = None
        if scraper := DeckScraper.from_url(link, self.metadata):
            sanitized_link = scraper.sanitize_url(link)
            if self._urls_manager.is_scraped(sanitized_link):
                _log.info(f"Skipping already scraped deck URL: {sanitized_link!r}...")
                return None
            elif self._urls_manager.is_failed(sanitized_link):
                _log.info(f"Skipping already failed deck URL: {sanitized_link!r}...")
                return None
            try:
                deck = scraper.scrape(throttled=any(site in link for site in self._THROTTLED))
            except ReadTimeout:
                _log.warning(f"Back-offed scraping of {link!r} failed with read timeout")
            if not deck:
                self._urls_manager.add_failed(sanitized_link)

        if deck:
            deck_name = f"{deck.name!r} deck" if deck.name else "Deck"
            _log.info(f"{deck_name} scraped successfully")
            if deck_url := deck.metadata.get("url"):
                self._urls_manager.add_scraped(deck_url)

        return deck

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
            self._sources.add(extract_source(url))
            if deck := self._process_deck(url):
                decks.append(deck)
        return decks

    def _collect(self, links: list[str], arena_lines: list[str]) -> list[Deck]:
        decks: set[Deck] = set()

        # 1st stage: URLs
        decks.update(self._process_urls(*links))

        # 2nd stage: Arena lines
        if arena_lines:
            self._sources.add("arena.decklist")
            for decklist in group_arena_lines(*arena_lines):
                if len(decklist) > 2:
                    if deck := ArenaParser("\n".join(decklist), self.metadata).parse():
                        deck_name = f"{deck.name!r} deck" if deck.name else "Deck"
                        _log.info(f"{deck_name} scraped successfully")
                        decks.add(deck)

        # 3rd stage: deck containers
        for link in links:
            if scraper := DeckUrlsContainerScraper.from_url(
                    link, self.metadata) or HybridContainerScraper.from_url(link, self.metadata):
                decks.update(scraper.scrape())
            elif scraper := DecksJsonContainerScraper.from_url(
                    link, self.metadata) or DeckTagsContainerScraper.from_url(link, self.metadata):
                sanitized_link = scraper.sanitize_url(link)
                if self._urls_manager.is_scraped(sanitized_link):
                    _log.info(
                        f"Skipping already scraped {scraper.short_name()} URL: "
                        f"{sanitized_link!r}...")
                    continue
                if self._urls_manager.is_failed(sanitized_link):
                    _log.info(
                        f"Skipping already failed {scraper.short_name()} URL: "
                        f"{sanitized_link!r}...")
                    continue
                decks.update(scraper.scrape())

        for deck in decks:
            self._decklists_manager.add_regular(deck.decklist_id, deck.decklist)
            self._decklists_manager.add_extended(
                deck.decklist_extended_id, deck.decklist_extended)

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
    CONSENT_XPATH = "//button[@aria-label='Accept all']"
    XPATH = "//span[contains(., 'subscribers')]"

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

    def __init__(self, channel_id: str) -> None:
        self._id = channel_id
        self._cooloff_manager = CoolOffManager()
        self._urls_manager = UrlsStateManager()
        self._urls_manager.current_channel = self.id
        self._title, self._description, self._tags = None, None, None
        self._subscribers, self._scrape_time, self._videos = None, None, []
        self._ytsp_data, self._data = None, None
        self._handle_earlier_data()

    def _handle_earlier_data(self):
        try:
            self._earlier_data = load_channel(self.id)
            self._title = self._earlier_data.title
            self._urls_manager.update_scraped({self.id: self.earlier_data.deck_urls})
            self._urls_manager.update_scraped(
                {f"{self.id}/{v['id']}": {d["metadata"]["url"] for d in v["decks"]
                                          if d.get("metadata") and d["metadata"].get("url")}
                 for v in self.earlier_data.videos})
        except FileNotFoundError:
            self._earlier_data = None

    def get_unscraped_video_ids(self, limit=10, only_newer_than_last_scraped=True) -> list[str]:
        scraped_ids = [v["id"] for v in self.earlier_data.videos] if self.earlier_data else []
        if not scraped_ids:
            last_scraped_id = None
        else:
            last_scraped_id = scraped_ids[0] if only_newer_than_last_scraped else None

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
                video = Video(vid)
            except pytubefix.exceptions.VideoPrivate:
                _log.warning(f"Skipping private video: 'https://www.youtube.com/watch?v={vid}'...")
                continue
            self._videos.append(video)
            self._cooloff_manager.bump_video()
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
    def scrape(self, limit=10, only_newer_than_last_scraped=True) -> None:
        video_ids = self.get_unscraped_video_ids(
            limit, only_newer_than_last_scraped=only_newer_than_last_scraped)
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
            soup, _, _ = get_dynamic_soup(self.url, self.XPATH, consent_xpath=self.CONSENT_XPATH)
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
                self.url, self.XPATH.replace("subscribers", "subscriber"),
                consent_xpath=self.CONSENT_XPATH)
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
        self._cooloff_manager.bump_channel()
