import argparse
import json
import os

import pytest

from multicrypto.gui.settings import (
    apply_scale,
    check_scale,
    initial_scale,
    load_scale,
    load_show_testnets,
    save_scale,
    save_show_testnets,
)


def test_save_and_load_scale(tmp_path):
    path = str(tmp_path / 'dir' / 'gui.json')

    save_scale(path, 1.5)

    assert load_scale(path) == 1.5


def test_auto_scale_removes_value_and_keeps_other_settings(tmp_path):
    path = tmp_path / 'gui.json'
    path.write_text(json.dumps({'scale': 2, 'other': 'kept'}))

    save_scale(str(path), None)

    assert json.loads(path.read_text()) == {'other': 'kept'}
    assert load_scale(str(path)) is None


@pytest.mark.parametrize(
    'content', [None, 'not json', '[]', '{"scale": "big"}', '{"scale": 9}', '{"scale": true}']
)
def test_invalid_settings_give_auto_scale(tmp_path, content):
    path = tmp_path / 'gui.json'
    if content is not None:
        path.write_text(content)

    assert load_scale(str(path)) is None


def test_initial_scale_prefers_command_line(tmp_path):
    path = str(tmp_path / 'gui.json')
    save_scale(path, 2)

    assert initial_scale(1.25, path) == 1.25
    assert initial_scale(None, path) == 2


def test_apply_scale_sets_qt_scale_factor(monkeypatch):
    monkeypatch.delenv('QT_SCALE_FACTOR', raising=False)

    apply_scale(1.5)

    assert os.environ['QT_SCALE_FACTOR'] == '1.5'


def test_auto_scale_keeps_qt_scale_factor(monkeypatch):
    monkeypatch.setenv('QT_SCALE_FACTOR', '2')

    apply_scale(None)

    assert os.environ['QT_SCALE_FACTOR'] == '2'


def test_check_scale():
    assert check_scale('1.75') == 1.75
    for value in ('0.4', '4.5', 'nan', 'big'):
        with pytest.raises(argparse.ArgumentTypeError):
            check_scale(value)


def test_show_testnets_setting(tmp_path):
    path = str(tmp_path / 'gui.json')
    assert load_show_testnets(path) is False
    save_scale(path, 1.5)

    save_show_testnets(path, True)

    assert load_show_testnets(path) is True
    assert load_scale(path) == 1.5
