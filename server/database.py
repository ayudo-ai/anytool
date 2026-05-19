"""
Database — PostgreSQL with MetaObject + MetaField + MetaRecord pattern.

Same architecture as Ayudo's meta tables but in 'anytool' schema.
Fully isolated from Ayudo's public schema.

Tables:
- meta_object: Defines object types (account, workspace, trigger, etc.)
- meta_field:  Defines fields per object type (typed, validated)
- meta_record: Stores actual data for any object type (JSONB)

Setup:
    1. Run seed script once:  python -m server.scripts.seed_system_objects
    2. Start server:          uvicorn server.main:app --port 8100
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
    """Defines object types — account, workspace, trigger, etc.

    Same pattern as Ayudo's MetaObject. Each object type gets one row.
    Seeded by seed_system_objects.py before first use.
    """

    __tablename__ = "meta_object"
    __table_args__ = (
        Index("ix_anytool_object_slug", "slug", unique=True),
        {"schema": SCHEMA},
    )

    object_id = Column(String(36), primary_key=True, default=_uuid)
    slug = Column(String(100), nullable=False)
    label = Column(String(255), nullable=False)
    description = Column(String(500), default="")
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="published")
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    fields = relationship("MetaField", back_populates="object_def", cascade="all, delete-orphan")
    records = relationship("MetaRecord", back_populates="object_definition")


# ── MetaField ────────────────────────────────────────────────────────

class MetaField(Base):
    """Defines individual fields within a MetaObject.

    Same pattern as Ayudo's MetaField. Typed, validated, ordered.
    Seeded alongside MetaObject by seed_system_objects.py.
    """

    __tablename__ = "meta_field"
    __table_args__ = (
        Index(
            "uq_anytool_field_object_version_apiname",
            "object_id", "object_version", "api_name",
            unique=True,
        ),
        {"schema": SCHEMA},
    )

    field_id = Column(String(36), primary_key=True, default=_uuid)
    object_id = Column(
        String(36),
        ForeignKey(f"{SCHEMA}.meta_object.object_id", ondelete="CASCADE"),
        nullable=False,
    )
    object_version = Column(Integer, nullable=False, default=1)
    api_name = Column(String(100), nullable=False)
    label = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    # string|text|number|integer|boolean|enum|date|datetime|
    # email|phone|url|json|list|reference
    required = Column(Boolean, nullable=False, default=False)
    unique = Column(Boolean, nullable=False, default=False)
    default = Column(JSONB, nullable=True)
    validation_rules = Column(JSONB, nullable=True)
    display_order = Column(Integer, nullable=True)

    object_def = relationship("MetaObject", back_populates="fields")


# ── MetaRecord ───────────────────────────────────────────────────────

class MetaRecord(Base):
    """Stores actual data for any MetaObject type.

    Same pattern as Ayudo's MetaRecord:
    - object_id: FK to MetaObject
    - object_slug: denormalized for fast queries
    - custom_data: JSONB — the actual record data
    - primary_field_value: indexed lookup key (api_key, trigger_id, etc.)
    - account_id + workspace_id: multi-tenant isolation
    """

    __tablename__ = "meta_record"
    __table_args__ = (
        Index("ix_anytool_record_object_slug", "object_slug"),
        Index("ix_anytool_record_account", "account_id"),
        Index("ix_anytool_record_primary_field", "primary_field_value"),
        Index("ix_anytool_record_slug_primary", "object_slug", "primary_field_value"),
        Index("ix_anytool_record_slug_account", "object_slug", "account_id"),
        Index("ix_anytool_record_slug_workspace", "object_slug", "workspace_id"),
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
    object_slug = Column(String(100), nullable=False)
    account_id = Column(String(36), nullable=True)
    workspace_id = Column(String(36), nullable=True)
    schema_version = Column(Integer, nullable=False, default=1)

    # Core data
    custom_data = Column(JSONB, nullable=False, default=dict)
    primary_field_value = Column(String(255), nullable=True)

    # Metadata
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

_object_cache: Dict[str, str] = {}  # slug → object_id


async def init_db():
    """Verify schema + tables exist and warm the object cache.

    Does NOT create objects — that's seed_system_objects.py's job.
    Only creates schema/tables if missing (for fresh deploys).
    """
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        await conn.run_sync(Base.metadata.create_all)

    await _warm_object_cache()


async def _warm_object_cache():
    """Load object slug → object_id mapping."""
    async with async_session() as session:
        result = await session.execute(select(MetaObject))
        for obj in result.scalars().all():
            _object_cache[obj.slug] = obj.object_id

    if not _object_cache:
        from loguru import logger
        logger.warning(
            "⚠️  No system objects found! "
            "Run: python -m server.scripts.seed_system_objects"
        )


async def _get_object_id(slug: str) -> str:
    """Get object_id for a slug. Raises if not seeded."""
    if slug in _object_cache:
        return _object_cache[slug]

    # Try DB in case cache is stale
    async with async_session() as session:
        result = await session.execute(
            select(MetaObject).where(MetaObject.slug == slug)
        )
        obj = result.scalar_one_or_none()
        if obj:
            _object_cache[slug] = obj.object_id
            return obj.object_id

    raise ValueError(
        f"Object type '{slug}' not found. "
        f"Run: python -m server.scripts.seed_system_objects"
    )


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
            if workspace_id is not None:
                record.workspace_id = workspace_id
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
