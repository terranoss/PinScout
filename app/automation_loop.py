"""Playwright's async objects must be created and used from a single asyncio
event loop/thread. Since Tkinter needs the main thread for its own event
loop, we run one persistent asyncio loop in a dedicated background thread
and schedule all Playwright work onto it via `run_coroutine_threadsafe`.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future


class AutomationLoop:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro) -> Future:
        """Schedule a coroutine on the automation loop from any thread.
        Returns a concurrent.futures.Future — call `.result()` to block
        until it completes, or attach callbacks as needed.
        """
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def shutdown(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
