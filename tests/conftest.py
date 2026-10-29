import os

import pytest


@pytest.fixture(scope='session')
def qapp():
    """Qt application shared by GUI tests, rendered offscreen without display."""
    pytest.importorskip('PySide6')
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
    # widgets left by the tests are deleted while Qt and Python are complete, deleting them during
    # the shutdown of the interpreter can crash it (segmentation fault after all tests passed)
    for widget in app.topLevelWidgets():
        widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
