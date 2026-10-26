"""Main window: wallet file handling, tabs and automatic locking."""

import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from multicrypto.gui.balance_tab import BalanceTab
from multicrypto.gui.dialogs import ask_password
from multicrypto.gui.forms import describe_error
from multicrypto.gui.send_tab import SendTab
from multicrypto.gui.wallet_tab import WalletTab
from multicrypto.gui.worker import Worker
from multicrypto.wallet import MIN_PASSWORD_LENGTH, Wallet, WalletFile

AUTO_LOCK_SECONDS = 5 * 60
WALLET_FILE_TYPES = [('multicrypto wallet', '*.mcw'), ('All files', '*')]


class MainWindow:
    def __init__(
        self, root: tk.Tk, wallet_file: WalletFile, auto_lock_seconds: int = AUTO_LOCK_SECONDS
    ):
        self.root = root
        self.wallet_file = wallet_file
        self.auto_lock_seconds = auto_lock_seconds
        self.wallet: Optional[Wallet] = None
        self.last_activity = time.monotonic()
        self.worker = Worker(root)
        root.title('multicrypto')
        root.minsize(800, 520)
        self._create_menu()
        self.status = tk.StringVar()
        ttk.Label(root, textvariable=self.status, anchor='w').pack(
            side='bottom', fill='x', padx=8, pady=(0, 6)
        )
        self.notebook = ttk.Notebook(root)
        self.wallet_tab = WalletTab(self.notebook, self)
        self.balance_tab = BalanceTab(self.notebook, self)
        self.send_tab = SendTab(self.notebook, self)
        self.tabs = (self.wallet_tab, self.balance_tab, self.send_tab)
        for tab, text in zip(self.tabs, ('Wallet', 'Balance', 'Send'), strict=True):
            self.notebook.add(tab.frame, text=text)
        self.locked_screen = ttk.Frame(root, padding=24)
        self.locked_message = tk.StringVar()
        ttk.Label(self.locked_screen, textvariable=self.locked_message).pack(pady=(40, 12))
        self.unlock_button = ttk.Button(self.locked_screen, text='Unlock...', command=self.unlock)
        self.unlock_button.pack(pady=4)
        ttk.Button(self.locked_screen, text='Create new wallet...', command=self.new_wallet).pack(
            pady=4
        )
        ttk.Button(self.locked_screen, text='Open wallet file...', command=self.open_wallet).pack(
            pady=4
        )
        for sequence in ('<KeyPress>', '<ButtonPress>', '<Motion>'):
            root.bind_all(sequence, self._touch, add='+')
        self._show_locked()
        self.tick()

    def _create_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label='New wallet...', command=self.new_wallet)
        file_menu.add_command(label='Open wallet...', command=self.open_wallet)
        file_menu.add_command(label='Change password...', command=self.change_password)
        file_menu.add_command(label='Lock', command=self.lock)
        file_menu.add_separator()
        file_menu.add_command(label='Quit', command=self.root.destroy)
        menubar.add_cascade(label='File', menu=file_menu)
        self.root.config(menu=menubar)

    def start(self):
        """Ask for the password when the wallet file exists."""
        if self.wallet_file.exists():
            self.unlock()

    def _touch(self, _event=None):
        self.last_activity = time.monotonic()

    def tick(self):
        """Update the status and lock the wallet after inactivity, called every second."""
        if self.wallet is not None:
            self._update_unlocked_status()
        self.root.after(1000, self.tick)

    def _update_unlocked_status(self):
        remaining = self.auto_lock_seconds - (time.monotonic() - self.last_activity)
        if remaining <= 0:
            self.lock()
        else:
            minutes, seconds = divmod(int(remaining), 60)
            self.status.set(
                f'{self.wallet_file.path} · unlocked · locks in {minutes}:{seconds:02d}'
            )

    def _show_locked(self):
        self.notebook.pack_forget()
        if self.wallet_file.exists():
            self.locked_message.set(f'Wallet {self.wallet_file.path} is locked')
            self.unlock_button.state(['!disabled'])
        else:
            self.locked_message.set(
                f'Wallet file {self.wallet_file.path} does not exist.\n'
                'Create a new wallet or open another wallet file.'
            )
            self.unlock_button.state(['disabled'])
        self.status.set(f'{self.wallet_file.path} · locked')
        self.locked_screen.pack(fill='both', expand=True)

    def show_wallet(self, wallet: Wallet):
        self.root.config(cursor='')
        self.wallet = wallet
        self._touch()
        self.locked_screen.pack_forget()
        self.notebook.pack(fill='both', expand=True, padx=8, pady=8)
        for tab in self.tabs:
            tab.refresh()
        self._update_unlocked_status()

    def lock(self):
        self.wallet_file.lock()
        self.wallet = None
        for tab in self.tabs:
            tab.clear()
        self._show_locked()

    def _derive_key(self, message: str, func, on_success):
        """Run operation deriving the key from the password (about a second) in background."""
        self.status.set(message)
        self.root.config(cursor='watch')

        def failed(error):
            self.root.config(cursor='')
            if self.wallet is None:
                self._show_locked()
            self.show_error(error)

        self.worker.run(func, on_success, failed)

    def unlock(self):
        password = ask_password(
            self.root, 'Unlock wallet', f'Password of the wallet {self.wallet_file.path}'
        )
        if password is not None:
            wallet_file = self.wallet_file
            self._derive_key('Unlocking...', lambda: wallet_file.unlock(password), self.show_wallet)

    def new_wallet(self):
        if self.wallet_file.exists():
            path = filedialog.asksaveasfilename(
                parent=self.root,
                title='New wallet file',
                initialdir=os.path.dirname(os.path.abspath(self.wallet_file.path)),
                initialfile='wallet.mcw',
                defaultextension='.mcw',
                filetypes=WALLET_FILE_TYPES,
            )
            if not path:
                return
        else:
            path = self.wallet_file.path
        password = ask_password(
            self.root,
            'New wallet',
            f'Password of the new wallet {path}\n(at least {MIN_PASSWORD_LENGTH} characters)',
            new_password=True,
        )
        if password is None:
            return
        self.lock()
        wallet_file = self.wallet_file = WalletFile(path)
        self._derive_key(
            'Creating wallet...', lambda: wallet_file.create(password), self.show_wallet
        )

    def open_wallet(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title='Open wallet file',
            initialdir=os.path.dirname(os.path.abspath(self.wallet_file.path)),
            filetypes=WALLET_FILE_TYPES,
        )
        if not path:
            return
        self.lock()
        self.wallet_file = WalletFile(path)
        self._show_locked()
        self.unlock()

    def change_password(self):
        if self.wallet is None:
            return
        old_password = ask_password(self.root, 'Change password', 'Current password')
        if old_password is None:
            return
        new_password = ask_password(
            self.root,
            'Change password',
            f'New password (at least {MIN_PASSWORD_LENGTH} characters)',
            new_password=True,
        )
        if new_password is None:
            return
        wallet_file = self.wallet_file
        self._derive_key(
            'Changing password...',
            lambda: wallet_file.change_password(old_password, new_password),
            self._password_changed,
        )

    def _password_changed(self, wallet: Wallet):
        self.show_wallet(wallet)
        messagebox.showinfo('Change password', 'The password has been changed', parent=self.root)

    def modify_wallet(self, change):
        """Apply the change to the wallet and save it, the change is reverted when saving fails."""
        entries = list(self.wallet.entries)
        result = change(self.wallet)
        try:
            self.wallet_file.save(self.wallet)
        except BaseException:
            self.wallet.entries = entries
            raise
        for tab in self.tabs:
            tab.refresh()
        return result

    def show_error(self, error: BaseException):
        messagebox.showerror('Error', describe_error(error), parent=self.root)
