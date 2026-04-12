"""

    mtg.data.db
    ~~~~~~~~~~~
    Handle database operations.

    @author: mazz3rr

"""
from functools import partial

from sqlalchemy import create_engine, delete, event, exists, func, select
from sqlalchemy.orm import Session, sessionmaker

from mtg.constants import APP_DIR
from mtg.data.models import Base, Deck, Decklist
from mtg.lib.json import to_json


# https://x.com/i/grok/share/1c53708fb9b148ba885ce61556618b5e
def exists_in_table(session: Session, model: type[Base], **filters) -> bool:
    """Check if a record exists using simple equality filters.

    Example:
        exists_in_table(session, User, email="test@example.com")
        exists_in_table(session, User, email="test@example.com", active=True)
    """
    stmt = select(
        exists().where(
            select(model).filter_by(**filters).exists()
        )
    )
    return session.scalar(stmt) is True


def retrieve_or_create(session: Session, model: type[Base], **attrs) -> Base:
    """Retrieve an instance of a model by the attributes passed. If not present in the database,
    first create it.
    """
    stmt = select(model).filter_by(**attrs)
    instance: Base | None = session.scalar(stmt)
    if instance:
        return instance
    instance = model(**attrs)
    session.add(instance)
    session.flush()
    return instance


@event.listens_for(Deck, "after_delete")
def delete_orphan_decklist(mapper, connection, target: Deck) -> None:
    """Delete Decklist if it has no more referencing Decks after a Deck is deleted.
    """
    if target.decklist_id is None:
        return

    # count remaining Decks that still point to this Decklist
    # (the DELETE for the current Deck has already been executed on the DB)
    remaining_count = connection.execute(
        select(func.count(1))
        .select_from(Deck)
        .where(Deck.decklist_id == target.decklist_id)
    ).scalar_one()

    if remaining_count == 0:
        # directly delete via SQL — no need to load the object into the session
        connection.execute(
            delete(Decklist).where(Decklist.id == target.decklist_id)
        )
        # the DELETE is automatically part of the current transaction


# init database
DB_PATH = APP_DIR / "scraped_data.db"
ENGINE = create_engine(
    f"sqlite:///{DB_PATH}",
    json_serializer=partial(to_json, sort_dictionaries=True, indent=None)
)
DefaultSession = sessionmaker(ENGINE)
NoAutoFlushSession = sessionmaker(ENGINE, autoflush=False)
Base.metadata.create_all(ENGINE)
