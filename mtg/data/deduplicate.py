"""

    data.deduplicate
    ~~~~~~~~~~~~~~~~
    Deduplicate decks per channel within the dataset in terms of their text decklists.

    @author: mazz3rr

"""
import itertools
import logging
import math
from collections import defaultdict
from operator import attrgetter

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload
from tqdm import tqdm

from mtg.logging import init_log
from mtg.data.db import DefaultSession
from mtg.data.models import Channel, Deck, Snapshot, Video
from mtg.lib.common import from_iterable
from mtg.lib.time import timed

_log = logging.getLogger(__name__)


@timed("deck deduplication")
def deduplicate(session: Session) -> None:
    """Deduplicate decks per channel from the dataset in terms of their text decklists.
    """
    stmt = select(Channel)
    deleted_deck_paths = []

    for channel in tqdm(
            session.scalars(stmt).all(), total=Channel.count(session),
            desc="Processing channels..."):

        decks_groups = defaultdict(list)

        for snapshot in channel.snapshots:
            for video in snapshot.videos:
                for deck in video.decks:
                    decks_groups[deck.decklist.hash].append(deck)

        for duplicated_decks in decks_groups.values():
            if len(duplicated_decks) <= 1:
                continue

            # find the oldest duplicate to be left,
            # when there are more than one, choose a scraped one, if possible
            duplicated_decks.sort(key=attrgetter("video.publish_time"))
            grouped = [
                (dt, list(item)) for dt, item in
                itertools.groupby(duplicated_decks, key=attrgetter("video.publish_time"))
            ]
            _, oldest_group = grouped[0]
            if len(oldest_group) > 1:
                found = from_iterable(
                        oldest_group, lambda d: d.json_metadata and d.json_metadata.get("url"))
                found = found or oldest_group[0]
            else:
                found = oldest_group[0]
            duplicated_decks.remove(found)

            # delete
            for deck in duplicated_decks:
                deleted_deck_paths.append(deck.datapath)
                session.delete(deck)

    if deleted_deck_paths:
        _log.info(
            f"Deleted {len(deleted_deck_paths)} deck(s) duplicated per channel from the database:")
        for dp in deleted_deck_paths:
            _log.info(f"\t{dp}")


@timed("deck deduplication")
def deduplicate3(session: Session) -> None:
    _log.info("Joining tables for deduplication...")
    # eager-load everything in one query
    stmt = (
        select(Deck)
        .join(Deck.video)
        .join(Video.snapshot)
        .join(Snapshot.channel)
        .options(
            joinedload(Deck.video).joinedload(Video.snapshot).joinedload(Snapshot.channel),
            joinedload(Deck.decklist)
        )
        .order_by(Channel.id, Video.publish_time)  # stable sort
    )

    all_decks = session.scalars(stmt).all()

    _log.info("Grouping duplicated decks...")
    # group by (channel_id, decklist.hash) once
    groups = defaultdict(list)
    for deck in all_decks:
        key = (deck.video.snapshot.channel_id, deck.decklist.hash)
        groups[key].append(deck)

    deck_ids_to_delete, deleted_deck_paths = [], []
    for _, duplicated_decks in groups.items():
        if len(duplicated_decks) <= 1:
            continue

        # group by publish_time to find oldest batch
        time_groups = defaultdict(list)
        for deck in duplicated_decks:
            time_groups[deck.video.publish_time].append(deck)

        oldest_time = min(time_groups)
        oldest_group = time_groups[oldest_time]

        # prefer scraped (with url metadata)
        found = from_iterable(
            oldest_group, lambda d: d.json_metadata and d.json_metadata.get("url"), oldest_group[0])

        # delete all except found
        duplicated_decks.remove(found)
        for deck in duplicated_decks:
            deck_ids_to_delete.append(deck.id)
            deleted_deck_paths.append(deck.datapath)

    if deck_ids_to_delete:
        _log.info("Deleting duplicates...")

        batch_size = 2000
        total = len(deleted_deck_paths)

        with tqdm(total=total, desc="Deleting duplicates", unit="deck") as pbar:
            for i in range(0, total, batch_size):
                batch = deck_ids_to_delete[i:i + batch_size]

                stmt = delete(Deck).where(Deck.id.in_(batch))
                session.execute(stmt)

                pbar.update(len(batch))


        _log.info(
            f"Deleted {len(deleted_deck_paths)} deck(s) duplicated per channel from the database:")
        for dp in deleted_deck_paths:
            _log.info(f"\t{dp}")


if __name__ == '__main__':
    init_log()
    with DefaultSession.begin() as session:
        deduplicate3(session)
