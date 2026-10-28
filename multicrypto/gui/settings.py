"""Settings of the GUI kept in a JSON file, read before QApplication is created."""

import argparse
import json
import os
from typing import Optional

SETTINGS_PATH = os.path.join(os.path.expanduser('~'), '.multicrypto', 'gui.json')
MIN_SCALE = 0.5
MAX_SCALE = 4


def _valid_scale(scale) -> bool:
    return (
        isinstance(scale, (int, float))
        and not isinstance(scale, bool)
        and MIN_SCALE <= scale <= MAX_SCALE
    )


def _load(path: str) -> dict:
    try:
        with open(path) as file:
            settings = json.load(file)
    except (OSError, ValueError):
        return {}
    return settings if isinstance(settings, dict) else {}


def load_scale(path: str) -> Optional[float]:
    """Saved scale of the interface, None means the scale of the system."""
    scale = _load(path).get('scale')
    return scale if _valid_scale(scale) else None


def save_scale(path: str, scale: Optional[float]) -> None:
    settings = _load(path)
    if scale is None:
        settings.pop('scale', None)
    else:
        settings['scale'] = scale
    os.makedirs(os.path.dirname(os.path.abspath(path)), mode=0o700, exist_ok=True)
    with open(path, 'w') as file:
        json.dump(settings, file)


def initial_scale(cli_scale: Optional[float], path: str) -> Optional[float]:
    """The scale from the command line overrides the saved one."""
    return cli_scale if cli_scale is not None else load_scale(path)


def apply_scale(scale: Optional[float]) -> None:
    """Scale the whole interface, has to be called before QApplication is created."""
    if scale is not None:
        os.environ['QT_SCALE_FACTOR'] = str(scale)


def check_scale(value: str) -> float:
    try:
        scale = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{value} is an invalid number') from None
    if not _valid_scale(scale):
        raise argparse.ArgumentTypeError(f'Scale must be between {MIN_SCALE} and {MAX_SCALE}')
    return scale
