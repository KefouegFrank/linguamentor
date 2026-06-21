"""
SQLAlchemy declarative base — used by Alembic autogenerate only.
We don't use SQLAlchemy's ORM for runtime queries. Raw asyncpg is
faster and gives us full control over SQL. But Alembic needs a
declarative Base to diff models against the live DB schema.

All models import Base from here. Keep it simple.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
