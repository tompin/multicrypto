import os

import pytest

from multicrypto.coins import coins

# Insight API of DASH, the tests of the Insight client and of the commands use DASH with it
INSIGHT_API = {'url': 'https://insight.dash.org/insight-api'}


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


@pytest.fixture
def dash_insight(monkeypatch):
    """DASH with the Insight API (it uses Blockbook since insight.dash.org stopped working)."""
    monkeypatch.setitem(coins['DASH'], 'apis', [INSIGHT_API])
