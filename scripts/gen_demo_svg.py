"""Render a representative redistail session to an SVG for the README.

This drives the *real* redistail Renderer with a recording rich Console, so the
colors in docs/demo.svg are exactly what you see in a live terminal.

Run:  uv run python scripts/gen_demo_svg.py
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from rich.console import Console

from redistail.events import KeyEvent
from redistail.format import Renderer
from redistail.options import Settings


def _ts(hms: str) -> datetime:
    return datetime.strptime(f"2024-05-14 {hms}", "%Y-%m-%d %H:%M:%S")


EVENTS: list[KeyEvent] = [
    KeyEvent(
        op="set",
        db=0,
        key="session:abc123",
        ts=_ts("14:02:11"),
        value="ana@example.com|role=admin",
        value_type="string",
    ),
    KeyEvent(
        op="expire",
        db=0,
        key="session:abc123",
        ts=_ts("14:02:11"),
        value="900",
        value_type="string",
    ),
    KeyEvent(
        op="hset",
        db=0,
        key="user:42",
        ts=_ts("14:02:12"),
        value={"last_seen": "1715695332", "logins": "37"},
        value_type="hash",
    ),
    KeyEvent(
        op="incrby",
        db=0,
        key="metrics:requests",
        ts=_ts("14:02:12"),
        value="148021",
        value_type="string",
    ),
    KeyEvent(
        op="rpush",
        db=0,
        key="queue:emails",
        ts=_ts("14:02:13"),
        value=["welcome:42", "digest:17", "receipt:1007"],
        value_type="list",
    ),
    KeyEvent(
        op="rename",
        db=0,
        key="lock:job:42 → lock:job:42:done",
        ts=_ts("14:02:13"),
    ),
    KeyEvent(
        op="del",
        db=0,
        key="cache:homepage",
        ts=_ts("14:02:14"),
    ),
    KeyEvent(
        op="expired",
        db=0,
        key="session:abc123",
        ts=_ts("14:02:15"),
    ),
    KeyEvent(
        op="evicted",
        db=0,
        key="cache:product:884",
        ts=_ts("14:02:15"),
    ),
    # A hot counter collapsed by redistail.
    KeyEvent(
        op="incrby",
        db=0,
        key="metrics:requests",
        ts=_ts("14:02:16"),
        source="synthetic",
        extra={"collapsed_count": 9213},
    ),
]


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "docs"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "demo.svg"

    settings = Settings(url="redis://localhost:6379/0", with_values=True)
    console = Console(
        record=True,
        force_terminal=True,
        color_system="truecolor",
        width=84,
        file=io.StringIO(),
        highlight=False,
        soft_wrap=True,
    )
    renderer = Renderer(settings=settings, stdout=console.file, console=console)

    console.print("[bold]$[/] redistail redis://localhost:6379/0", highlight=False)
    console.print("[dim]✓ notify-keyspace-events=AKE  ✓ PSUBSCRIBE __keyevent@0__:*[/]")
    console.print()
    for event in EVENTS:
        renderer.emit(event)

    svg = console.export_svg(title="redistail")
    out_path.write_text(svg, encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
