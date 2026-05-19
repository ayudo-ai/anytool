"""
Database — PostgreSQL with MetaObject + MetaRecord pattern.

Same architecture as Ayudo's meta tables but in 'anytool' schema.
Fully isolated from Ayudo's public schema.

Tables:
- meta_object: Defines object types (account, trigger, usage_log, etc.)
- meta_record: Stores actual data for any object type (JSONB)

Setup:
    The 'anytool' schema is created automatically on first startup.
    Tables are created inside the schema.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
    select,
    and_,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

from server.config import config

SCHEMA = config.db_schema


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ── MetaObject ───────────────────────────────────────────────────────

class MetaObject(Base):
    """Defines object types — account, trigger, usage_log, etc.

    Same pattern as Ayudo's MetaObject. Each object type gets one row.
    Records reference this via object_id FK.
    """

    __tablename__ = "meta_object"
    __table_args__ = (
        Index("ix_anytool_object_slug", "slug", unique=True),
        {"schema": SCHEMA},
    )

    object_id = Column(String(36), primary_key=True, default=_uuid)
    slug = Column(String(100), nullable=False)          # "account", "trigger"
    label = Column(String(255), nullable=False)          # "Account", "Trigger"
    description = Column(String(500), default="")
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="published")
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    records = relationship("MetaRecord", back_populates="object_definition")


# ── MetaRecord ───────────────────────────────────────────────────────

class MetaRecord(Base):
    """Stores actual data for any meta object type.

    Same pattern as Ayudo's MetaRecord:
    - object_id: FK to MetaObject
    - object_slug: denormalized for fast queries
    - custom_data: JSONB — the actual record data
    - primary_field_value: indexed lookup key (api_key, trigger_id, etc.)
    - account_id: owner account (multi-tenant isolation)
    """

    __tablename__ = "meta_record"
    __table_args__ = (
        Index("ix_anytool_record_object_slug", "object_slug"),
        Index("ix_anytool_record_account", "account_id"),
        Index("ix_anytool_record_primary_field", "primary_field_value"),
        Index("ix_anytool_record_slug_primary", "object_slug", "primary_field_value"),
        Index("ix_anytool_record_slug_account", "object_slug", "account_id"),
        Index("ix_anytool_record_is_deleted", "is_deleted"),
        Index(
            "ix_anytool_record_custom_data_gin",
            "custom_data",
            postgresql_using="gin",
            postgresql_ops={"custom_data": "jsonb_ops"},
        ),
        {"schema": SCHEMA},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    object_id = Column(
        String(36),
        ForeignKey(f"{SCHEMA}.meta_object.object_id", ondelete="CASCADE"),
        nullable=False,
    )
    object_slug = Column(String(100), nullable=False)   # Denormalized
    account_id = Column(String(36), nullable=True)      # Owner account
    workspace_id = Column(String(36), nullable=True)    # End-user / workspace

    # Core data
    custom_data = Column(JSONB, nullable=False, default=dict)
    primary_field_value = Column(String(255), nullable=True)  # Indexed lookup key

    # Metadata
    schema_version = Column(Integer, nullable=False, default=1)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    object_definition = relationship("MetaObject", back_populates="records")


# ── Engine + Session ─────────────────────────────────────────────────

engine = create_async_engine(
    config.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── Object type cache ────────────────────────────────────────────────
# Cache object_id lookups to avoid a query per record insert.

_object_cache: Dict[str, str] = {}  # slug → object_id


# ── Init ─────────────────────────────────────────────────────────────

# Default object types — created on first startup
_DEFAULT_OBJECTS = [
    {"slug": "account", "label": "Account", "description": "Developer accounts (company/team)"},
    {"slug": "workspace", "label": "Workspace", "description": "Isolated environment within an account (project, team, customer)"},
    {"slug": "api_key", "label": "API Key", "description": "API keys scoped to account + workspace"},
    {"slug": "trigger", "label": "Trigger", "description": "Deployed triggers for event polling"},
    {"slug": "usage_log", "label": "Usage Log", "description": "API call usage tracking"},
    {"slug": "webhook_log", "label": "Webhook Log", "description": "Trigger webhook delivery logs"},
]


async def init_db():
    """Create schema, tables, and seed default object types."""
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        await conn.run_sync(Base.metadata.create_all)

    # Seed default object types
    async with async_session() as session:
        for obj in _DEFAULT_OBJECTS:
            existing = await session.execute(
                select(MetaObject).where(MetaObject.slug == obj["slug"])
            )
            if not existing.scalar_one_or_none():
                session.add(MetaObject(
                    object_id=_uuid(),
                    slug=obj["slug"],
                    label=obj["label"],
                    description=obj["description"],
                ))
        await session.commit()

    # Warm the cache
    await _warm_object_cache()


async def _warm_object_cache():
    """Load object slug → object_id mapping."""
    async with async_session() as session:
        result = await session.execute(select(MetaObject))
        for obj in result.scalars().all():
            _object_cache[obj.slug] = obj.object_id


async def _get_object_id(slug: str) -> str:
    """Get object_id for a slug. Creates the object if missing."""
    if slug in _object_cache:
        return _object_cache[slug]

    async with async_session() as session:
        result = await session.execute(
            select(MetaObject).where(MetaObject.slug == slug)
        )
        obj = result.scalar_one_or_none()
        if obj:
            _object_cache[slug] = obj.object_id
            return obj.object_id

        # Auto-create
        obj_id = _uuid()
        session.add(MetaObject(
            object_id=obj_id,
            slug=slug,
            label=slug.replace("_", " ").title(),
        ))
        await session.commit()
        _object_cache[slug] = obj_id
        return obj_id


# ── Helpers ──────────────────────────────────────────────────────────


def generate_api_key() -> str:
    return f"at_{secrets.token_urlsafe(32)}"


def new_id() -> str:
    return _uuid()


def now() -> datetime:
    return datetime.now(timezone.utc)


# ── Generic CRUD ─────────────────────────────────────────────────────


async def put_record(
    object_slug: str,
    primary_key: str,
    data: Dict[str, Any],
    account_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    record_id: Optional[str] = None,
) -> MetaRecord:
    """Create or update a record. Upserts by (object_slug, primary_field_value)."""
    object_id = await _get_object_id(object_slug)

    async with async_session() as session:
        result = await session.execute(
            select(MetaRecord).where(
                MetaRecord.object_slug == object_slug,
                MetaRecord.primary_field_value == primary_key,
                MetaRecord.is_deleted.is_(False),
            )
        )
        record = result.scalar_one_or_none()

        if record:
            record.custom_data = data
            record.updated_at = now()
            if account_id is not None:
                record.account_id = account_id
        else:
            record = MetaRecord(
                id=record_id or _uuid(),
                object_id=object_id,
                object_slug=object_slug,
                account_id=account_id,
                workspace_id=workspace_id,
                custom_data=data,
                primary_field_value=primary_key,
                created_at=now(),
                updated_at=now(),
            )
            session.add(record)

        await session.commit()
        await session.refresh(record)
        return record


async def get_record(object_slug: str, primary_key: str) -> Optional[MetaRecord]:
    """Get a single record by slug + primary key."""
    async with async_session() as session:
        result = await session.execute(
            select(MetaRecord).where(
                MetaRecord.object_slug == object_slug,
                MetaRecord.primary_field_value == primary_key,
                MetaRecord.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()


async def get_record_by_field(object_slug: str, field: str, value: str) -> Optional[MetaRecord]:
    """Get a record by a field inside custom_data JSONB."""
    async with async_session() as session:
        result = await session.execute(
            select(MetaRecord).where(
                MetaRecord.object_slug == object_slug,
                MetaRecord.is_deleted.is_(False),
                MetaRecord.custom_data[field].astext == value,
            )
        )
        return result.scalar_one_or_none()


async def list_records(
    object_slug: str,
    account_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    active_only: bool = True,
) -> List[MetaRecord]:
    """List records of a type, filtered by account/workspace."""
    async with async_session() as session:
        conditions = [MetaRecord.object_slug == object_slug]
        if account_id:
            conditions.append(MetaRecord.account_id == account_id)
        if workspace_id:
            conditions.append(MetaRecord.workspace_id == workspace_id)
        if active_only:
            conditions.append(MetaRecord.is_deleted.is_(False))

        result = await session.execute(
            select(MetaRecord).where(and_(*conditions))
        )
        return list(result.scalars().all())


async def delete_record(object_slug: str, primary_key: str) -> bool:
    """Soft-delete a record."""
    async with async_session() as session:
        result = await session.execute(
            select(MetaRecord).where(
                MetaRecord.object_slug == object_slug,
                MetaRecord.primary_field_value == primary_key,
            )
        )
        record = result.scalar_one_or_none()
        if record:
            record.is_deleted = True
            record.deleted_at = now()
            record.updated_at = now()
            await session.commit()
            return True
        return False


async def update_record_fields(object_slug: str, primary_key: str, updates: Dict[str, Any]) -> bool:
    """Update specific fields in custom_data JSONB."""
    async with async_session() as session:
        result = await session.execute(
            select(MetaRecord).where(
                MetaRecord.object_slug == object_slug,
                MetaRecord.primary_field_value == primary_key,
                MetaRecord.is_deleted.is_(False),
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            return False

        data = dict(record.custom_data or {})
        data.update(updates)
        record.custom_data = data
        record.updated_at = now()
        await session.commit()
        return True
