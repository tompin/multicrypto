import os

import pytest


@pytest.fixture(scope='session')
def qapp():
    """Qt application shared by GUI tests, rendered offscreen without display."""
    pytest.importorskip('PySide6')
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
