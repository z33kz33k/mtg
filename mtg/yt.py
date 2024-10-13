"""

    mtg.yt.py
    ~~~~~~~~~~~~~~
    Handle YouTube data.

    @author: z33k

"""
import itertools
import json
import logging
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import cached_property
from http.client import RemoteDisconnected
from operator import attrgetter, itemgetter
from pathlib import Path
from types import TracebackType
from typing import Generator, Iterator, Type

import backoff
import pytubefix
import scrapetube
import httpx
import httpcore
from requests import ConnectionError, HTTPError, Timeout, ReadTimeout
from selenium.common.exceptions import TimeoutException
from youtube_comment_downloader import SORT_BY_POPULAR, YoutubeCommentDownloader
from youtubesearchpython import Channel as YtspChannel

from mtg import FILENAME_TIMESTAMP_FORMAT, Json, OUTPUT_DIR, PathLike, README
from mtg.deck import Deck
from mtg.deck.arena import ArenaParser, get_arena_lines, group_arena_lines
from mtg.deck.scrapers import DeckScraper, SANITIZED_FORMATS
from mtg.deck.scrapers.melee import ALT_DOMAIN as MELEE_ALT_DOMAIN
from mtg.deck.scrapers.moxfield import MoxfieldBookmarkScraper
from mtg.scryfall import all_formats
from mtg.utils import Counter, breadcrumbs, deserialize_dates, extract_float, find_longest_seqs, \
    from_iterable, getrepr, multiply_by_symbol, sanitize_filename, serialize_dates, timed
from mtg.utils.files import getdir
from mtg.utils.gsheets import extend_gsheet_rows_with_cols, retrieve_from_gsheets_cols
from mtg.utils.scrape import ScrapingError, extract_source, extract_url, \
    get_dynamic_soup_by_xpath, http_requests_counted, throttle_with_countdown, throttled, \
    timed_request, unshorten

_log = logging.getLogger(__name__)


GOOGLE_API_KEY = Path("scraping_api_key.txt").read_text(encoding="utf-8")  # not used anywhere
CHANNELS_DIR = OUTPUT_DIR / "channels"
REGULAR_DECKLISTS_FILE = CHANNELS_DIR / "regular_decklists.json"
EXTENDED_DECKLISTS_FILE = CHANNELS_DIR / "extended_decklists.json"
DORMANT_THRESHOLD = 30 * 3  # days
ABANDONED_THRESHOLD = 30 * 12  # days
DECK_STALE_THRESHOLD = 50  # videos
VERY_DECK_STALE_THRESHOLD = 100  # videos
EXCESSIVELY_DECK_STALE_THRESHOLD = 150  # videos


def channel_url_to_handle(url: str) -> str:
    if "@" not in url and "/c/" not in url:
        raise ValueError(f"Not a channel URL: {url!r}")
    _, handle = url.rsplit("/", maxsplit=1)
    if "/c/" in url:
        handle = f"c_{handle}"
    return handle


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
    def handle(self):
        return channel_url_to_handle(self.url)

    @property
    def decks(self) -> list[dict]:
        return [d for v in self.videos for d in v["decks"]]

    @property
    def sources(self) -> list[str]:
        return sorted({s for v in self.videos for s in v["sources"]})

    @property
    def deck_urls(self) -> set[str]:
        return {d["metadata"]["url"] for d in self.decks
                if d.get("metadata") and d["metadata"].get("url")}

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

    @property
    def is_dormant(self) -> bool:
        return (self.staleness is not None
                and ABANDONED_THRESHOLD >= self.staleness > DORMANT_THRESHOLD)

    @property
    def is_abandoned(self) -> bool:
        return self.staleness is not None and self.staleness > ABANDONED_THRESHOLD

    @property
    def is_active(self) -> bool:
        return not self.is_dormant and not self.is_abandoned

    @property
    def is_deck_stale(self) -> bool:
        return VERY_DECK_STALE_THRESHOLD >= self.deck_staleness > DECK_STALE_THRESHOLD

    @property
    def is_very_deck_stale(self) -> bool:
        return EXCESSIVELY_DECK_STALE_THRESHOLD >= self.deck_staleness > VERY_DECK_STALE_THRESHOLD

    @property
    def is_excessively_deck_stale(self) -> bool:
        return self.deck_staleness > EXCESSIVELY_DECK_STALE_THRESHOLD

    @property
    def is_deck_fresh(self) -> bool:
        return not (self.is_deck_stale or self.is_very_deck_stale or self.is_excessively_deck_stale)


def retrieve_urls() -> list[str]:
    """Retrieve channel URLs from a private Google Sheet spreadsheet.

    Mind that this operation takes about 4 seconds to complete.
    """
    return retrieve_from_gsheets_cols("mtga_yt", "channels", (1, ), start_row=2)[0]


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
    channel_dir = getdir(CHANNELS_DIR / channel_url_to_handle(channel_url.rstrip("/")))
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
                ch.decks_per_video or 0,
                ch.deck_staleness,
                ch.total_views,
                ch.subs_activity if ch.subs_activity is not None else "N/A",
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

    extend_gsheet_rows_with_cols("mtga_yt", "channels", data, start_row=2, start_col=3)


class ScrapingSession:
    """Context manager to ensure proper updates of global decklist repositories during scraping.
    """
    def __init__(self) -> None:
        self._regular_decklists, self._extended_decklists = {}, {}
        self._regular_count, self._extended_count = 0, 0

    def __enter__(self) -> "ScrapingSession":
        self._regular_decklists = json.loads(REGULAR_DECKLISTS_FILE.read_text(
            encoding="utf-8")) if REGULAR_DECKLISTS_FILE.is_file() else {}
        _log.info(
            f"Loaded {len(self._regular_decklists):,} regular decklist(s) from the global "
            f"repository")
        self._extended_decklists = json.loads(EXTENDED_DECKLISTS_FILE.read_text(
            encoding="utf-8")) if EXTENDED_DECKLISTS_FILE.is_file() else {}
        _log.info(
            f"Loaded {len(self._extended_decklists):,} extended decklist(s) from the global "
            f"repository")
        return self

    def __exit__(
            self, exc_type: Type[BaseException] | None, exc_val: BaseException | None,
            exc_tb: TracebackType | None) -> None:
        _log.info(f"Dumping '{REGULAR_DECKLISTS_FILE}'...")
        REGULAR_DECKLISTS_FILE.write_text(
            json.dumps(self._regular_decklists, indent=4, ensure_ascii=False), encoding="utf-8")
        _log.info(f"Dumping '{EXTENDED_DECKLISTS_FILE}'...")
        EXTENDED_DECKLISTS_FILE.write_text(
            json.dumps(self._extended_decklists, indent=4, ensure_ascii=False),encoding="utf-8")
        _log.info(
            f"Total of {self._regular_count} unique regular decklist(s) added to the global "
            f"repository")
        _log.info(
            f"Total of {self._extended_count} unique extended decklist(s) added to the global "
            f"repository")

    def update_regular(self, id_: str, decklist: str) -> None:
        if id_ not in self._regular_decklists:
            self._regular_decklists[id_] = decklist
            self._regular_count += 1

    def update_extended(self, id_: str, decklist: str) -> None:
        if id_ not in self._extended_decklists:
            self._extended_decklists[id_] = decklist
            self._extended_count += 1


def retrieve_decklist(id_: str) -> str | None:
    decklists = json.loads(REGULAR_DECKLISTS_FILE.read_text(
            encoding="utf-8")) if REGULAR_DECKLISTS_FILE.is_file() else {}
    decklists.update(json.loads(EXTENDED_DECKLISTS_FILE.read_text(
            encoding="utf-8")) if EXTENDED_DECKLISTS_FILE.is_file() else {})
    return decklists.get(id_)


def check_decklists() -> None:
    regular_ids, extended_ids = {}, {}
    for ch in load_channels():
        for v in ch.videos:
            for deck in v["decks"]:
                path_regular = breadcrumbs(ch.handle, v["id"], deck["decklist_id"])
                path_extended = breadcrumbs(ch.handle, v["id"], deck["decklist_extended_id"])
                regular_ids[deck["decklist_id"]] = path_regular
                extended_ids[deck["decklist_extended_id"]] = path_extended

    regular_decklists = json.loads(REGULAR_DECKLISTS_FILE.read_text(
            encoding="utf-8")) if REGULAR_DECKLISTS_FILE.is_file() else {}
    extended_decklists = json.loads(EXTENDED_DECKLISTS_FILE.read_text(
            encoding="utf-8")) if EXTENDED_DECKLISTS_FILE.is_file() else {}

    orphaned_regulars = {r for r in regular_ids if r not in regular_decklists}
    orphaned_extendeds = {e for e in extended_ids if e not in extended_decklists}

    if orphaned_regulars:
        _log.warning(
            f"Orphaned regular decklists: {sorted({regular_ids[r] for r in orphaned_regulars})}")
    if orphaned_extendeds:
        _log.warning(
            f"Orphaned extended decklists: {sorted({extended_ids[e] for e in orphaned_extendeds})}")

    if not orphaned_regulars and not orphaned_regulars:
        _log.info("No orphaned decklists found")


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
    with ScrapingSession() as session:
        current_videos, total_videos = 0, 0
        total_channels, total_decks = 0, 0
        for i, url in enumerate(urls, start=1):
            try:
                ch = Channel(url, only_earlier_than_last_scraped=only_earlier_than_last_scraped)
                _log.info(f"Scraping channel {i}/{len(urls)}: {ch.handle!r}...")
                ch.scrape(videos)
                if ch.data:
                    dst = getdir(CHANNELS_DIR / ch.handle)
                    ch.dump(dst)
                    current_videos += len(ch.videos)
                    total_videos += len(ch.videos)
                    total_channels += 1
                    total_decks += len(ch.decks)
                    for deck in ch.decks:
                        session.update_regular(deck.decklist_id, deck.decklist)
                        session.update_extended(deck.decklist_extended_id, deck.decklist_extended)
            except Exception as err:
                _log.exception(f"Scraping of channel {url!r} failed with: '{err}'. Skipping...")
            if current_videos > 500:
                current_videos = 0
                _log.info(f"Throttling for 5 minutes before the next batch...")
                throttle_with_countdown(5 * 60)

        _log.info(
            f"Scraped {total_decks} deck(s) from {total_videos} video(s) from {total_channels} "
            f"channel(s)")


def scrape_active(
        videos=25, only_earlier_than_last_scraped=True, only_deck_fresh=True) -> None:
    """Scrape these YouTube channels specified in private Google Sheet that are not dormant or
    abandoned. Save the scraped data as .json files.
    """
    urls = []
    for url in retrieve_urls():
        try:
            data = load_channel(url)
        except FileNotFoundError:
            data = None
        if not data:
            urls.append(url)
        elif data.is_active:
            if only_deck_fresh and data.is_deck_stale:
                continue
            urls.append(url)
    text = "active and deck-fresh" if only_deck_fresh else "active"
    _log.info(f"Scraping {len(urls)} {text} channel(s)...")
    scrape_channels(
        *urls, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_dormant(
        videos=25, only_earlier_than_last_scraped=True, only_deck_fresh=True) -> None:
    """Scrape these YouTube channels specified in private Google Sheet that are dormant. Save
    the scraped data as .json files.
    """
    urls = []
    for url in retrieve_urls():
        try:
            data = load_channel(url)
        except FileNotFoundError:
            data = None
        if data and data.is_dormant:
            if only_deck_fresh and data.is_deck_stale:
                continue
            urls.append(url)
    text = "dormant and deck-fresh" if only_deck_fresh else "dormant"
    _log.info(f"Scraping {len(urls)} {text} channel(s)...")
    scrape_channels(
        *urls, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_abandoned(
        videos=25, only_earlier_than_last_scraped=True, only_deck_fresh=True) -> None:
    """Scrape these YouTube channels specified in private Google Sheet that are abandoned. Save
    the scraped data as .json files.
    """
    urls = []
    for url in retrieve_urls():
        try:
            data = load_channel(url)
        except FileNotFoundError:
            data = None
        if data and data.is_abandoned:
            if only_deck_fresh and data.is_deck_stale:
                continue
            urls.append(url)
    text = "abandoned and deck-fresh" if only_deck_fresh else "abandoned"
    _log.info(f"Scraping {len(urls)} {text} channel(s)...")
    scrape_channels(
        *urls, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_deck_stale(videos=25, only_earlier_than_last_scraped=True, only_active=True) -> None:
    """Scrape these YouTube channels specified in private Google Sheet that are considered
    deck-stale. Save the scraped data as .json files.
    """
    urls = []
    for url in retrieve_urls():
        try:
            data = load_channel(url)
        except FileNotFoundError:
            data = None
        if data and data.is_deck_stale:
            if only_active and not data.is_active:
                continue
            urls.append(url)
    text = "deck-stale and active" if only_active else "deck-stale"
    _log.info(f"Scraping {len(urls)} {text} channel(s)...")
    scrape_channels(
        *urls, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_very_deck_stale(
        videos=25, only_earlier_than_last_scraped=True, only_active=True) -> None:
    """Scrape these YouTube channels specified in private Google Sheet that are considered
    very deck-stale. Save the scraped data as .json files.
    """
    urls = []
    for url in retrieve_urls():
        try:
            data = load_channel(url)
        except FileNotFoundError:
            data = None
        if data and data.is_very_deck_stale:
            if only_active and not data.is_active:
                continue
            urls.append(url)
    text = "very deck-stale and active" if only_active else "very deck-stale"
    _log.info(f"Scraping {len(urls)} {text} channel(s)...")
    scrape_channels(
        *urls, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def scrape_excessively_deck_stale(
        videos=25, only_earlier_than_last_scraped=True, only_active=True) -> None:
    """Scrape these YouTube channels specified in private Google Sheet that are considered
    excessively deck-stale. Save the scraped data as .json files.
    """
    urls = []
    for url in retrieve_urls():
        try:
            data = load_channel(url)
        except FileNotFoundError:
            data = None
        if data and data.is_excessively_deck_stale:
            if only_active and not data.is_active:
                continue
            urls.append(url)
    text = "excessively deck-stale and active" if only_active else "excessively deck-stale"
    _log.info(f"Scraping {len(urls)} {text} channel(s)...")
    scrape_channels(
        *urls, videos=videos, only_earlier_than_last_scraped=only_earlier_than_last_scraped)


def get_aggregate_deck_data() -> tuple[Counter, Counter]:
    """Get aggregated deck data across all channels.
    """
    decks = [d for ch in load_channels() for d in ch.decks]
    fmts = []
    for d in decks:
        if fmt := d["metadata"].get("format"):
            fmts.append(fmt)
        elif d["metadata"].get("irregular_format"):
            fmts.append("irregular")
    delta = len(decks) - len(fmts)
    if delta > 0:
        fmts += ["undefined"] * delta
    format_counter = Counter(fmts)
    sources = []
    for d in decks:
        src = d["metadata"]["source"]
        src = src.removeprefix("www.") if src.startswith("www.") else src
        if "tcgplayer" in src:
            _, *parts = src.split(".")
            src = ".".join(parts)
        elif MELEE_ALT_DOMAIN in src:
            src = "melee.gg"
        sources.append(src)
    source_counter = Counter(sources)
    return format_counter, source_counter


def update_readme_with_deck_data() -> None:
    """Update README.md with aggregated deck data.
    """
    _log.info("Updating README.md with aggregated deck data...")
    fmt_c, src_c = get_aggregate_deck_data()
    table_lines = fmt_c.markdown("Format").splitlines() + [""] + src_c.markdown(
        "Source").splitlines() + [""]
    old_lines = README.read_text(encoding="utf-8").splitlines()
    idx = old_lines.index("### Scraped decks breakdown")
    new_lines = old_lines[:idx + 1] + table_lines
    README.write_text("\n".join(new_lines), encoding="utf-8")
    _log.info("README.md updates done")


def get_duplicates() -> list[str]:
    """Get list of YouTube channels duplicated in the private Google Sheet.
    """
    urls = retrieve_urls()
    seen = set()
    duplicates = []
    for url in urls:
        if url in seen:
            duplicates.append(url)
        else:
            seen.add(url)
    return duplicates


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
        "aetherhub.com", "mtggoldfish.com", "moxfield.com", "tappedout.net", "hareruyamtg.com")

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

    def __init__(self, video_id: str, *already_scraped_deck_urls: str) -> None:
        """Initialize.

        Args:
            video_id: unique string identifying a YouTube video (the part after `v=` in the URL)
            already_scraped_deck_url: URLs of decks that have already been scraped within a channel
        """
        self._already_scraped_deck_urls = set(already_scraped_deck_urls)
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

    @timed("gathering video data")
    def _scrape(self):
        self._get_pytube_data()
        self._format_soup = self._get_format_soup()
        self._derived_format = self._derive_format()
        self._derived_name = self._derive_name()
        self._links, self._arena_lines = self._parse_lines(*self._desc_lines)
        self._decks = self._collect(self._links, self._arena_lines)
        if not self._decks:  # try with the most popular comment
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
        unwanted = {"mtg", "#mtg", "magic", "#magic"}
        kw_soup = {w.lower().lstrip("#") for kw in self.keywords for w in kw.strip().split()
                   if w.lower() not in unwanted}
        indices = []
        title_words = [w for w in self.title.strip().split()]
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
            if any(site in link for site in self._THROTTLED):
                try:
                    return scraper.scrape(throttled=True)
                except (ConnectionError, ReadTimeout) as e:
                    _log.warning(f"Scraping failed with: {e}. Re-trying with backoff...")
                    return scraper.scrape_with_backoff(throttled=True)
            else:
                try:
                    return scraper.scrape()
                except (ConnectionError, ReadTimeout) as e:
                    _log.warning(f"Scraping failed with: {e}. Re-trying with backoff...")
                    return scraper.scrape_with_backoff()
        elif any(h in link for h in self.PASTEBIN_LIKE_HOOKS):
            if "gist.github.com/" in link and not link.endswith("/raw"):
                link = f"{link}/raw"
            data = timed_request(link)
            if data:
                return ArenaParser(data.splitlines(), self.metadata).parse()
        return None

    @timed("comments lookup")
    def _get_comment_lines(self) -> list[str]:
        downloader = YoutubeCommentDownloader()
        try:
            comments = downloader.get_comments_from_url(self.url, sort_by=SORT_BY_POPULAR)
        except RuntimeError:
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
                start = f"{deck.name!r} deck" if deck.name else "Deck"
                _log.info(f"{start} scraped successfully")
                decks.append(deck)
        return decks

    def _collect(self, links: list[str], arena_lines: list[str]) -> list[Deck]:
        decks: set[Deck] = set()

        # 1st stage: regular URLs
        for deck in self._process_urls(*links):
            decks.add(deck)
            if deck_url := deck.metadata.get("url"):
                self._already_scraped_deck_urls.add(deck_url)

        # 2nd stage: shortened URLs
        if not decks:
            shortened_urls = [link for link in links
                              if any(hook in link for hook in self.SHORTENER_HOOKS)]
            if shortened_urls:
                unshortened_urls = [unshorten(url) for url in shortened_urls]
                self._unshortened_links = [url for url in unshortened_urls if url]
                for deck in self._process_urls(*self._unshortened_links):
                    decks.add(deck)
                    if deck_url := deck.metadata.get("url"):
                        self._already_scraped_deck_urls.add(deck_url)

        # 3rd stage: Arena lines
        if arena_lines:
            self._sources.add("arena.decklist")
            for decklist in group_arena_lines(*arena_lines):
                if len(decklist) > 2:
                    if deck := ArenaParser(decklist, self.metadata).parse():
                        start = f"{deck.name!r} deck" if deck.name else "Deck"
                        _log.info(f"{start} scraped successfully")
                        decks.add(deck)

        # TODO: more than only Moxfield bookmarks
        # 4th stage: deck groups
        if bookmark := from_iterable(
                [*links, *self._unshortened_links],
                lambda l: MoxfieldBookmarkScraper.is_bookmark_url(l)):
            decks.update(
                MoxfieldBookmarkScraper(bookmark, self.metadata).scrape(
                    *self._already_scraped_deck_urls))

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
    @property
    def url(self) -> str:
        return self._url.rstrip("/")

    @property
    def handle(self) -> str:
        return channel_url_to_handle(self.url)

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
        self._videos = []
        earlier_deck_urls = self.earlier_data.deck_urls if self.earlier_data else set()
        for i, vid in enumerate(video_ids, start=1):
            _log.info(
                f"Scraping video {i}/{len(video_ids)}: 'https://www.youtube.com/watch?v={vid}'...")
            self._videos.append(Video(vid, *earlier_deck_urls))
        self._id = self.videos[0].channel_id if self else None
        try:
            self._ytsp_data = self._get_ytsp() if self._id else None
        except TypeError:
            raise ScrapingError(
                "YTSP failed with TypeError. Are you sure the channel has at least two tabs "
                "(one being 'Videos')?")
        except (httpx.ReadTimeout, httpcore.ReadTimeout):
            _log.warning(f"YTSP timed out on {self.url!r}, re-trying with backoff...")
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
        # looking for subscribers is futile if there's only one (or none) :)
        except TimeoutException:
            return 1

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
        dstdir = dstdir or OUTPUT_DIR / "json"
        dstdir = getdir(dstdir)
        timestamp = self.scrape_time.strftime(FILENAME_TIMESTAMP_FORMAT)
        handle = self.handle.removeprefix("@").removeprefix("c_")
        filename = filename or f"{handle}_{timestamp}_channel"
        dst = dstdir / f"{sanitize_filename(filename)}.json"
        _log.info(f"Exporting channel to: '{dst}'...")
        dst.write_text(self.json, encoding="utf-8")
