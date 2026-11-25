import argparse
import asyncio

from app.db.migrate import upgrade_public
from app.db.orgs import create_organization, migrate_all_orgs, seed_organization
from app.db.session import get_engine


async def _migrate() -> None:
    await asyncio.to_thread(upgrade_public)
    schemas = await migrate_all_orgs()
    print(f"migrated public and {len(schemas)} org schema(s)")


async def _create_org(name: str) -> None:
    org = await create_organization(name)
    print(f"created organization {org.name!r} in schema {org.schema_name}")


async def _seed(org: str, owner_email: str, owner_name: str) -> None:
    result = await seed_organization(org, owner_email, owner_name)
    action = "created" if result.created_org else "found"
    print(f"{action} organization {result.organization.name!r}")
    print(f"owner invite for {owner_email}: {result.invite_status}")


async def _run(args: argparse.Namespace) -> None:
    try:
        if args.command == "migrate":
            await _migrate()
        elif args.command == "seed":
            await _seed(args.org, args.owner_email, args.owner_name)
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
    seed = sub.add_parser("seed", help="create an organization and a pending owner invite")
    seed.add_argument("--org", required=True)
    seed.add_argument("--owner-email", required=True)
    seed.add_argument("--owner-name", required=True)
    asyncio.run(_run(parser.parse_args(argv)))


if __name__ == "__main__":
    main()
