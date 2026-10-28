"""Selection of the wallet address: the list shows only the addresses, the account, address type,
path and label of the selected address are shown below it."""

from typing import Dict, Iterable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QWidget

from multicrypto.gui.forms import address_details
from multicrypto.wallet import Wallet, WalletAddress

DETAIL_NAMES = ('Account', 'Address type', 'Path', 'Label')


class WalletAddressPicker(QWidget):
    changed = Signal()  # the selected address has changed

    def __init__(self):
        super().__init__()
        self.wallet: Optional[Wallet] = None
        self.addresses: List[WalletAddress] = []
        self.box = QComboBox()
        self.box.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.box.setPlaceholderText('No wallet addresses of this coin')
        self.details: Dict[str, QLabel] = {}
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow(self.box)
        for name in DETAIL_NAMES:
            label = QLabel()
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.details[name] = label
            layout.addRow(name, label)
        self.box.currentIndexChanged.connect(lambda _index: self._selection_changed())

    def set_addresses(self, wallet: Optional[Wallet], addresses: Iterable[WalletAddress]):
        """Show the addresses, the selected address is kept when it is still on the list."""
        selected = self.box.currentData()
        self.wallet = wallet
        self.addresses = list(addresses)
        self.box.blockSignals(True)
        self.box.clear()
        for address in self.addresses:
            self.box.addItem(address.address, address.id)
        index = self.box.findData(selected)
        self.box.setCurrentIndex(index if index >= 0 else min(0, len(self.addresses) - 1))
        self.box.blockSignals(False)
        self._selection_changed()

    def clear(self):
        self.set_addresses(None, [])

    def current(self) -> Optional[WalletAddress]:
        index = self.box.currentIndex()
        return self.addresses[index] if index >= 0 else None

    def select(self, address_id: str) -> bool:
        index = self.box.findData(address_id)
        if index < 0:
            return False
        self.box.setCurrentIndex(index)
        return True

    def _selection_changed(self):
        address = self.current()
        if address is None:
            details = [(name, '') for name in DETAIL_NAMES]
        else:
            details = address_details(self.wallet, address)
        for name, text in details:
            self.details[name].setText(text)
        self.changed.emit()
