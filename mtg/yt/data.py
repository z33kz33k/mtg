"""

    mtg.yt.data.py
    ~~~~~~~~~~~~~~
    Handle YouTube data.

    @author: z33k

"""
import itertools
import json
import logging
from operator import attrgetter, itemgetter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import TracebackType
from typing import Generator, Iterator, Type

from mtg import OUTPUT_DIR, READABLE_TIMESTAMP_FORMAT, README, FILENAME_TIMESTAMP_FORMAT
from mtg.deck.scrapers.melee import ALT_DOMAIN as MELEE_ALT_DOMAIN
from mtg.deck.scrapers.mtgarenapro import ALT_DOMAIN as MTGARENAPRO_ALT_DOMAIN
from mtg.utils import Counter, breadcrumbs, deserialize_dates, serialize_dates
from mtg.utils.files import getdir
from mtg.utils.gsheets import extend_gsheet_rows_with_cols, retrieve_from_gsheets_cols

_log = logging.getLogger(__name__)
CHANNEL_URL_TEMPLATE = "https://www.youtube.com/channel/{}"
CHANNELS_DIR = OUTPUT_DIR / "channels"
REGULAR_DECKLISTS_FILE = CHANNELS_DIR / "regular_decklists.json"
EXTENDED_DECKLISTS_FILE = CHANNELS_DIR / "extended_decklists.json"
FAILED_URLS_FILE = CHANNELS_DIR / "failed_urls.json"
DORMANT_THRESHOLD = 30 * 3  # days (ca 3 months)
ABANDONED_THRESHOLD = 30 * 12  # days (ca. 1 yr)
DECK_STALE_THRESHOLD = 50  # videos
VERY_DECK_STALE_THRESHOLD = 100  # videos
EXCESSIVELY_DECK_STALE_THRESHOLD = 150  # videos


@dataclass
class ChannelData:
    id: str
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


def retrieve_ids() -> list[str]:
    """Retrieve channel IDs from a private Google Sheet spreadsheet.

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
    return itertools.islice(retrieve_ids(), start_idx, end_idx)


def load_channel(channel_id: str) -> ChannelData:
    """Load all earlier scraped data for a channel designated by the provided ID.
    """
    channel_dir = getdir(CHANNELS_DIR / channel_id)
    _log.info(f"Loading channel data from: '{channel_dir}'...")
    files = [f for f in channel_dir.iterdir() if f.is_file() and f.suffix.lower() == ".json"]
    if not files:
        raise FileNotFoundError(f"No channel files found at: '{channel_dir}'")
    channels = []
    for file in files:
        channel = json.loads(file.read_text(encoding="utf-8"), object_hook=deserialize_dates)
        # deal with legacy data that contains "url"
        if "url" in channel:
            del channel["url"]
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
    for id_ in retrieve_ids():
        yield load_channel(id_)


def update_gsheet() -> None:
    """Update "channels" Google Sheets worksheet.
    """
    data = []
    for id_ in retrieve_ids():
        try:
            ch = load_channel(id_)
            formats = sorted(ch.deck_formats.items(), key=itemgetter(1), reverse=True)
            formats = [pair[0] for pair in formats]
            deck_sources = sorted(ch.deck_sources.items(), key=itemgetter(1), reverse=True)
            deck_sources = [pair[0] for pair in deck_sources]
            data.append([
                ch.title,
                CHANNEL_URL_TEMPLATE.format(ch.id),
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
            _log.warning(f"Channel data for ID {id_!r} not found. Skipping...")
            data.append(
                ["NOT AVAILABLE", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                 "N/A", "N/A", "N/A", "N/A", "N/A"])
        except AttributeError as err:
            _log.warning(f"Corrupted Channel data for ID {id_!r}: {err}. Skipping...")
            data.append(
                ["NOT AVAILABLE", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                 "N/A", "N/A", "N/A", "N/A", "N/A"])

    extend_gsheet_rows_with_cols("mtga_yt", "channels", data, start_row=2, start_col=2)


class ScrapingSession:
    """Context manager to ensure proper updates of global decklist repositories during scraping.
    """
    def __init__(self) -> None:
        self._regular_decklists, self._extended_decklists = {}, {}
        self._failed_urls = {}
        self._regular_count, self._extended_count, self._failed_count = 0, 0, 0

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
        self._failed_urls = {k: set(v) for k, v in json.loads(FAILED_URLS_FILE.read_text(
                encoding="utf-8")).items()} if FAILED_URLS_FILE.is_file() else {}
        _log.info(
            f"Loaded {len({url for v in self._failed_urls.values() for url in v}):,} decklist "
            f"URL(s) that previously failed from the global repository")
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
        FAILED_URLS_FILE.write_text(
            json.dumps({k: sorted(v) for k, v in self._failed_urls.items()}, indent=4,
                       ensure_ascii=False), encoding="utf-8")
        _log.info(
            f"Total of {self._regular_count} unique regular decklist(s) added to the global "
            f"repository")
        _log.info(
            f"Total of {self._extended_count} unique extended decklist(s) added to the global "
            f"repository")
        _log.info(
            f"Total of {self._failed_count} newly failed decklist URLs added to the global "
            f"repository to be avoided in the future")

    def update_regular(self, decklist_id: str, decklist: str) -> None:
        if decklist_id not in self._regular_decklists:
            self._regular_decklists[decklist_id] = decklist
            self._regular_count += 1

    def update_extended(self, decklist_id: str, decklist: str) -> None:
        if decklist_id not in self._extended_decklists:
            self._extended_decklists[decklist_id] = decklist
            self._extended_count += 1

    def update_failed(self, channel_id: str, *urls: str) -> None:
        urls = {url.lower().removesuffix("/") for url in urls}
        failed_urls = self._failed_urls.setdefault(channel_id, set())
        for url in urls:
            if url not in failed_urls:
                failed_urls.add(url)
                self._failed_count += 1

    def get_failed(self, channel_id: str) -> list[str]:
        return sorted(self._failed_urls.get(channel_id, set()))


def retrieve_decklist(decklist_id: str) -> str | None:
    decklists = json.loads(REGULAR_DECKLISTS_FILE.read_text(
            encoding="utf-8")) if REGULAR_DECKLISTS_FILE.is_file() else {}
    decklists.update(json.loads(EXTENDED_DECKLISTS_FILE.read_text(
            encoding="utf-8")) if EXTENDED_DECKLISTS_FILE.is_file() else {})
    return decklists.get(decklist_id)


@dataclass(frozen=True)
class DecklistPath:
    channel_id: str
    video_id: str
    decklist_id: str

    def __str__(self) -> str:
        return breadcrumbs(self.channel_id, self.video_id, self.decklist_id)

    @staticmethod
    def from_path(path: str) -> "DecklistPath":
        return DecklistPath(*path.lstrip("/").split("/", 3))


def check_decklists() -> dict[str, list[str]]:
    regular_ids, extended_ids = {}, {}
    for ch in load_channels():
        for v in ch.videos:
            for deck in v["decks"]:
                path_regular = DecklistPath(ch.id, v["id"], deck["decklist_id"])
                path_extended = DecklistPath(ch.id, v["id"], deck["decklist_extended_id"])
                regular_ids[deck["decklist_id"]] = path_regular
                extended_ids[deck["decklist_extended_id"]] = path_extended

    regular_decklists = json.loads(REGULAR_DECKLISTS_FILE.read_text(
            encoding="utf-8")) if REGULAR_DECKLISTS_FILE.is_file() else {}
    extended_decklists = json.loads(EXTENDED_DECKLISTS_FILE.read_text(
            encoding="utf-8")) if EXTENDED_DECKLISTS_FILE.is_file() else {}

    regular_orphans = {r for r in regular_ids if r not in regular_decklists}
    extended_orphans = {e for e in extended_ids if e not in extended_decklists}

    return {
        "regular_orphans": sorted({str(regular_ids[r]) for r in regular_orphans}),
        "extended_orphans": sorted({str(extended_ids[e]) for e in extended_orphans}),
    }


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
        elif MTGARENAPRO_ALT_DOMAIN in src:
            src = "mtgarena.pro"
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


def prune_channel_data_file(file: Path, *video_ids: str) -> None:
    """Prune specified videos from channel data at 'file'.
    """
    _log.info(f"Pruning {len(video_ids)} video(s) from '{file}'...")
    data = json.loads(file.read_text(encoding="utf-8"), object_hook=deserialize_dates)
    indices = []
    for i, video in enumerate([*data["videos"]]):
        if video["id"] in video_ids:
            _log.info(f"Removing video data {i + 1}/{len(data['videos'])} ({video['title']!r})...")
            del data["videos"][i]
            indices.append(i)
    if indices:
        _log.info(f"Dumping pruned channel data at: '{file}'...")
        file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=serialize_dates),
            encoding="utf-8")
    else:
        _log.info(f"Nothing to prune in '{file}'...")
