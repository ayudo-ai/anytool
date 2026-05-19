"""
Database — flexible document store using a single records table.

Same pattern as Ayudo's MetaRecord: one table stores all object types.
Object type is just a string field. Data is JSON. Query by type + key.

Object types:
- "account"    → {name, email, api_key, plan, limits, calls_this_month}
- "trigger"    → {trigger_type, provider, connection_id, webhook_url, filters, ...}
- "usage_log"  → {action, provider, status_code, timestamp}
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, String, Boolean, Integer, DateTime, JSON, Index, select, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from server.config import config


class Base(DeclarativeBase):
    pass


class Record(Base):
    """Generic record — stores any object type as JSON.

    Think of it as a document store with SQL query capability.
    """

    __tablename__ = "records"

    id = Column(String(36), primary_key=True)
    object_type = Column(String(50), nullable=False, index=True)  # "account", "trigger", etc.
    key = Column(String(255), nullable=False, index=True)  # primary lookup key (api_key, trigger_id, etc.)
    account_id = Column(String(36), nullable=True, index=True)  # owner account (null for accounts themselves)
    data = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_type_key", "object_type", "key"),
        Index("idx_type_account", "object_type", "account_id"),
    )


# ── Engine + Session ─────────────────────────────────────────────────

engine = create_async_engine(config.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Helper Functions ─────────────────────────────────────────────────


def generate_api_key() -> str:
    """Generate a new API key: at_xxxx..."""
    return f"at_{secrets.token_urlsafe(32)}"


def new_id() -> str:
    """Generate a UUID."""
    from uuid import uuid4
    return str(uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


# ── Generic CRUD ─────────────────────────────────────────────────────


async def put_record(
    object_type: str,
    key: str,
    data: Dict[str, Any],
    account_id: Optional[str] = None,
    record_id: Optional[str] = None,
) -> Record:
    """Create or update a record. Upserts by (object_type, key)."""
    async with async_session() as session:
        result = await session.execute(
            select(Record).where(
                Record.object_type == object_type,
                Record.key == key,
            )
        )
        record = result.scalar_one_or_none()

        if record:
            record.data = data
            record.updated_at = now()
            if account_id is not None:
                record.account_id = account_id
        else:
            record = Record(
                id=record_id or new_id(),
                object_type=object_type,
                key=key,
                account_id=account_id,
                data=data,
                is_active=True,
                created_at=now(),
                updated_at=now(),
            )
            session.add(record)

        await session.commit()
        await session.refresh(record)
        return record


async def get_record(object_type: str, key: str) -> Optional[Record]:
    """Get a single record by type + key."""
    async with async_session() as session:
        result = await session.execute(
            select(Record).where(
                Record.object_type == object_type,
                Record.key == key,
                Record.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()


async def get_record_by_field(object_type: str, field: str, value: str) -> Optional[Record]:
    """Get a record by a field inside the JSON data."""
    async with async_session() as session:
        # SQLite JSON extract: json_extract(data, '$.field')
        # PostgreSQL: data->>'field'
        result = await session.execute(
            select(Record).where(
                Record.object_type == object_type,
                Record.is_active.is_(True),
                Record.data[field].as_string() == value,
            )
        )
        return result.scalar_one_or_none()


async def list_records(
    object_type: str,
    account_id: Optional[str] = None,
    active_only: bool = True,
) -> List[Record]:
    """List all records of a type, optionally filtered by account."""
    async with async_session() as session:
        conditions = [Record.object_type == object_type]
        if account_id:
            conditions.append(Record.account_id == account_id)
        if active_only:
            conditions.append(Record.is_active.is_(True))

        result = await session.execute(
            select(Record).where(and_(*conditions))
        )
        return list(result.scalars().all())


async def delete_record(object_type: str, key: str) -> bool:
    """Soft-delete a record."""
    async with async_session() as session:
        result = await session.execute(
            select(Record).where(
                Record.object_type == object_type,
                Record.key == key,
            )
        )
        record = result.scalar_one_or_none()
        if record:
            record.is_active = False
            record.updated_at = now()
            await session.commit()
            return True
        return False


async def update_record_fields(object_type: str, key: str, updates: Dict[str, Any]) -> bool:
    """Update specific fields in a record's data JSON."""
    async with async_session() as session:
        result = await session.execute(
            select(Record).where(
                Record.object_type == object_type,
                Record.key == key,
                Record.is_active.is_(True),
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            return False

        data = dict(record.data or {})
        data.update(updates)
        record.data = data
        record.updated_at = now()
        await session.commit()
        return True
