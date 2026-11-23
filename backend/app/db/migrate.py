from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = BACKEND_DIR / "migrations"


def make_config(target: str, schema: str | None = None, database_url: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("path_separator", "os")
    cfg.set_main_option("version_locations", str(MIGRATIONS_DIR / target))
    cfg.attributes["target"] = target
    cfg.attributes["schema"] = schema
    cfg.attributes["database_url"] = database_url
    return cfg


def upgrade_public(database_url: str | None = None) -> None:
    command.upgrade(make_config("public", database_url=database_url), "head")


def upgrade_org(schema: str, database_url: str | None = None) -> None:
    command.upgrade(make_config("org", schema, database_url), "head")
