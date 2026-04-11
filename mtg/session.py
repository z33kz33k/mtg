"""

    mtg.session
    ~~~~~~~~~~~
    State managers for scraping session's contexts.

    @author: mazz3rr

"""
import logging
from datetime import datetime
from operator import attrgetter
from timeit import default_timer as timer
from types import TracebackType
from typing import Self, Type

from sqlalchemy import select
from sqlalchemy.orm import Session

from mtg.data.db import NoAutoFlushSession, retrieve_or_create
from mtg.data.models import Channel, Deck, Decklist, FailedUrl, Snapshot, Tag, Video
from mtg.lib.scrape.core import normalize_url, throttle_with_countdown
from mtg.lib.text import get_hash
from mtg.lib.time import get_formatted_time

_log = logging.getLogger(__name__)


# TODO: each successfully scraped URL should be removed from failed ones (important for
#  re-scraping)
class UrlsStateManager:
    """State manager for already scraped and failed URLs.
    """
    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self.current_snapshot, self.current_video = None, None
        self.ignore_scraped, self.ignor_failed = False, False

    def is_scraped(self, url: str) -> bool:
        if self.ignore_scraped:
            return False
        for video in self.current_snapshot.channel.videos:
            for deck in video.decks:
                if deck.json_metadata and (deck_url := deck.json_metadata.get("url")):
                    if normalize_url(url) == normalize_url(deck_url):
                        return True
        return False

    def is_failed(self, url: str) -> bool:
        if self.ignore_failed:
            return False
        return normalize_url(url) in {
            furl.text for furl in self.current_snapshot.channel.failed_urls}

    def add_failed(self, url: str) -> None:
        url = normalize_url(url)
        if url in self.current_snapshot.channel.failed_urls:
            return
        failed_url = FailedUrl(text=url)
        self._db_session.add(failed_url)
        self.current_snapshot.channel.failed_urls.append(failed_url)
        self._db_session.flush()

    def prune_failed(self, keeper_chids: set[str]) -> None:
        """Prune failed URLs from channels that are not in 'keeper_chids'.
        """
        channels_count, urls_count = 0, 0
        stmt = select(Channel).where(Channel.yt_id.not_in(keeper_chids))

        for channel in self._db_session.scalars(stmt):
            failed_count = len(channel.failed_urls)
            if failed_count:
                channels_count += 1
                urls_count += failed_count
                channel.failed_urls.clear()

        self._db_session.flush()

        _log.info(
            f"Removed failed URLs data for {channels_count:,} channel(s) ({urls_count:,} URL(s) "
            f"in total)")


class CoolOffManager:
    """Keeps the things cool (with YT and pytube).
    """
    MAX_VIDEOS = 400

    def __init__(self) -> None:
        self.total_decks, self.total_videos, self.total_channels = 0, 0, 0
        self.current_videos = 0

    def _cool_off(self) -> None:
        _log.info(f"Throttling for 5 minutes before the next batch...")
        throttle_with_countdown(5 * 60)
        self.current_videos = 0

    def bump_channel(self) -> None:
        self.total_channels += 1

    def bump_video(self) -> None:
        self.total_videos += 1
        self.current_videos += 1
        if self.current_videos >= self.MAX_VIDEOS:
            self._cool_off()

    def bump_decks(self, decks: int) -> None:
        self.total_decks += decks


class ScrapingSession:
    """Context manager to ensure proper state management during scraping.
    """
    @property
    def ignore_failed(self) -> bool:
        return self._usm.ignore_failed

    @ignore_failed.setter
    def ignore_failed(self, value: bool) -> None:
        self._usm.ignore_failed = value

    @property
    def ignore_scraped(self) -> bool:
        return self._usm.ignore_scraped

    @ignore_scraped.setter
    def ignore_scraped(self, value: bool) -> None:
        self._usm.ignore_scraped = value

    def __init__(self) -> None:
        self._db_session: Session | None = None
        self._usm: UrlsStateManager | None = None
        self._cooloff: CoolOffManager | None = None

    def __enter__(self) -> Self:
        self._start = timer()
        # as we want DB session's lifetime to be the same as this session's, we need a
        # fine-grained control when states are persisted in the session's context,
        # this enables exactly that by enforcing manual flushing to the db transaction's buffer
        self._db_session = NoAutoFlushSession()
        self._usm = UrlsStateManager(self._db_session)
        self._cooloff = CoolOffManager()
        self._current_channel: Channel | None = None
        return self

    def __exit__(
            self, exc_type: Type[BaseException] | None, exc_val: BaseException | None,
            exc_tb: TracebackType | None) -> None:
        _log.info(
            f"Session finished with: {self._cooloff.total_decks} deck(s) from "
            f"{self._cooloff.total_videos} video(s) from "
            f"{self._cooloff.total_channels} channel(s) scraped in total")

        # db session finalization
        elapsed = get_formatted_time(timer() - self._start)
        if exc_type is None:
            _log.info(f"Scraping session finished successfully in {elapsed}")
            self._db_session.commit()
        else:
            _log.warning(
                f"Scraping aborted after {elapsed} due to {exc_type}. Rolling back the database "
                f"changes...")
            self._db_session.rollback()
        self._db_session.close()

        self._usm = None
        self._cooloff = None

    def set_channel(self, yt_id: str) -> None:
        channel = retrieve_or_create(self._db_session, Channel, yt_id=yt_id)
        self._current_channel = channel

    def get_scraped_video_yt_ids(self) -> list[str]:
        videos = sorted(
            [video for snapshot in self._current_channel.snapshots for video in snapshot.videos],
            key=attrgetter("publish_time"), reverse=True
        )
        return [video.yt_id for video in videos]

    def set_snapshot(
            self, title: str, description: str, tags: list[str], subscribers: int,
            scrape_time: datetime) -> None:
        snapshot = Snapshot(
            title=title,
            description=description,
            subscribers=subscribers,
            scrape_time=scrape_time,
        )
        self._db_session.add(snapshot)

        # tags
        if tags:
            existing_tags = set(self._db_session.scalars(select(Tag.text)).all())
            for tag_data in tags:
                if tag_data not in existing_tags:
                    tag = Tag(text=tag_data)
                    self._db_session.add(tag)
                    snapshot.tags.append(tag)

        self._current_channel.snapshots.append(snapshot)
        self._usm.current_snapshot = snapshot
        self._db_session.flush()

    def set_video(
            self, yt_id: str, title: str, descritpion: str, keywords: list[str],
            publish_time: datetime, views: int, comment: str | None) -> None:
        video = Video(
            yt_id=yt_id,
            title=title,
            description=descritpion,
            publish_time=publish_time,
            views=views,
            comment=comment,
        )
        self._db_session.add(video)

        # keywords
        if keywords:
            existing_tags = set(self._db_session.scalars(select(Tag.text)).all())
            for kw_data in keywords:
                if kw_data not in existing_tags:
                    tag = Tag(text=kw_data)
                    self._db_session.add(tag)
                    video.keywords.append(tag)

        self._usm.current_snapshot.videos.append(video)
        self._usm.current_video = video
        self._db_session.flush()

    def set_deck(self, decklist_text: str, json_metadata: dict | None) -> None:
        sha = get_hash(decklist_text, 40, sep="-")
        decklist = retrieve_or_create(self._db_session, Decklist, hash=sha)
        decklist.text = decklist_text

        self._db_session.add(decklist)
        deck = Deck(json_metadata=json_metadata)
        self._db_session.add(deck)
        decklist.decks.append(deck)
        self._usm.current_video.decks.append(deck)

        self._db_session.flush()

    # UrlsStateManager API
    def is_scraped(self, url: str) -> bool:
        return self._usm.is_scraped(url)

    def is_failed(self, url: str) -> bool:
        return self._usm.is_failed(url)

    def add_failed(self, url: str) -> None:
        self._usm.add_failed(url)

    def prune_failed(self, keeper_chids: set[str]) -> None:
        """Prune failed URLs from channels that are not in 'keeper_chids'.
        """
        self._usm.prune_failed(keeper_chids)

    # CoolOffManager API
    def bump_channel(self) -> None:
        self._cooloff.bump_channel()

    def bump_video(self) -> None:
        self._cooloff.bump_video()

    def bump_decks(self, decks: int) -> None:
        self._cooloff.bump_decks(decks)
