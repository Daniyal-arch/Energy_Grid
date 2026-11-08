"""Runs that outlive their connection (brief 30 Track 4.4): SSE resume and cancel.

POST /api/ask starts the graph as its own task writing into a `LiveRun` buffer; the response
reads the buffer. A dropped connection does not stop the run: the client reconnects with
GET /api/ask/{run_id}/stream and the `Last-Event-ID` header (or `?after=`) and gets the events
it missed, then the rest live. POST /api/ask/{run_id}/cancel stops the run; the stream ends
with a `done` event whose stop is "cancelled". Every event carries `id: <n>`; the first one
(`run`) names the run id.

Runs live in this process only: on Lambda a resume reaches the run while the same instance
holds it (a finished run is kept 15 minutes, at most 200 runs).
"""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.sse import event

KEEP_S = 15 * 60
MAX_RUNS = 200


@dataclass
class LiveRun:
    run_id: str
    events: list[str] = field(default_factory=list)
    done: bool = False
    ended_at: float = 0.0
    task: asyncio.Task | None = None
    changed: asyncio.Event = field(default_factory=asyncio.Event)

    def add(self, item: str) -> None:
        if item.startswith(":"):  # comments (heartbeats) are not part of the record
            return
        self.events.append(f"id: {len(self.events)}\n{item}")
        self.changed.set()

    def finish(self) -> None:
        self.done = True
        self.ended_at = time.time()
        self.changed.set()


RUNS: dict[str, LiveRun] = {}


def _prune() -> None:
    now = time.time()
    for rid in [r for r, x in RUNS.items() if x.done and now - x.ended_at > KEEP_S]:
        RUNS.pop(rid, None)
    while len(RUNS) > MAX_RUNS:
        oldest = min(RUNS.values(), key=lambda x: (not x.done, x.ended_at))
        RUNS.pop(oldest.run_id, None)


def start(source: AsyncIterator[str]) -> LiveRun:
    """The run as a task of its own: it goes on when the client goes away."""
    _prune()
    run = LiveRun("run_" + secrets.token_hex(8))
    RUNS[run.run_id] = run
    run.add(event("run", {"run_id": run.run_id}))

    async def produce() -> None:
        try:
            async for item in source:
                run.add(item)
        except asyncio.CancelledError:
            run.add(event("done", {"stop": "cancelled", "answer": "", "run_id": run.run_id}))
        finally:
            run.finish()

    run.task = asyncio.create_task(produce())
    return run


async def follow(run: LiveRun, after: int = -1) -> AsyncIterator[str]:
    """The run's events after `after`, then the new ones as they come, until it ends."""
    i = after + 1
    while True:
        run.changed.clear()
        while i < len(run.events):
            yield run.events[i]
            i += 1
        if run.done:
            return
        await run.changed.wait()


def cancel(run_id: str) -> bool:
    run = RUNS.get(run_id)
    if run is None or run.done or run.task is None:
        return False
    run.task.cancel()
    return True
