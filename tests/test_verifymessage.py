import sys
from io import StringIO
from unittest.mock import patch

import pytest

from multicrypto.commands.verifymessage import main


@patch('sys.stdout', new_callable=StringIO)
def test_transaddress_succes(sys_stdout):
    sys.argv = [
        '',
        '-c',
        'BTC',
        '-a',
        '1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi',
        '-m',
        'Hello World!',
        '-s',
        'H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=',
    ]

    main()

    assert sys_stdout.getvalue() == 'True\n'


@patch('sys.stdout', new_callable=StringIO)
def test_verifymessage_p2wpkh(sys_stdout):
    sys.argv = [
        '',
        '-c',
        'BTC',
        '-a',
        'bc1qngw83fg8dz0k749cg7k3emc7v98wy0c74dlrkd',
        '-m',
        'This is an example of a signed message.',
        '-s',
        'J9L5yLFjti0QTHhPyFrZCT1V/MMnBtXKmoiKDZ78NDBjERki6ZTQZdSMCtkgoNmp17By9ItJr8o7ChX0XxY91nk=',
    ]

    main()

    assert sys_stdout.getvalue() == 'True\n'


@patch('sys.stdout', new_callable=StringIO)
def test_verifymessage_incorrect_signature(sys_stdout, caplog):
    sys.argv = [
        '',
        '-c',
        'BTC',
        '-a',
        '1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi',
        '-m',
        'Hi',
        '-s',
        'abc',
    ]

    main()

    assert sys_stdout.getvalue() == ''
    assert 'Signature is not correct base64' in caplog.text


ETH_ADDRESS = '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'
ETH_SIGNATURE = (
    '0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb3'
    '3e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce1c'
)


@pytest.mark.parametrize('message, valid', [('I♥SF', 'True'), ('I♥NY', 'False')])
@patch('sys.stdout', new_callable=StringIO)
def test_verifymessage_ethereum(sys_stdout, message, valid):
    sys.argv = ['', '-c', 'ETH', '-a', ETH_ADDRESS.lower(), '-m', message, '-s', ETH_SIGNATURE]

    main()

    assert sys_stdout.getvalue() == valid + '\n'


@patch('sys.stdout', new_callable=StringIO)
def test_verifymessage_ethereum_incorrect_signature(sys_stdout, caplog):
    sys.argv = ['', '-c', 'ETH', '-a', ETH_ADDRESS, '-m', 'Hi', '-s', '0x1234']

    main()

    assert 'Signature must have 65 bytes, it has 2' in caplog.text
    assert sys_stdout.getvalue() == ''
