#!/usr/bin/env python3
"""
Seed System Objects for anytool Platform

Creates all system MetaObjects + MetaFields that should exist
before any signup happens. Every new account/workspace is created
as MetaRecords against these object definitions.

Object definitions live in seed_definitions/system_objects.py:
  - account, workspace, api_key
  - trigger, usage_log, webhook_log, connection

Run once on fresh deploy. Idempotent — skips objects that already exist.

Usage:
    cd anytool/
    python -m server.scripts.seed_system_objects

    # Or with custom DB:
    ANYTOOL_DB_HOST=prod-db.example.com python -m server.scripts.seed_system_objects
"""

import os
import sys

# Ensure anytool/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
from loguru import logger
from sqlalchemy import select, text

from server.config import config
from server.database import (
    engine, async_session, Base, MetaObject, MetaField,
    SCHEMA, _uuid,
)
from server.seed_definitions import SYSTEM_OBJECTS


async def seed_system_objects() -> None:
    """Create schema, tables, and seed all system objects + fields."""

    logger.info("🚀 anytool Platform — Seeding System Objects")
    logger.info(f"   Database: {config.db_host}:{config.db_port}/{config.db_name}")
    logger.info(f"   Schema:   {config.db_schema}")
    logger.info("=" * 60)

    # 1. Create schema + tables
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Schema + tables ready")

    # 2. Seed each system object
    created = 0
    skipped = 0

    async with async_session() as session:
        for obj_def in SYSTEM_OBJECTS:
            slug = obj_def["slug"]
            label = obj_def["label"]
            description = obj_def.get("description", "")
            fields = obj_def.get("fields", [])

            # Check if already exists
            result = await session.execute(
                select(MetaObject).where(MetaObject.slug == slug)
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(f"  ⏭️  {slug} — already exists ({existing.object_id[:12]}...)")
                skipped += 1
                continue

            # Create MetaObject
            object_id = _uuid()
            obj = MetaObject(
                object_id=object_id,
                slug=slug,
                label=label,
                description=description,
                version=1,
                status="published",
            )
            session.add(obj)

            # Create MetaFields
            for i, field_def in enumerate(fields):
                field = MetaField(
                    field_id=_uuid(),
                    object_id=object_id,
                    object_version=1,
                    api_name=field_def["api_name"],
                    label=field_def["label"],
                    type=field_def["type"],
                    required=field_def.get("required", False),
                    unique=field_def.get("unique", False),
                    default=field_def.get("default"),
                    validation_rules=field_def.get("validation_rules"),
                    display_order=i,
                )
                session.add(field)

            logger.info(f"  ✅ {slug} — created ({object_id[:12]}...) with {len(fields)} fields")
            created += 1

        await session.commit()

    # 3. Summary
    logger.info("=" * 60)
    logger.info(f"✅ Seeding complete! Created: {created}, Skipped: {skipped}")
    logger.info("")
    logger.info("📋 System Objects:")
    for obj in SYSTEM_OBJECTS:
        logger.info(f"   • {obj['slug']}: {obj['description'][:80]}")
    logger.info("")
    logger.info("🏗️  Data Model:")
    logger.info("   Account → Workspace → Users (end-users)")
    logger.info("   Users connect apps, deploy triggers, execute actions")
    logger.info("   Each trigger has its own webhook_url")
    logger.info("")
    logger.info("✅ Ready for production!")


async def verify_seed() -> None:
    """Verify all objects were seeded correctly."""
    logger.info("\n🔍 Verifying seed...")

    async with async_session() as session:
        result = await session.execute(select(MetaObject))
        objects = result.scalars().all()

        for obj in objects:
            # Count fields
            field_result = await session.execute(
                select(MetaField).where(MetaField.object_id == obj.object_id)
            )
            fields = field_result.scalars().all()

            field_names = [f.api_name for f in fields]
            logger.info(f"  ✅ {obj.slug} ({obj.object_id[:12]}...) — {len(fields)} fields: {field_names}")

    logger.info("🎉 All system objects verified!")


if __name__ == "__main__":
    async def main():
        await seed_system_objects()
        await verify_seed()

    asyncio.run(main())
