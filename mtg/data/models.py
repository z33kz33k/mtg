"""

    mtg.data.models
    ~~~~~~~~~~~~~~~
    SQLAlchemy models.

    The most defining characteristic of the employed scheme is this: there's a cascading multi
    one-to-many relationship coming all the way from a Channel (via Snapshot and Video) to a Deck
    and then in reverse direction (many-to-one) from a Deck to a Decklist.

    Then, there are two many-to-many relationships between a Tag and a Snapshot and between a Tag
    and a Video (in this context "tags" being called "keywords"). Those are handled by
    association tables.

    Then, there is a single relationship one-to-many between a Channel and a FailedUrl.

    @author: mazz3rr

"""
from datetime import datetime
from operator import attrgetter

from sqlalchemy import Column, ForeignKey, Index, Integer, JSON, String, Table, Text, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from mtg.data.structs import ChannelData, VideoData, Deck as DeckData, DataPath
from mtg.deck.arena import ArenaParser


class Base(DeclarativeBase):
    @classmethod
    def count(cls, session: Session, *filters) -> int:
        stmt = select(func.count()).select_from(cls)
        if filters:
            stmt = stmt.where(*filters)
        return session.scalar(stmt) or 0


# association tables for many-to-many relationships
snapshot_tags = Table(
    "snapshot_tags",
    Base.metadata,
    Column("snapshot_id", Integer, ForeignKey("snapshots.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True)
)
video_keywords = Table(
    "video_keywords",
    Base.metadata,
    Column("video_id", Integer, ForeignKey("videos.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey('tags.id'), primary_key=True)
)


class Channel(Base):
    """Represents a YouTube channel.

    It's essentially a collection of the channel's scraping snapshots.
    """
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)

    yt_id: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    # withdrawn from further scraping activities
    is_withdrawn: Mapped[bool] = mapped_column(default=False)

    snapshots: Mapped[list["Snapshot"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan")
    failed_urls: Mapped[list["FailedUrl"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan")

    @property
    def data(self) -> ChannelData | None:
        if not self.snapshots:
            return None
        snapshots = sorted(self.snapshots, key=attrgetter("scrape_time"), reverse=True)
        videos = sorted(
            (v.data for s in snapshots for v in s.videos),
            key=attrgetter("publish_time"),
            reverse=True
        )
        return ChannelData(
            yt_id=self.yt_id,
            title=snapshots[0].title,
            description=snapshots[0].description,
            tags=[t.text for t in snapshots[0].tags],
            subscribers=snapshots[0].subscribers,
            scrape_time=snapshots[0].scrape_time,
            videos=videos
        )


class Snapshot(Base):
    """Represents a YouTube channel at a time of its scraping.

    All the data here apart from the channel's YouTube ID and the scraping time is transient and
    dependent either on the channel owner's temporal whim (title, description) or scraping scope
    (choice of scraped videos) or other factors (subscribers).
    """
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))

    title: Mapped[str | None]
    description: Mapped[str | None]
    subscribers: Mapped[int | None]
    scrape_time: Mapped[datetime]

    channel: Mapped["Channel"] = relationship(back_populates="snapshots")
    videos: Mapped[list["Video"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan")
    tags: Mapped[list["Tag"]] = relationship(secondary=snapshot_tags, back_populates="snapshots")


class Video(Base):
    """Represents a video data scraped for a singular channel snapshot.

    Can't be duplicated in terms of YT ID. As videos can be routinely re-scraped, this means that
    a re-scraped one has to replace the older one.

    Note: "author" field isn't included as it's guaranteed to be the same as a title of the
    scraped channel (so, can be taken from the snapshot).
    """
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"))

    # sqlite_on_conflict_unique="REPLACE" means that updates with conflicting YT IDs will cause
    # the old row to be deleted and replaced by a new row
    # more on this: https://share.google/aimode/qfK5RNT74Bs3MwQ9E
    yt_id: Mapped[str] = mapped_column(
        String(11), unique=True, index=True, sqlite_on_conflict_unique="REPLACE")
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    publish_time: Mapped[datetime] = mapped_column()
    views: Mapped[int]
    comment: Mapped[str | None]

    snapshot: Mapped["Snapshot"] = relationship(back_populates="videos")
    keywords: Mapped[list["Tag"]] = relationship(secondary=video_keywords, back_populates="videos")
    decks: Mapped[list["Deck"]] = relationship(
        back_populates="video", cascade="all, delete-orphan")

    @property
    def data(self) -> VideoData:
        return VideoData(
            yt_id=self.yt_id,
            title=self.title,
            description=self.description,
            keywords=[kw.text for kw in self.keywords],
            publish_time=self.publish_time,
            views=self.views,
            comment=self.comment,
            decks=[d.data for d in self.decks if d.data],
        )


class Tag(Base):
    """Represents either a YouTube channel's tag or a YouTube video's keyword.
    """
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)

    # YT enforces a 500-character limit on a channel tag or a video keyword, but that pertains to
    # the whole space- or comma-delimited tag string and not for individual tags/keywords
    # (which ARE recommended to be only 30-characters long)
    text: Mapped[str] = mapped_column(String(500), unique=True, index=True)

    snapshots: Mapped[list["Snapshot"]] = relationship(
        secondary=snapshot_tags, back_populates="tags")
    videos: Mapped[list["Video"]] = relationship(
        secondary=video_keywords, back_populates="keywords")


class Deck(Base):
    """Represents an MTG deck data scraped from a YouTube video description.
    """
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
    decklist_id: Mapped[int | None] = mapped_column(ForeignKey("decklists.id"))

    # needs to have name different from 'metadata' not to overshadow `Base.metadata`
    json_metadata: Mapped[dict | None] = mapped_column(JSON)

    video: Mapped["Video"] = relationship(back_populates="decks")
    decklist: Mapped["Decklist"] = relationship(back_populates="decks")

    @property
    def data(self) -> DeckData | None:
        return ArenaParser(self.decklist.text, self.json_metadata).parse()

    @property
    def datapath(self) -> DataPath:
        return DataPath(
            channel_yt_id=self.video.snapshot.channel.yt_id,
            video_yt_id=self.video.yt_id,
            decklist_hash=self.decklist.hash
        )


class Decklist(Base):
    """Represents a text decklist in simplified format (with no printings specified), e.g. with
    lines like "4 Authority of the Consuls".

    This is also called "plain text" or simplified format and is different from a detailed or
    "Arena" one - that specifies printings - with lines like "4 Authority of the Consuls (FDN) 137".
    """
    __tablename__ = "decklists"

    id: Mapped[int] = mapped_column(primary_key=True)

    hash: Mapped[str] = mapped_column(String(44), index=True, unique=True)
    text: Mapped[str] = mapped_column(Text)

    # decklists orphaned by decks are deleted with an event listener defined in db.py
    decks: Mapped[list["Deck"]] = relationship(back_populates="decklist")


class FailedUrl(Base):
    """Represents a decklist URL marked as failed (to be withdrawn from further scraping).
    """
    __tablename__ = "failed_urls"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))

    text: Mapped[str] = mapped_column(Text)

    channel: Mapped["Channel"] = relationship(back_populates="failed_urls")

    __table_args__ = (  # enforces uniqueness of failed URLs per channel
        Index("ix_failed_url_per_channel", "channel_id", "text", unique=True),
    )
