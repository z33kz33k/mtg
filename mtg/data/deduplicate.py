"""

    data.deduplicate
    ~~~~~~~~~~~~~~~~
    Deduplicate decks per channel within the dataset in terms of their text decklists.

    @author: mazz3rr

"""
import itertools
import logging
from collections import defaultdict
from operator import attrgetter

from sqlalchemy import select
from sqlalchemy.orm import Session
from tqdm import tqdm

from mtg.logging import init_log
from mtg.data.db import DefaultSession
from mtg.data.models import Channel
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


if __name__ == '__main__':
    init_log()
    with DefaultSession.begin() as session:
        deduplicate(session)
