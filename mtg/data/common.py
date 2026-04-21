"""

    mtg.data.common
    ~~~~~~~~~~~~~~~
    Handle scraped data.

    @author: mazz3rr

"""
import itertools
import logging
import shutil
from collections import defaultdict
from datetime import date, datetime
from operator import itemgetter
from typing import Callable, Iterator

from sqlalchemy import delete, exists, select, update
from tqdm import tqdm

from mtg.constants import CHANNELS_DIR, CHANNEL_URL_TEMPLATE, FILENAME_TIMESTAMP_FORMAT, \
    READABLE_TIMESTAMP_FORMAT, README_FILE, WITHDRAWN_DIR
from mtg.data.db import DefaultSession
from mtg.data.models import Channel, Deck, Decklist, Snapshot
from mtg.data.structures import ChannelData, VideoData
from mtg.lib.common import MarkdownTableCounter
from mtg.lib.gsheets import extend_gsheet_rows_with_cols, retrieve_from_gsheets_cols
from mtg.lib.numbers import get_ordinal_suffix
from mtg.lib.scrape.core import fetch_soup
from mtg.lib.time import naive_utc_now

_log = logging.getLogger(__name__)
_channels_cache: dict[str, ChannelData] = {}


def retrieve_ids(sheet="channels") -> list[str]:
    """Retrieve channel YouTube IDs from a private Google Sheet spreadsheet.

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


def clear_cache() -> None:
    """Clear loaded channels' cache.
    """
    _channels_cache.clear()


def load_channel(channel_id: str) -> ChannelData | None:
    """Load all earlier scraped data for a channel designated by the provided YouTube ID.
    """
    if channel_data :=  _channels_cache.get(channel_id):
        return channel_data

    with DefaultSession() as session:
        stmt = select(Channel).where(Channel.is_withdrawn == False, Channel.yt_id == channel_id)
        channel = session.scalar(stmt)
        if channel:
            channel_data = channel.data

    if channel_data:
        _channels_cache[channel_id] = channel_data

    return channel_data


def load_channels(*channel_ids: str) -> Iterator[ChannelData]:
    """Load channel data for specified YouTube channel IDs.

    If nothing is specified, all known channels are considered.
    """
    chids = channel_ids or retrieve_ids()
    for chid in chids:
        if channel := load_channel(chid):
            yield channel


def update_gsheet() -> None:
    """Update "channels" Google Sheets worksheet with the currently scraped data.
    """
    data, chids = [], retrieve_ids()
    for chid in tqdm(chids, total=len(chids), desc="Loading channels data..."):
        url = CHANNEL_URL_TEMPLATE.format(chid)
        try:
            ch = load_channel(chid)
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
            _log.warning(f"Channel data for ID {chid!r} not found. Skipping...")
            data.append(
                ["NOT AVAILABLE", url, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                 "N/A", "N/A", "N/A", "N/A", "N/A"])
        except AttributeError as err:
            _log.warning(f"Corrupted Channel data for ID {chid!r}: {err}. Skipping...")
            data.append(
                ["NOT AVAILABLE", url, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                 "N/A", "N/A", "N/A", "N/A", "N/A"])

    extend_gsheet_rows_with_cols("mtga_yt", "channels", data, start_row=2, start_col=2)


def get_aggregate_deck_data() -> tuple[MarkdownTableCounter, MarkdownTableCounter]:
    """Get aggregated deck data across all channels.
    """
    chids = retrieve_ids()
    decks = [
        d for ch
        in tqdm(load_channels(*chids), total=len(chids), desc="Loading channels data...")
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
    format_counter = MarkdownTableCounter(fmts)
    sources = [d.source for d in decks if d.source]
    source_counter = MarkdownTableCounter(sources)
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
    old_lines = README_FILE.read_text(encoding="utf-8").splitlines()
    idx = old_lines.index("### Scraped decks breakdown")
    new_lines = old_lines[:idx + 1] + [f"**{dt}**"] + table_lines
    README_FILE.write_text("\n".join(new_lines), encoding="utf-8")
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


def parse_snapshot_filename(filename: str) -> tuple[str, datetime]:
    """Parse channel snapshot's filename into the channel ID and timestamp's datetime embedded in it.
    """
    if not filename.endswith("_channel.json") or "___" not in filename:
        raise ValueError(f"Not a channel data filename: {filename!r}")
    channel_id, timestamp = filename.split("___", maxsplit=1)
    return channel_id, datetime.strptime(
        timestamp.removesuffix("_channel.json"), FILENAME_TIMESTAMP_FORMAT)


def remove_channel_data(*range_: date | datetime | str, include_withdrawn=False) -> None:
    """Remove all channel snapshots within the specified time range.

    All data with scrape times LATER or equal to start and EARLIER or equal to end is removed.

    Range can be expressed as datetime, date, or equivalent string(s) (in "%Y-%m-%d [%H:%M:%S]"
    format). An omitted end time defaults to now.

    Args:
        range_: start (and, optionally, end) of the time range
        include_withdrawn: if True, include withdrawn channels in removal (default: False)
    """
    if len(range_) == 1:
        start, end = range_[0], naive_utc_now()
    elif len(range_) == 2:
        start, end = range_
    else:
        raise ValueError(f"Invalid range: {range_}")

    for i, item in enumerate((start, end)):
        if isinstance(item, str):
            try:
                item = datetime.strptime(item, READABLE_TIMESTAMP_FORMAT)
            except ValueError:
                dt = date.fromisoformat(item)
                item = datetime.combine(dt, datetime.min.time())
        elif isinstance(item, date):
            item = datetime.combine(item, datetime.min.time())

        if i == 0:
            start = item
            start_str = start.strftime(READABLE_TIMESTAMP_FORMAT)
        elif i == 1:
            end = item
            end_str = end.strftime(READABLE_TIMESTAMP_FORMAT)

    _log.info(f"Removing channel snapshots with scrape times between {start_str} and {end_str}...")
    with DefaultSession.begin() as session:
        if include_withdrawn:
            stmt = delete(Snapshot).where(Snapshot.scrape_time.between(start, end))
        else:
            stmt = delete(Snapshot).where(
                exists()
                .where(Channel.id == Snapshot.channel_id)
                .where(Channel.is_withdrawn == False)
            ).where(Snapshot.scrape_time.between(start, end))
        result = session.execute(stmt)
    _log.info(f"Removed {result.rowcount} snapshot(s)")


# this should be theoretically always empty
def find_dangling_decklists() -> set[str]:
    """Return a set of text decklists that have no counterparts in the scraped data.
    """
    with DefaultSession() as session:
        stmt = (
            select(Decklist)
            .outerjoin(Deck)
            .where(Deck.id.is_(None))
            .distinct()
        )
        return set(d.text for d in session.scalars(stmt))


def prune_dangling_decklists() -> None:
    """Prune global decklist repositories of those decklists that have no counterpart in the
    scraped data.
    """
    with DefaultSession.begin() as session:
        stmt = delete(Decklist).where(~Decklist.decks.any())
        result = session.execute(stmt)

    if result.rowcount:
        _log.info(f"Pruned {result.rowcount} dangling decklist(s) from the database")


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
        video_filter: Callable[[VideoData], bool] = lambda _: True
) -> defaultdict[str, list[VideoData]]:
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
    for ch in tqdm(load_channels(*chids), total=len(chids), desc="Loading channels data..."):
        videos = [v for v in ch.videos if video_filter(v)]
        if videos:
            channels[ch.id].extend(videos)
    return channels


def clean_up(soft_delete=True) -> None:
    """Clean up channels data.

    Channels that are no longer present in the private Google Sheet are either removed or moved to
    "withdrawn" directory.

    Channels are removed from the sheet (or moved to another one) on a regular basis for variety of
    reasons. Either they were scraped only temporarily or they enter state that warrants it.
    This happens when they:
        * pass an arbitrary threshold for staleness (aka get abandoned)
        * pass an arbitrary threshold for deck-staleness
        * author deletes them entirely, or they delete all their content, or they delete only their Videos tab

    Args:
        soft_delete: if True, channels not present in the private Google Sheet will be only marked as 'withdrawn', otherwise they will be removed with all their scraped data from the database
    """
    ids = set(retrieve_ids())
    with DefaultSession.begin() as session:
        if soft_delete:
            stmt = update(Channel).where(Channel.yt_id.not_in(ids)).values(is_withdrawn=True)
            result = session.execute(stmt)
            if result.rowcount:
                _log.info(f"Marked {result.rowcount} channels as withdrawn.")
        else:
            stmt = delete(Channel).where(Channel.yt_id.not_in(ids))
            result = session.execute(stmt)
            if result.rowcount:
                _log.info(
                    f"Removed {result.rowcount} channels and their scraped data from the database.")


def clear_update() -> None:
    """Clear the caches and update the Google Sheet and README.md with the deck data in one go.
    """
    clear_cache()
    update_gsheet()
    update_readme_with_deck_data()
