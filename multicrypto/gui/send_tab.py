"""Send tab: preparing, confirming and broadcasting transactions (sendcrypto)."""

import json
import tkinter as tk
from tkinter import ttk

from multicrypto.api import broadcast_prepared, prepare_from_private_keys
from multicrypto.coins import coins
from multicrypto.gui.dialogs import TextDialog, confirm
from multicrypto.gui.forms import (
    check_sources,
    describe_transaction,
    extract_txid,
    parse_address,
    parse_amount,
    parse_int,
    parse_nodes,
    parse_thresholds,
)
from multicrypto.gui.wallet_tab import create_entries_tree, show_entries
from multicrypto.network import broadcast_transaction

DEFAULT_FEE = 10000


class SendTab:
    def __init__(self, notebook, app):
        self.app = app
        self.frame = ttk.Frame(notebook, padding=8)
        ttk.Label(
            self.frame, text='From (one or more addresses with the same coin and address type)'
        ).pack(anchor='w')
        self.sources = create_entries_tree(self.frame, selectmode='extended', height=5)
        self.sources.pack(fill='both', expand=True, pady=(2, 8))
        form = ttk.Frame(self.frame)
        form.pack(fill='x')
        self.destination = self._add_row(form, 0, 'To address', width=74)
        self.amount = self._add_row(form, 1, 'Amount', width=20)
        self.fee = self._add_row(form, 2, 'Fee (satoshis)', width=20)
        self.fee.insert(0, str(DEFAULT_FEE))
        advanced = ttk.LabelFrame(self.frame, text='Advanced', padding=8)
        advanced.pack(fill='x', pady=8)
        self.minimum = self._add_row(advanced, 0, 'Minimum input (satoshis)', width=20)
        self.maximum = self._add_row(advanced, 1, 'Maximum input (satoshis)', width=20)
        self.limit = self._add_row(advanced, 2, 'Limit of inputs', width=20)
        self.p2p = tk.BooleanVar()
        ttk.Checkbutton(
            advanced, text='Send directly to the peer-to-peer network', variable=self.p2p
        ).grid(row=3, column=0, columnspan=2, sticky='w', pady=2)
        self.nodes = self._add_row(advanced, 4, 'Nodes host[:port] (optional)', width=74)
        self.button = ttk.Button(self.frame, text='Prepare transaction...', command=self.prepare)
        self.button.pack(anchor='e')

    @staticmethod
    def _add_row(parent, row: int, text: str, width: int) -> ttk.Entry:
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky='w', padx=(0, 8), pady=2)
        entry = ttk.Entry(parent, width=width)
        entry.grid(row=row, column=1, sticky='w', pady=2)
        return entry

    def refresh(self):
        show_entries(self.sources, self.app.wallet.entries)

    def clear(self):
        self.sources.delete(*self.sources.get_children())
        self.destination.delete(0, 'end')
        self.amount.delete(0, 'end')

    def select_source(self, entry):
        self.sources.selection_set([entry.id])
        self.app.notebook.select(self.frame)

    def prepare(self):
        try:
            entries = [self.app.wallet.get(item) for item in self.sources.selection()]
            coin_symbol, address_type = check_sources(entries)
            coin = coins[coin_symbol]
            if not coin.get('apis'):
                raise ValueError(f'No API has been defined for the coin {coin_symbol}')
            destination = parse_address(self.destination.get(), coin_symbol)
            satoshis = parse_amount(self.amount.get())
            fee = parse_int(self.fee.get(), 'Fee', minimum=0)
            minimum, maximum, limit = parse_thresholds(
                self.minimum.get(), self.maximum.get(), self.limit.get()
            )
            broadcast, target = self._get_broadcast(coin, coin_symbol)
        except ValueError as error:
            self.app.show_error(error)
            return
        wif_private_keys = [entry.wif for entry in entries]
        source_addresses = [entry.address for entry in entries]

        def prepare_transaction():
            return prepare_from_private_keys(
                coin=coin,
                wif_private_keys=wif_private_keys,
                input_addresses=None,
                unlocking_scripts=None,
                destination_address=destination,
                satoshis=satoshis,
                fee=fee,
                minimum_input_threshold=minimum,
                maximum_input_threshold=maximum,
                limit_inputs=limit,
                address_type=address_type,
            )

        self.button.state(['disabled'])
        self.app.worker.run(
            prepare_transaction,
            lambda prepared: self._confirm(
                coin, coin_symbol, prepared, source_addresses, broadcast, target
            ),
            self._failed,
        )

    def _get_broadcast(self, coin, coin_symbol: str):
        """Return function broadcasting the transaction (None for the API) and its description."""
        nodes_text = self.nodes.get()
        if not self.p2p.get() and not nodes_text.strip():
            return None, 'block explorer API'
        if 'network' not in coin:
            raise ValueError(f'No peer-to-peer network has been defined for the coin {coin_symbol}')
        nodes = parse_nodes(nodes_text, coin['network']['port'])

        def broadcast(raw_transaction):
            return json.dumps({'txid': broadcast_transaction(coin, raw_transaction, nodes)})

        return broadcast, 'peer-to-peer network'

    def _confirm(self, coin, coin_symbol, prepared, source_addresses, broadcast, target):
        self.button.state(['!disabled'])
        rows = describe_transaction(prepared, coin_symbol, source_addresses, target)
        if not confirm(self.frame, 'Confirm transaction', rows, 'Send'):
            return
        self.button.state(['disabled'])
        self.app.worker.run(
            lambda: extract_txid(broadcast_prepared(coin, prepared, broadcast)),
            self._sent,
            self._failed,
        )

    def _sent(self, txid: str):
        self.button.state(['!disabled'])
        self.amount.delete(0, 'end')
        TextDialog(self.frame, 'Transaction sent', 'Transaction id', txid, copy=True)

    def _failed(self, error):
        self.button.state(['!disabled'])
        self.app.show_error(error)
