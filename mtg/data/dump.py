"""

    mtg.data.dump
    ~~~~~~~~~~~~~
    Take the scraped data held in database and dump it to JSON.

    @author: mazz3rr

"""
import itertools
import logging
from collections import defaultdict
from datetime import datetime
from operator import attrgetter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from tqdm import tqdm

from mtg.constants import OUTPUT_DIR
from mtg.data.db import ENGINE
from mtg.data.models import Channel, Decklist, FailedUrl
from mtg.lib.common import get_timestamp, timed
from mtg.lib.json import to_json

_log = logging.getLogger(__name__)


class Dumper:
    SNAPSHOT_FILE_TEMPLATE = "{channel_yt_id}___{scrape_time}.json"

    def __init__(self) -> None:
        self._dump_dir: Path | None = None

    def _dump_failed_urls(self) -> None:
        dst = self._dump_dir / "failed_urls.json"
        _log.info(f"Dumping failed URLs data to {dst}...")

        data: defaultdict[str, list[str]] = defaultdict(list)
        with Session(ENGINE) as session:
            stmt = select(FailedUrl)
            for failed_url in session.scalars(stmt):
                data[failed_url.channel.yt_id].append(failed_url.text)

        dst.write_text(to_json(data, sort_data=True))
        _log.info(f"{len(list(itertools.chain([lst for lst in data.values()]))):,} URLs dumped.")

    def _dump_decklists(self) -> None:
        dst = self._dump_dir / "decklists.json"
        _log.info(f"Dumping decklists data to {dst}...")
        data: dict[str, str] = {}
        with Session(ENGINE) as session:
            stmt = select(Decklist)
            for decklist in session.scalars(stmt):
                data[decklist.hash] = decklist.text

        dst.write_text(to_json(data, sort_data=True))
        _log.info(f"{len(list(data)):,} decklists dumped.")

    def _get_channel_dir(self, channel_yt_id: str) -> Path:
        dir_ = self._dump_dir / channel_yt_id
        dir_.mkdir(parents=True, exist_ok=True)
        return dir_

    def _get_snapshot_file(self, channel_yt_id: str, scrape_time: datetime) -> Path:
        return self._get_channel_dir(channel_yt_id) / self.SNAPSHOT_FILE_TEMPLATE.format(
            channel_yt_id=channel_yt_id, scrape_time=get_timestamp(dt=scrape_time))

    # TODO: probably needs to be sped up with a thread pool
    def _dump_channels(self) -> None:
        channels_count, snapshots_count = 0, 0
        with Session(ENGINE) as session:
            stmt = select(Channel)
            for channel in tqdm(session.scalars(stmt).all(), desc="Dumping channels..."):

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

                channels_count += 1

        _log.info(f"Dumped {snapshots_count:,} snapshots of {channels_count:,} channels.")

    @timed("dumping scraped data to JSON", precision=0)
    def dump(self) -> None:
        self._dump_dir = OUTPUT_DIR / f"dump_{get_timestamp()}"
        self._dump_dir.mkdir(parents=True, exist_ok=True)
        self._dump_failed_urls()
        self._dump_decklists()
        self._dump_channels()


if __name__ == '__main__':
    Dumper().dump()
