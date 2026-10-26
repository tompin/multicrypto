"""Entry point of the multicrypto-gui command."""

import argparse
import logging
import sys

from multicrypto.validators import check_positive


def get_args():
    parser = argparse.ArgumentParser(
        description='Graphical user interface of multicrypto with private keys kept in '
        'encrypted wallet file'
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
        import tkinter as tk

        from multicrypto.gui.window import MainWindow
        from multicrypto.wallet import DEFAULT_PATH, WalletFile
    except ModuleNotFoundError as error:
        if error.name == 'nacl':
            sys.exit(
                'multicrypto-gui requires PyNaCl, install it with: pip install "multicrypto[gui]"'
            )
        if error.name in ('tkinter', '_tkinter'):
            sys.exit(
                'multicrypto-gui requires tkinter, install it with the system package manager '
                '(e.g. python3-tk)'
            )
        raise
    root = tk.Tk()
    window = MainWindow(root, WalletFile(args.wallet or DEFAULT_PATH), args.auto_lock * 60)
    root.after_idle(window.start)
    root.mainloop()


if __name__ == '__main__':
    main()
