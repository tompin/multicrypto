"""Wallet tab: addresses of the wallet, adding and removing private keys."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Optional

from multicrypto.coins import coins, get_address_types
from multicrypto.ellipticcurve import secp256k1
from multicrypto.gui.dialogs import SECRET_DISPLAY_SECONDS, TextDialog, ask_password
from multicrypto.gui.forms import EXPECTED_ERRORS
from multicrypto.wallet import WalletEntry, check_entry, generate_wif

COLUMNS = (
    ('label', 'Label', 160),
    ('coin', 'Coin', 60),
    ('address_type', 'Type', 100),
    ('address', 'Address', 460),
)


def create_entries_tree(parent, selectmode: str, height: int = 10) -> ttk.Treeview:
    tree = ttk.Treeview(
        parent,
        columns=[name for name, _, _ in COLUMNS],
        show='headings',
        selectmode=selectmode,
        height=height,
    )
    for name, heading, width in COLUMNS:
        tree.heading(name, text=heading)
        tree.column(name, width=width, stretch=name == 'address')
    return tree


def show_entries(tree: ttk.Treeview, entries) -> None:
    """Replace rows of the tree with the entries, keeping selection of the remaining ones."""
    selection = tree.selection()
    tree.delete(*tree.get_children())
    for entry in entries:
        values = (entry.label, entry.coin, entry.address_type, entry.address)
        tree.insert('', 'end', iid=entry.id, values=values)
    tree.selection_set([item for item in selection if tree.exists(item)])


class EntryDialog(simpledialog.Dialog):
    """Add private key to the wallet, imported in WIF format or generated when the dialog opens,
    so the shown address is the one which will be saved."""

    def __init__(self, parent, title: str, submit, import_wif: bool):
        self.submit = submit  # function(label, coin_symbol, wif, address_type)
        self.import_wif = import_wif
        self.private_key = None if import_wif else secp256k1.gen_private_key()
        super().__init__(parent, title)

    def body(self, master):
        self.label = tk.StringVar()
        self.coin = tk.StringVar(value='BTC')
        self.address_type = tk.StringVar()
        self.wif = tk.StringVar()
        self.address = tk.StringVar()
        ttk.Label(master, text='Label').grid(row=0, column=0, sticky='w', padx=(0, 8))
        label_entry = ttk.Entry(master, textvariable=self.label, width=40)
        label_entry.grid(row=0, column=1, sticky='w', pady=2)
        ttk.Label(master, text='Coin').grid(row=1, column=0, sticky='w', padx=(0, 8))
        ttk.Combobox(
            master, textvariable=self.coin, values=sorted(coins), state='readonly', width=10
        ).grid(row=1, column=1, sticky='w', pady=2)
        ttk.Label(master, text='Address type').grid(row=2, column=0, sticky='w', padx=(0, 8))
        self.type_box = ttk.Combobox(
            master, textvariable=self.address_type, state='readonly', width=14
        )
        self.type_box.grid(row=2, column=1, sticky='w', pady=2)
        if self.import_wif:
            ttk.Label(master, text='Private key (WIF)').grid(row=3, column=0, sticky='w')
            ttk.Entry(master, textvariable=self.wif, show='•', width=60).grid(
                row=3, column=1, sticky='w', pady=2
            )
        ttk.Label(master, text='Address').grid(row=4, column=0, sticky='w', padx=(0, 8))
        ttk.Label(master, textvariable=self.address).grid(row=4, column=1, sticky='w', pady=2)
        self.coin.trace_add('write', self._coin_changed)
        self.address_type.trace_add('write', self._update_address)
        self.wif.trace_add('write', self._update_address)
        self._coin_changed()
        return label_entry

    def _get_wif(self) -> str:
        if self.import_wif:
            return self.wif.get().strip()
        # the same private key in the WIF format of the selected coin
        return generate_wif(self.coin.get(), self.private_key)

    def _coin_changed(self, *_args):
        address_types = get_address_types(coins[self.coin.get()])
        self.type_box['values'] = address_types
        if self.address_type.get() in address_types:
            self._update_address()
        else:
            self.address_type.set(address_types[0])  # calls _update_address

    def _update_address(self, *_args):
        if self.import_wif and not self.wif.get().strip():
            self.address.set('')
            return
        try:
            self.address.set(check_entry(self.coin.get(), self._get_wif(), self.address_type.get()))
        except ValueError as error:
            self.address.set(f'({error})')

    def validate(self):
        label = self.label.get().strip()
        try:
            if not label:
                raise ValueError('Enter the label')
            self.submit(label, self.coin.get(), self._get_wif(), self.address_type.get())
        except EXPECTED_ERRORS as error:
            messagebox.showerror('Error', str(error), parent=self)
            return False
        return True


class WalletTab:
    def __init__(self, notebook, app):
        self.app = app
        self.frame = ttk.Frame(notebook, padding=8)
        buttons = ttk.Frame(self.frame)
        for text, command in (
            ('Import WIF…', self.import_wif),
            ('Generate new…', self.generate),
            ('Copy address', self.copy_address),
            ('Show WIF…', self.show_wif),
            ('Remove…', self.remove),
        ):
            ttk.Button(buttons, text=text, command=command).pack(side='left', padx=(0, 6))
        buttons.pack(side='bottom', fill='x', pady=(8, 0))
        self.tree = create_entries_tree(self.frame, selectmode='browse')
        scrollbar = ttk.Scrollbar(self.frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.menu = tk.Menu(self.frame, tearoff=False)
        self.menu.add_command(label='Copy address', command=self.copy_address)
        self.menu.add_command(
            label='Check balance', command=lambda: self._with_selected(app.balance_tab.check_entry)
        )
        self.menu.add_command(
            label='Send from this address',
            command=lambda: self._with_selected(app.send_tab.select_source),
        )
        self.tree.bind('<Button-3>', self._show_menu)

    def refresh(self):
        show_entries(self.tree, self.app.wallet.entries)

    def clear(self):
        self.tree.delete(*self.tree.get_children())

    def selected_entry(self) -> Optional[WalletEntry]:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo('Wallet', 'Select an address first', parent=self.frame)
            return None
        return self.app.wallet.get(selection[0])

    def _with_selected(self, action):
        entry = self.selected_entry()
        if entry:
            action(entry)

    def _show_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.menu.tk_popup(event.x_root, event.y_root)

    def import_wif(self):
        EntryDialog(self.frame, 'Import private key', self._add, import_wif=True)

    def generate(self):
        EntryDialog(self.frame, 'Generate new private key', self._add, import_wif=False)

    def _add(self, label, coin_symbol, wif, address_type):
        self.app.modify_wallet(lambda wallet: wallet.add_wif(label, coin_symbol, wif, address_type))

    def copy_address(self):
        entry = self.selected_entry()
        if entry:
            self.frame.clipboard_clear()
            self.frame.clipboard_append(entry.address)

    def show_wif(self):
        entry = self.selected_entry()
        if not entry:
            return
        password = ask_password(
            self.frame,
            'Show private key',
            f'Enter the wallet password to show the private key of "{entry.label}"',
        )
        if password is None:
            return
        self.app.worker.run(
            lambda: self.app.wallet_file.verify_password(password),
            lambda correct: self._show_wif(entry, correct),
            self.app.show_error,
        )

    def _show_wif(self, entry: WalletEntry, correct: bool):
        if not correct:
            messagebox.showerror('Error', 'Wrong password', parent=self.frame)
            return
        TextDialog(
            self.frame,
            f'Private key of "{entry.label}"',
            f'{entry.coin} {entry.address_type} {entry.address}',
            entry.wif,
            close_after=SECRET_DISPLAY_SECONDS,
        )

    def remove(self):
        entry = self.selected_entry()
        if not entry or not messagebox.askyesno(
            'Remove address',
            f'Remove "{entry.label}" ({entry.address})?\n\n'
            'The private key will be permanently deleted from the wallet file. '
            'Make sure you have its backup.',
            icon='warning',
            default='no',
            parent=self.frame,
        ):
            return
        try:
            self.app.modify_wallet(lambda wallet: wallet.remove(entry.id))
        except EXPECTED_ERRORS as error:
            self.app.show_error(error)
