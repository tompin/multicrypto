"""Fee rate field with the estimate from the block explorer API."""

import html
import math
from typing import Callable, Dict, Optional

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from multicrypto.api import FEE_TARGETS, estimate_fee_rates
from multicrypto.coins import coins
from multicrypto.gui.forms import describe_error, parse_fee_rate

INVALID_COLOR = '#c62828'
DEFAULT_TARGET = 6


class FeeRateField(QWidget):
    """Fee rate in sat/vB, Estimate fills it with the rate for the selected number of blocks."""

    def __init__(self, app, coin_symbol: Callable[[], Optional[str]]):
        super().__init__()
        self.app = app
        self.coin_symbol = coin_symbol
        self.rate = QLineEdit()
        self.rate.setPlaceholderText('sat/vB')
        self.target = QComboBox()
        for blocks in FEE_TARGETS:
            self.target.addItem(f'{blocks} block{"s" if blocks > 1 else ""}', blocks)
        self.target.setCurrentIndex(self.target.findData(DEFAULT_TARGET))
        self.button = QPushButton('Estimate')
        self.button.clicked.connect(lambda _checked=False: self.estimate())
        self.status = QLabel()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.rate)
        layout.addWidget(QLabel('confirmation in'))
        layout.addWidget(self.target)
        layout.addWidget(self.button)
        layout.addWidget(self.status, 1)
        self.rate.textEdited.connect(lambda _text: self.status.setText(''))

    def value(self) -> float:
        return parse_fee_rate(self.rate.text())

    def estimate(self):
        coin_symbol = self.coin_symbol()
        if coin_symbol is None:
            self._error('Select the source address first')
            return
        target = self.target.currentData()
        self.status.setText('')
        self.button.setEnabled(False)
        self.app.worker.run(
            lambda: estimate_fee_rates(coins[coin_symbol]),
            lambda rates: self._estimated(rates, target),
            self._failed,
        )

    def _estimated(self, rates: Dict[int, float], target: int):
        self.button.setEnabled(True)
        targets = sorted(rates)
        later = [blocks for blocks in targets if blocks >= target]
        rate = rates[later[0]] if later else rates[targets[-1]]
        self.rate.setText(f'{math.ceil(rate * 10) / 10:.1f}')

    def _failed(self, error):
        self.button.setEnabled(True)
        self._error(describe_error(error))

    def _error(self, text: str):
        self.status.setText(f'<span style="color: {INVALID_COLOR}">{html.escape(text)}</span>')
