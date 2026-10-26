"""Balance tab: unspent outputs of the wallet address or any other address (checkaddress)."""

import tkinter as tk
from argparse import Namespace
from tkinter import ttk

from multicrypto.commands.checkaddress import check_address
from multicrypto.gui.forms import (
    coins_with_api,
    entry_description,
    format_amount,
    parse_address,
    parse_thresholds,
)

UTXO_COLUMNS = (
    ('txid', 'Transaction id', 470),
    ('confirmations', 'Confirmations', 100),
    ('satoshis', 'Satoshis', 130),
    ('amount', 'Amount', 130),
)


class BalanceTab:
    def __init__(self, notebook, app):
        self.app = app
        self.entries = []
        self.frame = ttk.Frame(notebook, padding=8)
        source = ttk.Frame(self.frame)
        source.pack(fill='x')
        self.source = tk.StringVar(value='wallet')
        ttk.Radiobutton(source, text='Wallet address', variable=self.source, value='wallet').grid(
            row=0, column=0, sticky='w'
        )
        self.entry_box = ttk.Combobox(source, state='readonly', width=90)
        self.entry_box.grid(row=0, column=1, columnspan=2, sticky='we', pady=2)
        self.entry_box.bind('<<ComboboxSelected>>', lambda _event: self.source.set('wallet'))
        ttk.Radiobutton(source, text='Other address', variable=self.source, value='other').grid(
            row=1, column=0, sticky='w'
        )
        self.coin = ttk.Combobox(source, values=coins_with_api(), state='readonly', width=8)
        self.coin.set('BTC')
        self.coin.grid(row=1, column=1, sticky='w', pady=2)
        self.address = ttk.Entry(source, width=74)
        self.address.grid(row=1, column=2, sticky='we', pady=2)
        self.address.bind('<FocusIn>', lambda _event: self.source.set('other'))
        filters = ttk.Frame(self.frame)
        filters.pack(fill='x', pady=(4, 8))
        self.minimum = self._add_field(filters, 'Minimum input (satoshis)')
        self.maximum = self._add_field(filters, 'Maximum input (satoshis)')
        self.limit = self._add_field(filters, 'Limit of inputs')
        self.button = ttk.Button(filters, text='Check', command=self.check)
        self.button.pack(side='right')
        self.total = tk.StringVar()
        ttk.Label(self.frame, textvariable=self.total).pack(side='bottom', anchor='e', pady=(4, 0))
        self.tree = ttk.Treeview(
            self.frame, columns=[name for name, _, _ in UTXO_COLUMNS], show='headings'
        )
        for name, heading, width in UTXO_COLUMNS:
            self.tree.heading(name, text=heading)
            self.tree.column(
                name, width=width, stretch=name == 'txid', anchor='w' if name == 'txid' else 'e'
            )
        self.tree.pack(fill='both', expand=True)

    @staticmethod
    def _add_field(parent, text: str) -> ttk.Entry:
        ttk.Label(parent, text=text).pack(side='left')
        entry = ttk.Entry(parent, width=12)
        entry.pack(side='left', padx=(4, 12))
        return entry

    def refresh(self):
        index = self.entry_box.current()
        selected = self.entries[index].id if 0 <= index < len(self.entries) else None
        self.entries = list(self.app.wallet.entries)
        self.entry_box['values'] = [entry_description(entry) for entry in self.entries]
        ids = [entry.id for entry in self.entries]
        if selected in ids:
            self.entry_box.current(ids.index(selected))
        elif self.entries:
            self.entry_box.current(0)
        else:
            self.entry_box.set('')

    def clear(self):
        self.entries = []
        self.entry_box.set('')
        self.entry_box['values'] = []
        self.tree.delete(*self.tree.get_children())
        self.total.set('')

    def check_entry(self, entry):
        self.entry_box.current([item.id for item in self.entries].index(entry.id))
        self.source.set('wallet')
        self.app.notebook.select(self.frame)
        self.check()

    def check(self):
        try:
            coin_symbol, address = self._get_address()
            minimum, maximum, limit = parse_thresholds(
                self.minimum.get(), self.maximum.get(), self.limit.get()
            )
        except ValueError as error:
            self.app.show_error(error)
            return
        args = Namespace(
            coin_symbol=coin_symbol,
            address=address,
            minimum_input_threshold=minimum,
            maximum_input_threshold=maximum,
            limit_inputs=limit,
        )
        self.button.state(['disabled'])
        self.app.worker.run(
            lambda: check_address(args), lambda utxos: self._show(utxos, coin_symbol), self._failed
        )

    def _get_address(self):
        if self.source.get() == 'wallet':
            index = self.entry_box.current()
            if index < 0:
                raise ValueError('Select the wallet address')
            entry = self.entries[index]
            return entry.coin, entry.address
        coin_symbol = self.coin.get()
        return coin_symbol, parse_address(self.address.get(), coin_symbol)

    def _show(self, utxos, coin_symbol: str):
        self.button.state(['!disabled'])
        self.tree.delete(*self.tree.get_children())
        for utxo in utxos:
            self.tree.insert(
                '',
                'end',
                values=(
                    utxo['txid'],
                    utxo['confirmations'],
                    utxo['satoshis'],
                    format_amount(utxo['satoshis']),
                ),
            )
        total = sum(utxo['satoshis'] for utxo in utxos)
        self.total.set(
            f'{len(utxos)} inputs, total {format_amount(total)} {coin_symbol} ({total} satoshis)'
        )

    def _failed(self, error):
        self.button.state(['!disabled'])
        self.app.show_error(error)
