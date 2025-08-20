"""

    mtg.yt.data.dump
    ~~~~~~~~~~~~~~~~
    Dump channels' deck data.

    @author: z33k

"""
from datetime import datetime
from pathlib import Path
from typing import Generator, Literal

from tqdm import tqdm

from mtg import DECKS_DIR, FILENAME_TIMESTAMP_FORMAT, PathLike
from mtg.deck.arena import ArenaParser
from mtg.deck.export import Exporter, FORMATS as EXPORT_FORMATS
from mtg.gstate import DecklistsStateManager
from mtg.utils import logging_disabled
from mtg.utils.files import getdir, sanitize_filename
from mtg.yt.data import get_channels_count, load_channels
from mtg.yt.data.structures import Channel


def _dump_data_gen(
        channels: list[Channel],
        dstdir: Path) -> Generator[tuple[Exporter | None, Path], None, None]:
    manager = DecklistsStateManager()
    manager.load()
    for channel_data in channels:
        if title := channel_data.title:
            channel_dir = dstdir / f"{sanitize_filename(title)}_({channel_data.id})"
        else:
            channel_dir = dstdir /channel_data.id
        for video_data in channel_data.videos:
            for deck_data in video_data["decks"]:
                decklist = manager.extended[deck_data["decklist_extended_id"]]
                metadata = dict(**deck_data["metadata"])
                metadata["video_url"] = video_data["url"]
                deck = ArenaParser(decklist, metadata=metadata).parse()
                if deck:
                    yield Exporter(deck), channel_dir
                else:
                    yield None, channel_dir


def dump_decks(
        dstdir: PathLike = "", fmt: Literal["arena", "forge", "json", "xmage"] = "forge") -> None:
    """Export all decks from all channels to ```dstdir``` in the format provided.
    """
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"Invalid dump format: {fmt!r}. Must be one of: {EXPORT_FORMATS}")
    timestamp = datetime.now().strftime(FILENAME_TIMESTAMP_FORMAT)
    dstdir = dstdir or DECKS_DIR / "yt" / timestamp
    dstdir = getdir(dstdir)
    channels = [*tqdm(load_channels(), total=get_channels_count(), desc="Loading channels data...")]
    total = sum(len(ch.decks) for ch in channels)
    with logging_disabled():
        for exporter, channel_dir in tqdm(
                _dump_data_gen(channels, dstdir), total=total, desc="Exporting YT decks..."):
            if exporter:
                try:
                    match fmt:
                        case "arena":
                            exporter.to_arena(channel_dir)
                        case "forge":
                            exporter.to_forge(channel_dir)
                        case "json":
                            exporter.to_json(channel_dir)
                        case "xmage":
                            exporter.to_xmage(channel_dir)
                except OSError as err:
                    if "File name too long" in str(err):
                        pass
                    else:
                        raise
