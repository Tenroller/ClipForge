"""Lightweight migration runner (Alembic-style) for simple upgrades.

This module discovers Python migration files under `migrations/versions` and
executes their `upgrade(conn)` functions in lexical order if not already applied.

It records applied revisions in a simple `migrations` table.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import List

from sqlalchemy import text


def _discover_versions() -> List[str]:
    root = Path(__file__).parent / "versions"
    if not root.exists():
        return []
    files = sorted([p for p in root.iterdir() if p.suffix == ".py" and not p.name.startswith("_")])
    return [f.stem for f in files]


def run_migrations(engine) -> None:
    """Run all unapplied migrations against the given SQLAlchemy engine.

    The runner expects each version module to expose `revision` (string)
    and an `upgrade(conn)` callable which accepts a SQLAlchemy Connection.
    """
    versions = _discover_versions()
    if not versions:
        return

    # Ensure migrations table exists
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS migrations (revision TEXT PRIMARY KEY, applied_at TIMESTAMP WITH TIME ZONE DEFAULT now());"))

        # Load already applied revisions
        applied = {row[0] for row in conn.execute(text("SELECT revision FROM migrations")).fetchall()}

        for mod_name in versions:
            # module path under backend.migrations.versions
            pkg = f"backend.migrations.versions.{mod_name}"
            if mod_name in applied:
                continue
            try:
                mod = importlib.import_module(pkg)
                rev = getattr(mod, "revision", None) or mod_name
                upgrade = getattr(mod, "upgrade", None)
                if not callable(upgrade):
                    # nothing to do
                    continue

                # Run upgrade
                upgrade(conn)

                # Record applied revision
                conn.execute(text("INSERT INTO migrations (revision) VALUES (:rev) ON CONFLICT DO NOTHING;"), {"rev": rev})
            except Exception:
                # Re-raise so startup fails loudly when migrations can't be applied
                raise
