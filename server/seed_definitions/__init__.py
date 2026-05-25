"""
Seed definitions for anytool's meta-object system.

Re-exports all object definitions used by seed_system_objects.py.
MetaObject defines structure, MetaRecord stores data.
"""

from .system_objects import SYSTEM_OBJECTS

__all__ = ["SYSTEM_OBJECTS"]
