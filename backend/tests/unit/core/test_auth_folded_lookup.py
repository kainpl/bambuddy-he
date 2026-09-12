"""A folded lookup that finds several case-variant users (spec §3.5).

``users.username`` / ``users.email`` are UNIQUE under SQLite's BINARY collation,
and the duplicate check in ``routes/users.py`` folded ASCII only until Unicode
case folding landed — so an install can already hold both ``Ірина`` and
``ІРИНА``. Both now match one folded lookup, where ``scalar_one_or_none()``
would raise ``MultipleResultsFound``: a 500 on login for both accounts. The
rule: the byte-exact match wins, else the oldest row, and one WARNING per
process so the administrator renames one.
"""

import logging

import pytest
from sqlalchemy import inspect

from backend.app.core import auth
from backend.app.models.user import User


@pytest.fixture(autouse=True)
def _forget_warned_collisions():
    """``_collision_warned`` is process state — warning once per process is the
    point, so a test asserting the warning must not inherit another's."""
    auth._collision_warned.clear()
    yield
    auth._collision_warned.clear()


async def _two_case_variants(db) -> tuple[User, User]:
    """The older account first, so "lowest id" and "oldest" are the same row."""
    older = User(username="Ірина", email="Ірина@example.com", role="user")
    db.add(older)
    await db.flush()
    newer = User(username="ІРИНА", email="ІРИНА@example.com", role="user")
    db.add(newer)
    await db.flush()
    assert older.id < newer.id
    return older, newer


@pytest.mark.asyncio
async def test_the_byte_exact_username_wins(db_session):
    _older, newer = await _two_case_variants(db_session)

    found = await auth.get_user_by_username(db_session, "ІРИНА")

    assert found is not None and found.id == newer.id


@pytest.mark.asyncio
async def test_no_exact_match_takes_the_oldest_and_warns_once(db_session, caplog):
    older, _newer = await _two_case_variants(db_session)

    with caplog.at_level(logging.WARNING, logger="backend.app.core.auth"):
        first = await auth.get_user_by_username(db_session, "ірина")
        after_first = [r for r in caplog.records if r.levelno == logging.WARNING]
        second = await auth.get_user_by_username(db_session, "ірина")
        after_second = [r for r in caplog.records if r.levelno == logging.WARNING]

    assert first is not None and first.id == older.id, "the older account"
    assert second is not None and second.id == older.id
    assert len(after_first) == 1
    assert "Ірина" in after_first[0].getMessage() and "ІРИНА" in after_first[0].getMessage()
    assert len(after_second) == 1, "one warning per process, not one per lookup"


@pytest.mark.asyncio
async def test_the_same_rule_covers_email(db_session):
    older, newer = await _two_case_variants(db_session)

    assert (await auth.get_user_by_email(db_session, "ІРИНА@example.com")).id == newer.id
    assert (await auth.get_user_by_email(db_session, "ірина@example.com")).id == older.id


@pytest.mark.asyncio
async def test_one_match_answers_with_its_groups_already_loaded(db_session, caplog):
    """The rewrite from ``scalar_one_or_none()`` to ``.scalars().all()`` must keep
    ``selectinload(User.groups)``: a lazy load inside an async session raises
    ``MissingGreenlet``, and every permission check reads ``user.groups``."""
    db_session.add(User(username="solo", email="solo@example.com", role="user"))
    await db_session.flush()

    with caplog.at_level(logging.WARNING, logger="backend.app.core.auth"):
        found = await auth.get_user_by_username(db_session, "SOLO")

    assert found is not None and found.username == "solo"
    assert "groups" not in inspect(found).unloaded
    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []
