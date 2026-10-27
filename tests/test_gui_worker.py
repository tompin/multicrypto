import threading
import time

import pytest

pytest.importorskip('PySide6')

from multicrypto.gui.worker import Worker  # noqa: E402


def wait_until(qapp, condition):
    deadline = time.monotonic() + 5
    while not condition():
        assert time.monotonic() < deadline
        qapp.processEvents()
        time.sleep(0.01)


def test_worker_runs_function_in_background_and_callback_in_gui_thread(qapp):
    worker = Worker()
    results = []

    worker.run(
        lambda: (42, threading.current_thread()),
        lambda result: results.append((result, threading.current_thread())),
        None,
    )
    wait_until(qapp, lambda: results)

    (value, task_thread), callback_thread = results[0]
    assert value == 42
    assert task_thread is not threading.main_thread()
    assert callback_thread is threading.main_thread()


def test_worker_passes_exception_to_error_callback(qapp):
    worker = Worker()
    errors = []

    def fail():
        raise ValueError('bad value')

    worker.run(fail, None, errors.append)
    wait_until(qapp, lambda: errors)

    assert str(errors[0]) == 'bad value'


def test_worker_survives_callback_error(qapp):
    worker = Worker()
    results = []

    def broken_callback(_result):
        raise RuntimeError('callback error')

    worker.run(lambda: 1, broken_callback, None)
    wait_until(qapp, lambda: worker.pending == 0)
    worker.run(lambda: 2, results.append, None)
    wait_until(qapp, lambda: results)

    assert results == [2]
