"""

    mtg.yt.data.models.py
    ~~~~~~~~~~~~~~~~~~~~~
    SQLAlchemy models.

    @author: mazz3rr

"""
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer, JSON, String, Table, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from mtg.lib import naive_utc_now as utcnow


class Base(DeclarativeBase):
    pass


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

    yt_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    # withdrawn from further scraping activities
    is_withdrawn: Mapped[bool] = mapped_column(nullable=False, default=False)

    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="channel")
    failed_urls: Mapped[list["FailedUrl"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan")


class Snapshot(Base):
    """Represents a YouTube channel at a time of its scraping.

    All the data here apart from the channel's YouTube ID and the scraping time is transient and
    dependent either on the channel owner's temporal whim (title, description) or scraping scope
    (choice of scraped videos) or other factors (subscribers).
    """
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey('channels.id'))

    title: Mapped[str | None]
    description: Mapped[str | None]
    subscribers: Mapped[int | None]
    scrape_time: Mapped[datetime] = mapped_column(default=utcnow, unique=True, nullable=False)

    channel: Mapped["Channel"] = relationship(back_populates='snapshots')
    videos: Mapped[list["Video"]] = relationship(back_populates='snapshot')
    tags: Mapped[list["Tag"]] = relationship(secondary=snapshot_tags, back_populates='snapshots')


class Video(Base):
    """Represents a video data scraped for a singular channel snapshot.

    If various snapshots scrape the same videos multiple times there will be multiple records
    with the same video ID and (potentially only slightly) different data in this table.

    Note: "author" field isn't included as it's guaranteed to be the same as a title of the
    scraped channel (so, can be taken from the snapshot).
    """
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"))

    yt_id: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    title: Mapped[str | None]
    description: Mapped[str] = mapped_column(Text, nullable=False)
    publish_time: Mapped[datetime] = mapped_column(nullable=False)
    views: Mapped[int | None]

    snapshot: Mapped["Snapshot"] = relationship(back_populates='videos')
    keywords: Mapped[list["Tag"]] = relationship(secondary=video_keywords, back_populates='videos')
    decks: Mapped[list["Deck"]] = relationship(
        back_populates='videos', cascade='all, delete-orphan')


class Tag(Base):
    """Represents either a YouTube channel's tag or a YouTube video's keyword.
    """
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)

    # YT enforces a 500-character limit on a channel tag or a video keyword, but that pertains to
    # the whole space- or comma-delimited tag string and not for individual tags/keywords
    # (which ARE recommended to be only 30-characters long)
    text: Mapped[str] = mapped_column(Text, unique=True, index=True)

    snapshots: Mapped[list["Snapshot"]] = relationship(
        secondary=snapshot_tags, back_populates='tags')
    videos: Mapped[list["Video"]] = relationship(
        secondary=video_keywords, back_populates='keywords')


class Deck(Base):
    """Represents an MTG deck data scraped from a YouTube video description.
    """
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
    decklist_id: Mapped[int] = mapped_column(ForeignKey("decklists.id"))
    decklist_with_printings_id: Mapped[int] = mapped_column(
        ForeignKey("decklists_with_printings.id"))

    json_metadata: Mapped[dict] = mapped_column(JSON)  # needs to be different from `Base.metadata`

    video: Mapped["Video"] = relationship(back_populates="decks")
    decklist: Mapped["Decklist"] = relationship(back_populates="decks")
    decklist_with_printings: Mapped["DecklistWithPrintings"] = relationship(back_populates="decks")


class Decklist(Base):
    """Represents a decklist without printings specified, e.g. with lines like
    "4 Authority of the Consuls".

    This is also called "plain text" or simplified format.
    """
    __tablename__ = "decklists"

    id: Mapped[int] = mapped_column(primary_key=True)

    text: Mapped[str] = mapped_column(Text)

    decks: Mapped[list["Deck"]] = relationship(back_populates="decklist")


class DecklistWithPrintings(Base):
    """Represents a decklist with printings specified, e.g. with lines like
    "4 Authority of the Consuls (FDN) 137".

    This is also called Arena or detailed format.
    """
    __tablename__ = "decklists_with_printings"

    id: Mapped[int] = mapped_column(primary_key=True)

    text: Mapped[str] = mapped_column(Text)

    decks: Mapped[list["Deck"]] = relationship(back_populates="decklist_with_printings")


class FailedUrl(Base):
    """Represents a decklist URL marked as failed (to be withdrawn from further scraping).
    """
    __tablename__ = "failed_urls"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))

    text: Mapped[str] = mapped_column(Text, nullable=False)

    channel: Mapped["Channel"] = relationship(back_populates="failed_urls")


# TODO: an event listener to delete orphaned decklists: https://x.com/i/grok/share/e5d2d23d74d848ca863f840c7890f380
