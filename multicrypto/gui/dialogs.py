"""Modal dialogs of the GUI."""

from tkinter import messagebox, simpledialog, ttk
from typing import List, Optional, Tuple

from multicrypto.gui.forms import check_password_confirmation

SECRET_DISPLAY_SECONDS = 30


class PasswordDialog(simpledialog.Dialog):
    """Ask for the password, the new password has to be entered twice."""

    def __init__(self, parent, title: str, prompt: str, new_password: bool = False):
        self.prompt = prompt
        self.new_password = new_password
        self.result: Optional[str] = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text=self.prompt).grid(row=0, column=0, sticky='w')
        self.password = ttk.Entry(master, show='*', width=40)
        self.password.grid(row=1, column=0, pady=(4, 8))
        if self.new_password:
            ttk.Label(master, text='Repeat the password').grid(row=2, column=0, sticky='w')
            self.confirmation = ttk.Entry(master, show='*', width=40)
            self.confirmation.grid(row=3, column=0, pady=(4, 8))
        return self.password

    def validate(self):
        password = self.password.get()
        try:
            if self.new_password:
                check_password_confirmation(password, self.confirmation.get())
            elif not password:
                raise ValueError('Enter the password')
        except ValueError as error:
            messagebox.showerror('Error', str(error), parent=self)
            return False
        self.result = password
        return True


def ask_password(parent, title: str, prompt: str, new_password: bool = False) -> Optional[str]:
    return PasswordDialog(parent, title, prompt, new_password).result


class ConfirmDialog(simpledialog.Dialog):
    """Show the rows and ask for confirmation. Cancel has the focus and Enter is not bound, so the
    action cannot be confirmed by accident."""

    def __init__(self, parent, title: str, rows: List[Tuple[str, str]], confirm_text: str):
        self.rows = rows
        self.confirm_text = confirm_text
        self.confirmed = False
        super().__init__(parent, title)

    def body(self, master):
        for row, (name, value) in enumerate(self.rows):
            ttk.Label(master, text=f'{name}:').grid(
                row=row, column=0, sticky='nw', padx=(0, 12), pady=2
            )
            ttk.Label(master, text=value).grid(row=row, column=1, sticky='w', pady=2)
        return None

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text=self.confirm_text, command=self.ok).pack(side='left', padx=5, pady=5)
        cancel = ttk.Button(box, text='Cancel', command=self.cancel)
        cancel.pack(side='left', padx=5, pady=5)
        self.bind('<Escape>', self.cancel)
        box.pack()
        self.initial_focus = cancel

    def apply(self):
        self.confirmed = True


def confirm(parent, title: str, rows: List[Tuple[str, str]], confirm_text: str) -> bool:
    return ConfirmDialog(parent, title, rows, confirm_text).confirmed


class TextDialog(simpledialog.Dialog):
    """Show the text in a read-only field, optionally with copy button and closed after timeout."""

    def __init__(
        self,
        parent,
        title: str,
        label: str,
        text: str,
        copy: bool = False,
        close_after: Optional[int] = None,
    ):
        self.label = label
        self.text = text
        self.copy = copy
        self.close_after = close_after
        self._close_job = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text=self.label).grid(row=0, column=0, sticky='w')
        entry = ttk.Entry(master, width=max(len(self.text) + 2, 40))
        entry.insert(0, self.text)
        entry.state(['readonly'])
        entry.grid(row=1, column=0, pady=4)
        if self.close_after:
            ttk.Label(master, text=f'The window closes in {self.close_after} seconds').grid(
                row=2, column=0, sticky='w'
            )
            self._close_job = self.after(self.close_after * 1000, self.cancel)
        return entry

    def buttonbox(self):
        box = ttk.Frame(self)
        if self.copy:
            ttk.Button(box, text='Copy', command=self._copy).pack(side='left', padx=5, pady=5)
        ttk.Button(box, text='Close', command=self.cancel).pack(side='left', padx=5, pady=5)
        self.bind('<Escape>', self.cancel)
        box.pack()

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.text)

    def destroy(self):
        if self._close_job:
            self.after_cancel(self._close_job)
            self._close_job = None
        super().destroy()
