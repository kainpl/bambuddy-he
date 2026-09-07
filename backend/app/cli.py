"""BamDude administrative CLI.

Invoked via ``python -m backend.app.cli <command>``. Commands are intentionally
small and destructive operations are explicit - this is a rescue / operator
utility, not a daily-driver surface. Commands:

* ``reset_admin`` - wipe the "setup_completed" flag so the next server start
  sends the user back through ``/setup`` to create a fresh admin. Use this when
  all admin users have been lost (forgotten credentials, mistaken deletions,
  etc.) and you still have file-system / container access.

* ``init_embedded_pg`` - initialise the bundled PostgreSQL cluster (initdb +
  our conf) WITHOUT starting it. Used by the Windows installer, which then
  registers the server as its own service; it reuses the application's own
  bootstrap so the flags and the configuration file have a single source of
  truth. Requires ``DATABASE_URL=embedded`` in the environment.

Existing non-admin users and all other data are left untouched.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from sqlalchemy import delete, select

from backend.app.core.auth import has_any_admin
from backend.app.core.database import async_session, init_db
from backend.app.models.settings import Settings

logger = logging.getLogger("bamdude.cli")


async def _reset_admin() -> int:
    """Clear the setup-completed flag so the server boots into SetupPage."""
    await init_db()  # ensures Settings table exists and migrations are applied
    async with async_session() as db:
        if await has_any_admin(db):
            print(
                "Admin user(s) still exist. Refusing to reset - delete them first "
                "via the admin panel or directly in the database, then re-run "
                "this command.",
                file=sys.stderr,
            )
            return 2

        # Remove the advisory flags so the frontend + middleware route the
        # next request through /setup.
        await db.execute(delete(Settings).where(Settings.key.in_(["setup_completed", "auth_enabled"])))
        await db.commit()

        # Sanity check: re-query to confirm removal.
        result = await db.execute(select(Settings).where(Settings.key == "setup_completed"))
        assert result.scalar_one_or_none() is None, "failed to clear setup_completed"

    print(
        "Setup has been reset. Restart the server (or reload the browser) and "
        "you will be routed to /setup to create a new admin user.",
    )
    return 0


async def _init_embedded_pg() -> int:
    """initdb + write our conf for the bundled server, but do not start it.

    The Windows installer runs this, then registers the cluster as its own
    service. Reuses services/embedded_postgres so initdb flags and the conf are
    written by exactly the code the child-process path uses.
    """
    from backend.app.core.config import settings
    from backend.app.services import embedded_postgres as ep

    if not settings.embedded_postgres:
        print("DATABASE_URL is not 'embedded' — nothing to initialise.", file=sys.stderr)
        return 2

    ep._refuse_other_major()
    pgdata = settings.embedded_pg_data_dir
    if pgdata is not None and (pgdata / "PG_VERSION").exists():
        print(f"Embedded PostgreSQL cluster already present at {pgdata}; leaving it as is.")
    else:
        await ep._initdb()
    ep._write_conf()
    print(f"Embedded PostgreSQL initialised at {pgdata} (port {settings.embedded_pg_port}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.app.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("reset_admin", help="Clear setup flag so the next boot re-enters the setup flow.")
    sub.add_parser(
        "init_embedded_pg",
        help="initdb + conf for the bundled PostgreSQL without starting it (Windows installer).",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "reset_admin":
        return asyncio.run(_reset_admin())
    if args.command == "init_embedded_pg":
        return asyncio.run(_init_embedded_pg())
    parser.error(f"Unknown command: {args.command}")
    return 1  # unreachable


if __name__ == "__main__":
    raise SystemExit(main())
