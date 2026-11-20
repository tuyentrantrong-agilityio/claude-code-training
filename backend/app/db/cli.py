import argparse
import asyncio

from app.db.migrate import upgrade_public
from app.db.orgs import create_organization, migrate_all_orgs
from app.db.session import get_engine


async def _migrate() -> None:
    await asyncio.to_thread(upgrade_public)
    schemas = await migrate_all_orgs()
    print(f"migrated public and {len(schemas)} org schema(s)")


async def _create_org(name: str) -> None:
    org = await create_organization(name)
    print(f"created organization {org.name!r} in schema {org.schema_name}")


async def _run(args: argparse.Namespace) -> None:
    try:
        if args.command == "migrate":
            await _migrate()
        else:
            await _create_org(args.name)
    finally:
        await get_engine().dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.db.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="upgrade public, then every org schema")
    create = sub.add_parser("create-org", help="create an organization and its schema")
    create.add_argument("name")
    asyncio.run(_run(parser.parse_args(argv)))


if __name__ == "__main__":
    main()
