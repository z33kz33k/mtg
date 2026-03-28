"""

    mtg.data.db
    ~~~~~~~~~~~
    Handle database operations.

    @author: mazz3rr

"""
from sqlalchemy import exists, select
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


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
