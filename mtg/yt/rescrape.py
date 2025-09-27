"""

    mtg.yt.rescrape
    ~~~~~~~~~~~~~~~
    Re-scrape designated videos.

    @author: z33k

"""
import itertools
import logging
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from tqdm import tqdm

from mtg import OUTPUT_DIR, PathLike
from mtg.gstate import CHANNELS_DIR, DecklistsStateManager, UrlsStateManager
from mtg.utils import logging_disabled, timed
from mtg.utils.files import getdir, getfile
from mtg.utils.json import from_json, to_json
from mtg.utils.scrape import http_requests_counted
from mtg.yt import scrape_channel_videos
from mtg.yt.data import ScrapingSession, load_channel, load_channels, retrieve_ids, \
    retrieve_video_data
from mtg.yt.data.structures import DataPath, Video

_log = logging.getLogger(__name__)


def find_orphans() -> dict[str, list[str]]:
    """Check the scraped channels data for any decklists missing in the global decklist
    repositories and return their structural paths.

    Returns:
        A dictionary of string paths pointing to the orphaned decklists (both in regular and
        extended form) in the channel data.
    """
    regular_ids, extended_ids = {}, {}
    chids = retrieve_ids()
    for ch in tqdm(load_channels(*chids), total=len(chids), desc="Loading channels data..."):
        for v in ch.videos:
            for deck in v.decks:
                path_regular = DataPath(ch.id, v.id, deck.decklist_id)
                path_extended = DataPath(ch.id, v.id, deck.decklist_extended_id)
                regular_ids[deck.decklist_id] = path_regular
                extended_ids[deck.decklist_extended_id] = path_extended

    manager = DecklistsStateManager()
    manager.reset()
    manager.load()
    loaded_regular, loaded_extended = manager.regular, manager.extended
    regular_orphans = {r for r in regular_ids if r not in loaded_regular}
    extended_orphans = {e for e in extended_ids if e not in loaded_extended}

    _log.info(
        f"Found {len(regular_orphans):,} orphaned regular decklist(s) and {len(extended_orphans):,}"
        f" orphaned extended decklist(s)")

    return {
        "regular_orphans": sorted({str(regular_ids[r]) for r in regular_orphans}),
        "extended_orphans": sorted({str(extended_ids[e]) for e in extended_orphans}),
    }


def prune_channel_file(file: PathLike, *video_ids: str) -> None:
    """Prune specified videos from channel data at 'file'.
    """
    file = getfile(file)
    _log.info(f"Pruning {len(video_ids)} video(s) from '{file}'...")
    data = from_json(file.read_text(encoding="utf-8"))
    videos = data["videos"]
    data["videos"], indices = [], []
    for i, video in enumerate(videos):
        if video["id"] in video_ids:
            _log.info(f"Removing video data {i + 1}/{len(videos)} ({video['title']!r})...")
            indices.append(i)
        else:
            data["videos"].append(video)

    if indices:
        _log.info(f"Dumping pruned channel data at: '{file}'...")
        file.write_text(to_json(data), encoding="utf-8")
    else:
        _log.info(f"Nothing to prune in '{file}'")


def find_channel_files(channel_id: str, *video_ids: str) -> list[str]:
    """Find channel data files containing specified videos.
    """
    video_ids = set(video_ids)
    channel_dir = getdir(CHANNELS_DIR / channel_id)
    _log.info(f"Loading channel data from: '{channel_dir}'...")
    files = [f for f in channel_dir.iterdir() if f.is_file() and f.suffix.lower() == ".json"]
    if not files:
        raise FileNotFoundError(f"No channel files found at: '{channel_dir}'")
    filtered = []
    for file in files:
        data = from_json(file.read_text(encoding="utf-8"))
        if any(video["id"] in video_ids for video in data["videos"]):
            filtered.append(file.as_posix())
    return filtered


def backup_channel_files(chid: str, *files: PathLike) -> None:
    """Backup channel data files.
    """
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
    backup_channel_files(channel_id, *files)
    if scrape_channel_videos(channel_id, *video_ids):
        for f in files:
            prune_channel_file(f, *video_ids)


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
        session.urls_manager.ignore_scraped = True
        for i, (channel_id, video_ids) in enumerate(channels.items(), start=1):
            _log.info(
                f"Re-scraping ==> {i}/{len(channels)} <== channel for missing decklists data...")
            _process_videos(channel_id, *video_ids)


@http_requests_counted("re-scraping videos")
@timed("re-scraping videos", precision=1)
def rescrape_videos(
        *chids: str, video_filter: Callable[[Video], bool] = lambda _: True) -> None:
    """Re-scrape videos across all specified channels. Optionally, define a video-filtering
    predicate.

    The default for scraping is all known channels and all their videos.

    Args:
        *chids: channel IDs
        video_filter: video-filtering predicate
    """
    chids = chids or retrieve_ids()
    channels = retrieve_video_data(*chids, video_filter=video_filter)

    if not channels:
        _log.info("No videos found that needed re-scraping")
        return

    with ScrapingSession() as session:
        session.urls_manager.ignore_scraped_within_current_video = True
        session.urls_manager.ignore_failed = True
        for i, (channel_id, videos) in enumerate(channels.items(), start=1):
            _log.info(
                f"Re-scraping {len(videos)} video(s) of ==> {i}/{len(channels)} <== channel...")
            _process_videos(channel_id, *[v.id for v in videos])


def rescrape_by_date(
        *chids: str, after: date | None = None, before: date | None = None,
        video_filter: Callable[[Video], bool] = lambda _: True) -> None:
    """Re-scrape videos across all specified channels but only those scraped before/after the
    specified threshold dates (or inbetween them).

    If not specified, all known channels are considered.

    Args:
        *chids: channel IDs
        after: scrape videos after or equal to this date (if specified)
        before: scrape videos before this date (if specified)
        video_filter: optionally, additional video-filtering predicate
    """
    if after and before:
        rescrape_videos(
            *chids,
            video_filter=lambda v: v.scrape_time
                                   and before > v.scrape_time.date() >= after
                                   and video_filter(v)
        )
    elif after:
        rescrape_videos(
            *chids,
            video_filter=lambda v: v.scrape_time
                                   and v.scrape_time.date() >= after
                                   and video_filter(v)
        )
    elif before:
        rescrape_videos(
            *chids,
            video_filter=lambda v: v.scrape_time
                                   and before > v.scrape_time.date()
                                   and video_filter(v)
        )
    else:
        raise ValueError("At least one threshold date must be specified")


def rescrape_by_urls_pool(urls_pool: set[str], *chids: str, exact=False) -> None:
    """Re-scrape videos across all specified channels but only those that feature URLs present in
    ``urls_pool``.

    If not specified, all known channels are considered.

    Args:
        urls_pool: set of URLs to filter against
        *chids: channel IDs
        exact: if True only exact match counts, else partial match is enough
    """
    def check_partial(video: Video) -> bool:
        for featured_url in video.featured_urls:
            for pool_url in urls_pool:
                if pool_url in featured_url:
                    return True
        return False

    if exact:
        rescrape_videos(
            *chids,
            video_filter=lambda v: any(l in urls_pool for l in v.featured_urls)
        )
    rescrape_videos(
        *chids,
        video_filter=lambda v: check_partial(v)
    )


def rescrape_by_url_predicate(url_predicate: Callable[[str], bool], *chids: str) -> None:
    """Re-scrape videos across all specified channels but only those that feature URLs satisfying
    the provided predicate.

    If not specified, all known channels are considered.

    Args:
        url_predicate: URL-filtering predicate
        *chids: channel IDs
    """
    rescrape_videos(
        *chids,
        video_filter=lambda v: any(url_predicate(l) for l in v.featured_urls)
    )
