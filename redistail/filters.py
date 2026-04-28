"""Pure filter predicates for db / key-pattern / op / redaction selection.

All functions here are pure: no I/O, no Settings mutation. They take the
relevant primitive(s) and return a boolean. ``event_allowed`` composes
them so the caller can run a single check per incoming event.

Redis keys are binary-safe and case-sensitive, so we use
``fnmatch.fnmatchcase`` (not the locale-aware ``fnmatch.fnmatch``).
"""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redistail.events import KeyEvent
    from redistail.options import Settings


def db_allowed(db: int, allowed_dbs: tuple[int, ...]) -> bool:
    """Return True if ``db`` is in the configured ``--db`` list.

    Empty tuple means "no restriction" (mirrors how the CLI normalizes
    omitted flags), but in practice the CLI always populates this with at
    least ``(0,)``.
    """
    if not allowed_dbs:
        return True
    return db in allowed_dbs


def key_allowed(
    key: str,
    patterns: tuple[str, ...],
    exclude: tuple[str, ...],
) -> bool:
    """Return True if ``key`` matches any include glob and no exclude glob.

    - Empty ``patterns`` means "include everything".
    - ``exclude`` always wins over ``patterns``.
    """
    if exclude and any(fnmatch.fnmatchcase(key, g) for g in exclude):
        return False
    if not patterns:
        return True
    return any(fnmatch.fnmatchcase(key, g) for g in patterns)


def op_allowed(op: str, allowed_ops: tuple[str, ...]) -> bool:
    """Return True if ``op`` is in the configured ``--ops`` list."""
    if not allowed_ops:
        return True
    return op.lower() in {o.lower() for o in allowed_ops}


def should_redact(key: str, redact_globs: tuple[str, ...]) -> bool:
    """Return True if ``key`` matches any ``--redact`` glob."""
    if not redact_globs:
        return False
    return any(fnmatch.fnmatchcase(key, g) for g in redact_globs)


def event_allowed(event: KeyEvent, settings: Settings) -> bool:
    """Composite check: db + key + op. Used by the streaming pipeline."""
    if not db_allowed(event.db, settings.dbs):
        return False
    if not key_allowed(event.key, settings.patterns, settings.exclude):
        return False
    return op_allowed(event.op, settings.ops)


__all__ = [
    "db_allowed",
    "event_allowed",
    "key_allowed",
    "op_allowed",
    "should_redact",
]
