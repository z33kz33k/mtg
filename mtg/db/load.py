"""

    mtg.yt.data.load.py
    ~~~~~~~~~~~~~~~~~~~
    Load scraped data from JSON to the database.

    @author: mazz3rr

"""
import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from mtg import HOME_DIR
from mtg.yt.data.structures import Channel as ChannelData
from mtg.db.models import (
    Base,
    Channel,
    Snapshot,
    Video,
    Tag,
    Deck,
    Decklist,
    DecklistWithPrintings,
    FailedUrl
)


DB_PATH = HOME_DIR / "scraped_data.db"


class Loader:
    def __init__(
            self,
            channels_path: str,
            withdrawn_path: str,
            decklists_path: str,
            decklists_with_printings_path: str,
            failed_urls_path: str) -> None:
        self._channels_json = json.loads(Path(channels_path).read_text(encoding="utf-8"))
        self._withdrawn_json = json.loads(Path(withdrawn_path).read_text(encoding="utf-8"))
        self._decklists_json = json.loads(Path(decklists_path).read_text(encoding="utf-8"))
        self._decklists_with_printing_json = json.loads(
            Path(decklists_with_printings_path).read_text(encoding="utf-8"))
        self._failed_urls_json = json.loads(Path(failed_urls_path).read_text(encoding="utf-8"))
        self._engine = create_engine("sqlite:///" + DB_PATH)
        Base.metadata.create_all(self._engine)

