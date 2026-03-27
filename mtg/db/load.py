"""

    mtg.yt.data.load.py
    ~~~~~~~~~~~~~~~~~~~
    Load scraped data from JSON to the database.

    @author: mazz3rr

"""
import itertools
import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from tqdm import tqdm

from mtg import HOME_DIR, WITHDRAWN_DIR
from mtg.lib import get_hash
from mtg.db import exists_in_table
from mtg.gstate import CHANNELS_DIR, DECKLISTS_FILE, FAILED_URLS_FILE
from mtg.db.models import (
    Base,
    Channel,
    Snapshot,
    Video,
    Tag,
    Deck,
    Decklist,
    FailedUrl
)


DB_PATH = HOME_DIR / "scraped_data.db"


class Loader:
    def __init__(self) -> None:
        self._channels_jsons = self._load_channels(CHANNELS_DIR)
        self._withdrawn_jsons = {
            k: v for k, v in self._load_channels(WITHDRAWN_DIR).items()
            if k not in self._channels_jsons}
        self._decklists_json = json.loads(Path(DECKLISTS_FILE).read_text(encoding="utf-8"))
        self._failed_urls_json = json.loads(Path(FAILED_URLS_FILE).read_text(encoding="utf-8"))
        self._engine = create_engine(f"sqlite:///{DB_PATH}")
        Base.metadata.create_all(self._engine)

    @staticmethod
    def _load_channels(channels_dir: str) -> dict[str, list]:
        sub_dirs = [d for d in Path(channels_dir).iterdir() if d.is_dir()]
        total = len(sub_dirs)
        data = {}
        for sub_dir in tqdm(sub_dirs, total=total, desc="Loading channels data..."):
            data[sub_dir.name] = [
            json.loads(f.read_text(encoding="utf-8")) for f in Path(sub_dir).rglob("*.json")]
        return data

    def _populate_channels(self) -> None:
        with Session(self._engine) as session:
            for chid in self._channels_jsons:
                session.add(Channel(yt_id=chid))
            session.flush()
            for chid in self._withdrawn_jsons:
                session.add(Channel(yt_id=chid, is_withdrawn=True))
            session.commit()

    def _populate_failed_urls(self) -> None:
        with Session(self._engine) as session:
            for chid, urls in self._failed_urls_json.items():
                if exists_in_table(session, Channel, yt_id=chid):
                    for url in urls:
                        session.add(FailedUrl(channel_id=chid, text=url))
            session.commit()

    def _populate_decklists(self) -> None:
        with Session(self._engine) as session:
            for decklist in self._decklists_json.values():
                sha = get_hash(decklist, truncation=40, sep="-")
                session.add(Decklist(hash=sha, text=decklist))
        session.commit()

    def _populate_tags(self) -> None:
        tags = set()
        for snapshot in itertools.chain(*self._channels_jsons.values()):
            for tag in snapshot.get("tags", []):
                tags.add(tag)
            for video in snapshot["videos"]:
                for kw in video.get("keywords", []):
                    tags.add(kw)
        with Session(self._engine) as session:
            for tag in tags:
                session.add(Tag(text=tag))
        session.commit()

    def load(self) -> None:
        self._populate_channels()
        self._populate_failed_urls()
        self._populate_decklists()
        self._populate_tags()

