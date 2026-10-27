"""QR code of the address, drawn in memory without saving the image to disk."""

import pyqrcode
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from multicrypto.gui.dialogs import monospace_label
from multicrypto.wallet import WalletAddress

QUIET_ZONE = 4  # white modules around the code required by the QR code specification


def qr_image(text: str, scale: int = 6) -> QImage:
    matrix = pyqrcode.create(text, error='M').code
    size = (len(matrix) + 2 * QUIET_ZONE) * scale
    image = QImage(size, size, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    for row, modules in enumerate(matrix):
        for column, module in enumerate(modules):
            if module:
                painter.fillRect(
                    (column + QUIET_ZONE) * scale,
                    (row + QUIET_ZONE) * scale,
                    scale,
                    scale,
                    Qt.GlobalColor.black,
                )
    painter.end()
    return image


class QrDialog(QDialog):
    def __init__(self, parent, address: WalletAddress):
        super().__init__(parent)
        self.setWindowTitle(f'QR code of "{address.label}"')
        image = QLabel()
        image.setPixmap(QPixmap.fromImage(qr_image(address.address)))
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.address_label = monospace_label(address.address)
        self.address_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.address_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copy_button = QPushButton('Copy')
        copy_button.clicked.connect(lambda: QApplication.clipboard().setText(address.address))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.addButton(copy_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(f'{address.coin} {address.address_type} · {address.path or "imported"}')
        )
        layout.addWidget(image)
        layout.addWidget(self.address_label)
        layout.addWidget(buttons)
