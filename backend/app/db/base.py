from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class PublicBase(DeclarativeBase):
    """Identity tables, always in schema public."""

    metadata = MetaData(schema="public", naming_convention=NAMING)


class OrgBase(DeclarativeBase):
    """Per-organization tables; the schema comes from search_path."""

    metadata = MetaData(naming_convention=NAMING)
