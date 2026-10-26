"""Running slow operations (network requests, key derivation) outside of the tkinter thread."""

import logging
import queue
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)

POLL_INTERVAL = 100  # in milliseconds


class Worker:
    """Run functions in background threads and call the callbacks in the tkinter thread, since
    tkinter widgets must not be used from other threads."""

    def __init__(self, root):
        self.root = root
        self.pending = 0
        self._results = queue.Queue()
        self.root.after(POLL_INTERVAL, self._poll)

    def run(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        def target():
            try:
                result = func()
            except Exception as error:  # passed to on_error in the tkinter thread
                self._results.put((on_error, error))
            else:
                self._results.put((on_success, result))

        self.pending += 1
        threading.Thread(target=target, daemon=True).start()

    def _poll(self) -> None:
        try:
            while True:
                try:
                    callback, value = self._results.get_nowait()
                except queue.Empty:
                    break
                self.pending -= 1
                try:
                    callback(value)
                except Exception:
                    logger.exception('Error in the callback of the background task')
        finally:
            self.root.after(POLL_INTERVAL, self._poll)
