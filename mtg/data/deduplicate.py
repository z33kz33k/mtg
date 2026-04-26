"""

    data.deduplicate
    ~~~~~~~~~~~~~~~~
    Deduplicate decks per channel within the dataset in terms of their text decklists.

    @author: mazz3rr

"""
import logging
from collections import defaultdict

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session, joinedload
from tqdm import tqdm

from mtg.data.db import DefaultSession
from mtg.data.models import Channel, Deck, Snapshot, Video
from mtg.lib.common import from_iterable
from mtg.lib.time import timed
from mtg.logging import init_log

_log = logging.getLogger(__name__)


@timed("deck deduplication")
def deduplicate(session: Session) -> None:
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

        session.commit()

        # optionally, shrink the database with VACUUM
        if len(deleted_deck_paths) > 20_000:
            _log.info("Compacting database file with VACUUM (this may take a while)...")
            session.execute(text("VACUUM"))
            _log.info("VACUUM completed. Database file should now be smaller.")
            session.commit()

        _log.info(
            f"Deleted {len(deleted_deck_paths)} deck(s) duplicated per channel from the database:")
        for dp in deleted_deck_paths:
            _log.info(f"\t{dp}")


if __name__ == '__main__':
    init_log()
    with DefaultSession() as session:
        deduplicate(session)

