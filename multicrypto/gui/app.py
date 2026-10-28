"""Entry point of the multicrypto-gui command."""

import argparse
import logging
import sys

from multicrypto.validators import check_positive


def get_args():
    parser = argparse.ArgumentParser(
        description='Graphical user interface of multicrypto with HD wallet (BIP-39 mnemonic '
        'with optional passphrase) kept in encrypted wallet file'
    )
    parser.add_argument(
        '-w',
        '--wallet',
        type=str,
        required=False,
        default=None,
        help='Path of the wallet file, default is ~/.multicrypto/wallet.mcw',
    )
    parser.add_argument(
        '-l',
        '--auto_lock',
        type=check_positive,
        required=False,
        default=5,
        help='Lock the wallet after given number of minutes of inactivity. Default 5 minutes',
    )
    return parser.parse_args()


def main():
    args = get_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        from multicrypto.gui.window import MainWindow
        from multicrypto.wallet import DEFAULT_PATH, WalletFile
    except ModuleNotFoundError as error:
        if error.name and error.name.split('.')[0] in ('nacl', 'PySide6'):
            sys.exit(
                'multicrypto-gui requires optional dependencies, install them with: '
                'pip install "multicrypto[gui]"'
            )
        raise
    app = QApplication(sys.argv[:1])
    app.setStyle('Fusion')
    window = MainWindow(WalletFile(args.wallet or DEFAULT_PATH), args.auto_lock * 60)
    window.show()
    QTimer.singleShot(0, window.start)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
