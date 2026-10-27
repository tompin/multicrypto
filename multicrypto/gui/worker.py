"""Running slow operations (key derivation, network requests) outside of the GUI thread."""

import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

logger = logging.getLogger(__name__)


class _Signals(QObject):
    finished = Signal(object, object)  # callback, value


class _Task(QRunnable):
    def __init__(self, func, on_success, on_error, signals: _Signals):
        super().__init__()
        self.func = func
        self.on_success = on_success
        self.on_error = on_error
        self.signals = signals

    def run(self):
        try:
            result = self.func()
        except Exception as error:  # passed to on_error in the GUI thread
            self.signals.finished.emit(self.on_error, error)
        else:
            self.signals.finished.emit(self.on_success, result)


class Worker(QObject):
    """Run functions in the thread pool and call the callbacks in the GUI thread, since widgets
    must not be used from other threads."""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.pending = 0
        self._signals = _Signals(self)
        self._signals.finished.connect(self._finish)

    def run(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self.pending += 1
        QThreadPool.globalInstance().start(_Task(func, on_success, on_error, self._signals))

    @Slot(object, object)
    def _finish(self, callback, value):
        self.pending -= 1
        try:
            callback(value)
        except Exception:
            logger.exception('Error in the callback of the background task')
