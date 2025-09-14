"""

    mtg.yt.data
    ~~~~~~~~~~~
    Handle YouTube data.

    @author: z33k

"""
import itertools
import json
import logging
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from operator import attrgetter, itemgetter
from types import TracebackType
from typing import Callable, Generator, Iterator, Self, Type

from tqdm import tqdm

from mtg import AVOIDED_DIR, FILENAME_TIMESTAMP_FORMAT, READABLE_TIMESTAMP_FORMAT, README
from mtg.gstate import CHANNELS_DIR, CoolOffManager, DecklistsStateManager, UrlsStateManager
from mtg.utils import Counter, get_ordinal_suffix, logging_disabled
from mtg.utils.files import getdir
from mtg.utils.gsheets import extend_gsheet_rows_with_cols, retrieve_from_gsheets_cols
from mtg.utils.json import from_json
from mtg.utils.scrape import fetch_soup
from mtg.yt.data.structures import CHANNEL_URL_TEMPLATE, Channel, Video

_log = logging.getLogger(__name__)


def get_channels_count() -> int:
    """Return number of currently existing channel folders.
    """
    return len([d for d in CHANNELS_DIR.iterdir() if d.is_dir()])


def retrieve_ids(sheet="channels") -> list[str]:
    """Retrieve channel IDs from a private Google Sheet spreadsheet.

    Mind that this operation takes about 4 seconds to complete.
    """
    return retrieve_from_gsheets_cols("mtga_yt", sheet, (1, ), start_row=2)[0]


def channels_batch(start_row=2, batch_size: int | None = None) -> Iterator[str]:
    """Retrieve a batch of channel IDs from a private Google Sheet spreadsheet.

    Returns:
        an iterator of string IDs
    """
    if start_row < 2:
        raise ValueError("Start row must not be lesser than 2")
    if batch_size is not None and batch_size < 1:
        raise ValueError("Batch size must be a positive integer or None")
    txt = f" {batch_size}" if batch_size else ""
    _log.info(f"Batch updating{txt} channel(s)...")
    start_idx = start_row - 2
    end_idx = None if batch_size is None else start_row - 2 + batch_size
    return itertools.islice(retrieve_ids(), start_idx, end_idx)


def load_channel(channel_id: str) -> Channel:
    """Load all earlier scraped data for a channel designated by the provided ID.
    """
    channel_dir = getdir(CHANNELS_DIR / channel_id)
    _log.info(f"Loading channel data from: '{channel_dir}'...")
    files = [f for f in channel_dir.iterdir() if f.is_file() and f.suffix.lower() == ".json"]
    if not files:
        raise FileNotFoundError(f"No channel files found at: '{channel_dir}'")
    channels = []
    for file in files:
        try:
            data = from_json(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _log.critical(f"Failed to load channel data from: '{file}'")
            sys.exit(1)
        channels.append(Channel.from_dict(data, sort_videos_by_publish_time=False))
    channels.sort(key=attrgetter("scrape_time"), reverse=True)

    videos_map = defaultdict(list)
    for video in itertools.chain(*[c.videos for c in channels]):
        videos_map[video.id].append(video)

    videos = []
    for same_video_batch in videos_map.values():
        if len(same_video_batch) > 1:
            same_video_batch.sort(key=attrgetter("scrape_time"), reverse=True)
        videos.append(same_video_batch[0])

    videos.sort(key=attrgetter("publish_time"), reverse=True)

    return Channel(
        id=channels[0].id,
        title=channels[0].title,
        description=channels[0].description,
        tags=channels[0].tags,
        subscribers=channels[0].subscribers,
        scrape_time=channels[0].scrape_time,
        videos=videos,
    )


def load_channels() -> Generator[Channel, None, None]:
    """Load channel data for all channels recorded in a private Google Sheet.
    """
    with logging_disabled():
        for id_ in retrieve_ids():
            yield load_channel(id_)


def update_gsheet() -> None:
    """Update "channels" Google Sheets worksheet with the currently scraped data.
    """
    data, ids = [], retrieve_ids()
    for id_ in tqdm(ids, total=len(ids), desc="Loading channels data..."):
        url = CHANNEL_URL_TEMPLATE.format(id_)
        try:
            with logging_disabled():
                ch = load_channel(id_)
            formats = sorted(ch.deck_formats.items(), key=itemgetter(1), reverse=True)
            formats = [pair[0] for pair in formats]
            deck_sources = sorted(ch.deck_sources.items(), key=itemgetter(1), reverse=True)
            deck_sources = [pair[0] for pair in deck_sources]
            data.append([
                ch.title,
                ch.url,
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
                ", ".join(ch.domains),
            ])
        except FileNotFoundError:
            _log.warning(f"Channel data for ID {id_!r} not found. Skipping...")
            data.append(
                ["NOT AVAILABLE", url, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                 "N/A", "N/A", "N/A", "N/A", "N/A"])
        except AttributeError as err:
            _log.warning(f"Corrupted Channel data for ID {id_!r}: {err}. Skipping...")
            data.append(
                ["NOT AVAILABLE", url, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                 "N/A", "N/A", "N/A", "N/A", "N/A"])

    extend_gsheet_rows_with_cols("mtga_yt", "channels", data, start_row=2, start_col=2)


class ScrapingSession:
    """Context manager to ensure proper state management during scraping.
    """
    def __init__(self) -> None:
        self._urls_manager, self._decklists_manager = UrlsStateManager(), DecklistsStateManager()
        self._cooloff_manager = CoolOffManager()

    def __enter__(self) -> Self:
        self._decklists_manager.load()
        self._urls_manager.load_failed()
        return self

    def __exit__(
            self, exc_type: Type[BaseException] | None, exc_val: BaseException | None,
            exc_tb: TracebackType | None) -> None:
        _log.info(
            f"Session finished with: {self._cooloff_manager.total_decks} deck(s) from "
            f"{self._cooloff_manager.total_videos} video(s) from "
            f"{self._cooloff_manager.total_channels} channel(s) scraped in total")
        self._decklists_manager.dump()
        self._urls_manager.dump_failed()
        self._decklists_manager.reset()
        self._urls_manager.reset()
        self._cooloff_manager.reset()


def get_aggregate_deck_data() -> tuple[Counter, Counter]:
    """Get aggregated deck data across all channels.
    """
    decks = [
        d for ch
        in tqdm(load_channels(), total=get_channels_count(), desc="Loading channels data...")
        for d in ch.decks]
    fmts = []
    for d in decks:
        if fmt := d.metadata.get("format"):
            fmts.append(fmt)
        elif d.metadata.get("irregular_format"):
            fmts.append("irregular")
    delta = len(decks) - len(fmts)
    if delta > 0:
        fmts += ["undefined"] * delta
    format_counter = Counter(fmts)
    sources = [d.source for d in decks if d.source]
    source_counter = Counter(sources)
    return format_counter, source_counter


def update_readme_with_deck_data() -> None:
    """Update README.md with aggregated deck data.
    """
    _log.info("Updating README.md with aggregated deck data...")
    today = datetime.today()
    dt = today.strftime(f"%d{get_ordinal_suffix(today.day)} %b %Y").lstrip("0")
    fmt_c, src_c = get_aggregate_deck_data()
    table_lines = fmt_c.markdown("Format").splitlines() + [""] + src_c.markdown(
        "Source").splitlines() + [""]
    old_lines = README.read_text(encoding="utf-8").splitlines()
    idx = old_lines.index("### Scraped decks breakdown")
    new_lines = old_lines[:idx + 1] + [f"**{dt}**"] + table_lines
    README.write_text("\n".join(new_lines), encoding="utf-8")
    _log.info("README.md updates done")


def get_duplicates() -> list[str]:
    """Get list of YouTube channels duplicated in the private Google Sheet.
    """
    ids = retrieve_ids()
    seen = set()
    duplicates = []
    for id_ in ids:
        if id_ in seen:
            duplicates.append(id_)
        else:
            seen.add(id_)
    return duplicates


def parse_channel_data_filename(filename: str) -> tuple[str, datetime]:
    """Parse channel data's filename into the channel ID and timestamp's datetime embedded in it.
    """
    if not filename.endswith("_channel.json") or "___" not in filename:
        raise ValueError(f"Not a channel data filename: {filename!r}")
    channel_id, timestamp = filename.split("___", maxsplit=1)
    return channel_id, datetime.strptime(
        timestamp.removesuffix("_channel.json"), FILENAME_TIMESTAMP_FORMAT)


def remove_channel_data(*range_: datetime | str) -> None:
    """Remove all channel data files within the specified time range.

    Range can be expressed as datime, or equivalent string(s) (in "%Y-%m-%d %H:%M:%S" format).
    An omitted end time defaults to now.

    Args:
        range_: start (and, optionally, end) of the time range
    """
    if len(range_) == 1:
        start, end = range_[0], datetime.now()
    elif len(range_) == 2:
        start, end = range_
    else:
        raise ValueError(f"Invalid range: {range_}")

    if isinstance(start, str):
        start_str = start
        start = datetime.strptime(start, READABLE_TIMESTAMP_FORMAT)
    else:
        start_str = start.strftime(READABLE_TIMESTAMP_FORMAT)
    if isinstance(end, str):
        end_str = end
        end = datetime.strptime(end, READABLE_TIMESTAMP_FORMAT)
    else:
        end_str = end.strftime(READABLE_TIMESTAMP_FORMAT)

    _log.info(f"Removing channel data between {start_str} and {end_str}...")
    for channel_dir in [d for d in CHANNELS_DIR.iterdir() if d.is_dir()]:
        for file in [f for f in channel_dir.iterdir() if f.is_file()]:
            channel_id, timestamp = parse_channel_data_filename(file.name)
            if start <= timestamp <= end:
                _log.info(f"Removing file: '{file}'...")
                file.unlink()


def find_dangling_decklists() -> dict[str, str]:
    """Find those decklists in the global decklist repositories that have no counterpart in the
    scraped data.

    Returns:
        a mapping of decklist ID to decklists
    """
    manager = DecklistsStateManager()
    manager.reset()
    manager.load()
    loaded_regular, loaded_extended = manager.regular, manager.extended
    dangling, scraped_regular, scraped_extended = {}, set(), set()
    decks = [
        d for ch
        in tqdm(load_channels(), total=get_channels_count(), desc="Loading channels data...")
        for d in ch.decks]
    for d in decks:
        scraped_regular.add(d.decklist_id)
        scraped_extended.add(d.decklist_extended_id)
    for decklist_id in loaded_regular:
        if decklist_id not in scraped_regular:
            dangling[decklist_id] = loaded_regular[decklist_id]
    for decklist_id in loaded_extended:
        if decklist_id not in scraped_extended:
            dangling[decklist_id] = loaded_extended[decklist_id]
    _log.info(f"Found {len(dangling):,} dangling decklist(s)")
    return dangling


def prune_dangling_decklists() -> None:
    """Prune global decklist repositories of those decklists that have no counterpart in the
    scraped data.
    """
    dangling = find_dangling_decklists()
    if not dangling:
        _log.info("Nothing to prune")
        return
    manager = DecklistsStateManager()
    manager.reset()
    manager.load()
    manager.prune(lambda did: did in dangling)
    manager.dump()
    _log.info(f"Pruning done")


def fetch_channel_ids(*urls: str, only_new=True) -> list[str]:
    """Fetch channel IDs from the provided channels URLs. By default, return only the ones not
    already present in the private Google Sheet.

    This function is for extracting channel IDs from links that does not contain it (they e.g. can
    contain an author's YT handle instead).
    """
    retrieved_ids = set(retrieve_ids())
    ids = []
    for url in sorted(set(urls)):
        soup = fetch_soup(url)
        if not soup:
            _log.warning(f"Skipping invalid channel URL: {url!r}...")
            continue
        prefix = CHANNEL_URL_TEMPLATE[:-2]
        tag = soup.find("link", rel="canonical")
        chid = tag.attrs["href"].removeprefix(prefix)
        if chid in retrieved_ids:
            if only_new:
                _log.info(f"Skipping already retrieved channel ID: {chid!r}...")
                continue
            else:
                _log.warning(f"Adding already retrieved channel ID: {chid!r}")
        ids.append(chid)

    return ids


def retrieve_video_data(
        *chids: str,
        video_filter: Callable[[Video], bool] = lambda _: True) -> defaultdict[str, list[Video]]:
    """Retrieve video data for specified channels. Optionally, define a video-filtering
    predicate.

    The default is retrieving all videos of all channels.

    Args:
        *chids: channel IDs
        video_filter: video-filtering predicate

    Returns:
        A video data mapped to channel IDs
    """
    chids = chids or retrieve_ids()
    channels = defaultdict(list)
    for chid in tqdm(chids, total=len(chids), desc="Retrieving video data per channel..."):
        with logging_disabled():
            ch = load_channel(chid)
        videos = [v for v in ch.videos if video_filter(v)]
        if videos:
            channels[chid].extend(videos)
    return channels


def clean_up(move=True) -> None:
    """Clean up channels data.

    Channels that are no longer present in the private Google Sheet are either removed or moved to
    "avoided" directory.

    Channels are removed from the sheet (or moved to another one) on a regular basis for variety of
    reasons. Either they were scraped only temporarily or they enter state that warrants it.
    This happens when they:
        * got abandoned
        * got deck-stale
        * got deleted entirely or deleted all their content or deleted only their Videos tab
    """
    ids = set(retrieve_ids())
    for chdir in [d for d in CHANNELS_DIR.iterdir() if d.is_dir()]:
        if chdir.name not in ids:
            if move:
                dst = AVOIDED_DIR /  chdir.name
                if dst.is_dir():
                    shutil.rmtree(dst)
                _log.info(f"Moving channel data from '{chdir}' to '{dst}'...")
                shutil.move(chdir, dst)
            else:
                _log.info(f"Removing channel data from '{chdir}'...")
                shutil.rmtree(chdir)
    manager = UrlsStateManager()
    manager.load_failed()
    manager.prune_failed(ids)
    manager.dump_failed()
