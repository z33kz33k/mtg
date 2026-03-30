"""

    mtg.data.dump
    ~~~~~~~~~~~~~
    Take the scraped data held in database and dump it to JSON.

    @author: mazz3rr

"""
import itertools
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from operator import attrgetter
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tqdm import tqdm

from mtg.constants import OUTPUT_DIR
from mtg.data.db import ENGINE
from mtg.data.models import Channel, Decklist, FailedUrl, Snapshot
from mtg.lib.common import get_timestamp, timed
from mtg.lib.json import to_json

_log = logging.getLogger(__name__)


class Dumper:
    SNAPSHOT_FILE_TEMPLATE = "{channel_yt_id}___{scrape_time}.json"

    @property
    def _channels_dir(self) -> Path:
        dir_ = self._dump_dir / "channels"
        dir_.mkdir(parents=True, exist_ok=True)
        return dir_

    @property
    def _withdrawn_dir(self) -> Path:
        dir_ = self._dump_dir / "withdrawn"
        dir_.mkdir(parents=True, exist_ok=True)
        return dir_

    def __init__(self) -> None:
        self._dump_dir: Path | None = None

    def _dump_failed_urls(self) -> None:
        dst = self._channels_dir / "failed_urls.json"
        _log.info(f"Dumping failed URLs data to {dst}...")

        data: defaultdict[str, list[str]] = defaultdict(list)
        with Session(ENGINE) as session:
            stmt = select(FailedUrl)
            for failed_url in session.scalars(stmt):
                data[failed_url.channel.yt_id].append(failed_url.text)

        dst.write_text(to_json(data, sort_data=True))
        _log.info(f"{len(list(itertools.chain([lst for lst in data.values()]))):,} URLs dumped.")

    def _dump_decklists(self) -> None:
        dst = self._channels_dir / "decklists.json"
        _log.info(f"Dumping decklists data to {dst}...")
        data: dict[str, str] = {}
        with Session(ENGINE) as session:
            stmt = select(Decklist)
            for decklist in session.scalars(stmt):
                data[decklist.hash] = decklist.text

        dst.write_text(to_json(data, sort_data=True))
        _log.info(f"{len(list(data)):,} decklists dumped.")

    def _dump_withdrawn(self) -> None:
        _log.info(f"Dumping withdrawn channels to {self._withdrawn_dir}...")
        count = 0
        with Session(ENGINE) as session:
            stmt = select(Channel).where(Channel.is_withdrawn == True)
            for withdrawn in session.scalars(stmt):
                dst_dir = self._withdrawn_dir / withdrawn.yt_id
                dst_dir.mkdir(parents=True, exist_ok=True)
                count += 1
        _log.info(f"Dumped {count:,} withdrawn channels.")

    def _get_channel_dir(self, channel_yt_id: str) -> Path:
        dir_ = self._channels_dir / channel_yt_id
        dir_.mkdir(parents=True, exist_ok=True)
        return dir_

    def _get_snapshot_file(self, channel_yt_id: str, scrape_time: datetime) -> Path:
        return self._get_channel_dir(channel_yt_id) / self.SNAPSHOT_FILE_TEMPLATE.format(
            channel_yt_id=channel_yt_id, scrape_time=get_timestamp(dt=scrape_time))

    def _process_channel(self, channel_id: int) -> int:
        snapshots_count = 0
        with Session(ENGINE) as session:
            channel = session.get(Channel, channel_id)

            for snapshot in channel.snapshots:
                snapshot_dst = self._get_snapshot_file(
                    channel_yt_id=channel.yt_id, scrape_time=snapshot.scrape_time)
                snapshot_data = {
                    "id": channel.yt_id,
                    "title": snapshot.title,
                    "description": snapshot.description,
                    "tags": [t.text for t in snapshot.tags],
                    "subscribers": snapshot.subscribers,
                    "scrape_time": snapshot.scrape_time,
                    "videos": []
                }

                # sort oldest-first
                for video in sorted(snapshot.videos, key=attrgetter("publish_time")):
                    video_data = {
                        "id": video.yt_id,
                        "title": video.title,
                        "description": video.description,
                        "keywords": [kw.text for kw in video.keywords],
                        "publish_time": video.publish_time,
                        "views": video.views,
                        "decks": []
                    }
                    if video.comment is not None:
                        video_data["comment"] = video.comment

                    for deck in video.decks:
                        deck_data = {
                            "metadata": deck.json_metadata,
                            "decklist_hash": deck.decklist.hash,
                        }
                        video_data["decks"].append(deck_data)

                    snapshot_data["videos"].append(video_data)

                snapshot_dst.write_text(to_json(snapshot_data))
                snapshots_count += 1

        return snapshots_count

    def _dump_channels(self) -> None:
        snapshots_count = 0
        # Session is not thread-safe so only channel IDs are pulled from the db (which is
        # cheap) in the main thread and then channel gets retrieved and processed in its own
        # session within each thread
        with Session(ENGINE) as session:
            channels_count = session.scalar(select(func.count()).select_from(Channel))
            channel_ids = session.scalars(select(Channel.id)).all()

        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = [executor.submit(self._process_channel, chid) for chid in channel_ids]

            with tqdm(total=channels_count, desc="Dumping channels...") as pbar:
                for future in as_completed(futures):
                    snapshots_count += future.result()
                    pbar.update(1)

        _log.info(f"Dumped {snapshots_count:,} snapshots of {channels_count:,} channels.")

    @timed("dumping scraped data to JSON", precision=0)
    def dump(self) -> None:
        self._dump_dir = OUTPUT_DIR / f"dump_{get_timestamp()}"
        self._dump_dir.mkdir(parents=True, exist_ok=True)
        self._dump_failed_urls()
        self._dump_decklists()
        self._dump_withdrawn()
        self._dump_channels()


if __name__ == '__main__':
    Dumper().dump()
