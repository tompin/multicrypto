import threading
import time

from multicrypto.gui.worker import Worker


class FakeRoot:
    """Records callbacks scheduled with after() instead of running tkinter event loop."""

    def __init__(self):
        self.callbacks = []

    def after(self, _milliseconds, callback):
        self.callbacks.append(callback)


def poll_until(root, condition):
    deadline = time.monotonic() + 5
    while not condition():
        assert time.monotonic() < deadline
        time.sleep(0.01)
        root.callbacks.pop(0)()


def test_worker_passes_result_to_callback_in_calling_thread():
    root = FakeRoot()
    worker = Worker(root)
    results = []

    worker.run(
        lambda: 42, lambda result: results.append((result, threading.current_thread())), None
    )
    poll_until(root, lambda: results)

    assert results == [(42, threading.main_thread())]


def test_worker_passes_exception_to_error_callback():
    root = FakeRoot()
    worker = Worker(root)
    errors = []

    def fail():
        raise ValueError('bad value')

    worker.run(fail, None, errors.append)
    poll_until(root, lambda: errors)

    assert str(errors[0]) == 'bad value'


def test_worker_keeps_polling_after_callback_error():
    root = FakeRoot()
    worker = Worker(root)
    results = []

    def broken_callback(_result):
        raise RuntimeError('callback error')

    worker.run(lambda: 1, broken_callback, None)
    poll_until(root, lambda: worker.pending == 0)
    worker.run(lambda: 2, results.append, None)
    poll_until(root, lambda: results)

    assert results == [2]
