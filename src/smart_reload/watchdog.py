from __future__ import annotations
from typing import TYPE_CHECKING

import os
import threading
import time

if TYPE_CHECKING:
    from smart_reload import manager


class _BaseWatchdog:
    def __init__(
        self,
        manager: manager.ReloadManager,
        interval: float = 1
    ) -> None:
        self.manager = manager
        self.interval = interval


class SyncWatchdog(_BaseWatchdog):
    def __init__(
        self,
        manager: manager.ReloadManager,
        interval: float = 1
    ) -> None:
        super().__init__(manager, interval)
        self.modules_lock = threading.Lock()
        self.is_closed = threading.Event()
        self.thread = threading.Thread(name="sync_watchdog", target=self._watch_files)
        self._last_time: float | None = None
    
    @property
    def last_time(self) -> float:
        if not self._last_time:
            return 0
        return self._last_time

    def _watch_files(self) -> None:
        self._last_time = time.time()
        
        while not self.is_closed.is_set():
            t = time.time()

            extensions: set[str] = set()
            with self.modules_lock:
                for name, module in self.manager.modules.items():
                    if os.stat(module.path).st_mtime > self._last_time:
                        print(name)
                        extensions.add(name)

            for name in extensions:
                self.manager.reload_module(name)
            
            time.sleep(self.interval)
            self._last_time = t