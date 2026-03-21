"""PostgreSQL runtime helpers backed by SQLAlchemy async."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from .config import settings

logger = logging.getLogger("strype.database")

_ENGINE: AsyncEngine | None = None


def database_url() -> str:
    """Return the canonical database URL."""
    return settings.resolved_database_url()


def is_postgres() -> bool:
    return database_url().startswith("postgresql+")


def get_engine() -> AsyncEngine:
    """Return a cached SQLAlchemy async engine."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_async_engine(
            database_url(),
            pool_pre_ping=True,
            future=True,
        )
    return _ENGINE


def _normalize_sql(sql: str, params: Iterable[Any] | None) -> tuple[str, dict[str, Any]]:
    if not params:
        return sql, {}
    if isinstance(params, dict):
        return sql, params
    values = list(params)
    converted = []
    bindings: dict[str, Any] = {}
    index = 0
    for char in sql:
        if char == "?":
            key = f"p{index}"
            converted.append(f":{key}")
            bindings[key] = values[index]
            index += 1
        else:
            converted.append(char)
    return "".join(converted), bindings


class AsyncResultCursor:
    """Compatibility wrapper around SQLAlchemy result objects."""

    def __init__(self, result=None):
        self._result = result
        self.rowcount = getattr(result, "rowcount", 0) if result is not None else 0

    async def fetchone(self):
        if self._result is None:
            return None
        row = self._result.fetchone()
        return CompatRow(row) if row is not None else None

    async def fetchall(self):
        if self._result is None:
            return []
        return [CompatRow(row) for row in self._result.fetchall()]


class CompatRow:
    """Mapping-friendly row wrapper that also supports numeric indexing."""

    def __init__(self, row):
        self._mapping = dict(row._mapping)
        self._values = list(self._mapping.values())

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._values[item]
        return self._mapping[item]

    def __iter__(self):
        return iter(self._mapping.items())

    def __len__(self):
        return len(self._mapping)


class CompatAsyncDB:
    """Provide the subset of aiosqlite APIs used by the stores."""

    def __init__(self, connection: AsyncConnection):
        self._connection = connection
        self._transaction = None

    async def start(self) -> None:
        self._transaction = await self._connection.begin()

    async def execute(self, sql: str, params: Iterable[Any] | None = None):
        normalized = sql.strip().upper()
        if normalized.startswith("BEGIN"):
            return AsyncResultCursor()
        if normalized == "COMMIT":
            await self.commit()
            return AsyncResultCursor()
        if normalized == "ROLLBACK":
            await self.rollback()
            return AsyncResultCursor()
        query, bindings = _normalize_sql(sql, params)
        result = await self._connection.execute(text(query), bindings)
        return AsyncResultCursor(result)

    async def commit(self) -> None:
        if self._transaction is not None:
            await self._transaction.commit()
        self._transaction = await self._connection.begin()

    async def rollback(self) -> None:
        if self._transaction is not None:
            await self._transaction.rollback()
        self._transaction = await self._connection.begin()

    async def close(self) -> None:
        if self._transaction is not None:
            await self._transaction.rollback()
            self._transaction = None
        await self._connection.close()


async def get_postgres_db():
    """Yield a compatibility wrapper over an async SQLAlchemy connection."""
    connection = await get_engine().connect()
    db = CompatAsyncDB(connection)
    await db.start()
    try:
        yield db
    finally:
        await db.close()


def run_migrations() -> None:
    """Apply Alembic migrations to the configured PostgreSQL database."""
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url())
    command.upgrade(config, "head")


async def check_connection() -> None:
    """Raise if the PostgreSQL connection is not healthy."""
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("PostgreSQL connectivity check failed")
        raise RuntimeError("Database connectivity check failed") from exc
