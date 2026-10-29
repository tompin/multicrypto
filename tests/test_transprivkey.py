import os
import sys
from io import StringIO
from unittest.mock import patch

from multicrypto.commands.transprivkey import main


@patch('sys.stdout', new_callable=StringIO)
def test_transprivkey_succes(sys_stdout, tmpdir):
    output_dir = tmpdir.strpath
    sys.argv = [
        'transprivkey',
        '-p',
        'KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp',
        '-o',
        'DOGE',
        '-d',
        output_dir,
    ]

    main()

    res = (
        'Private key: QNcdNChp1UfHrCNLTmGsRDcLKw1JN4aTTu34FdofZGJ5QHT5dNJV'
        ', compressed: True, address: DTjYRngJWn5kdFjkmJSDGdf7pKyfUnVnGg, coin symbol: DOGE\n'
        'QR codes were saved in directory {}\n'.format(output_dir)
    )
    assert sys_stdout.getvalue() == res
    assert os.path.isfile(os.path.join(output_dir, 'DTjYRngJWn5kdFjkmJSDGdf7pKyfUnVnGg.png'))
    assert os.path.isfile(
        os.path.join(output_dir, 'DTjYRngJWn5kdFjkmJSDGdf7pKyfUnVnGg_private_key.png')
    )


KEY_1_WIF = 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn'  # private key 1, compressed


@patch('sys.stdout', new_callable=StringIO)
def test_transprivkey_without_output_symbol_returns_integer(sys_stdout):
    sys.argv = ['transprivkey', '-p', KEY_1_WIF]

    main()

    assert sys_stdout.getvalue() == (
        'Private key: 1, compressed: True, address: , coin symbol: None\n'
    )


@patch('sys.stdout', new_callable=StringIO)
def test_transprivkey_to_ethereum(sys_stdout):
    sys.argv = ['transprivkey', '-p', KEY_1_WIF, '-o', 'eth']

    main()

    assert sys_stdout.getvalue() == (
        f'Private key: 0x{"00" * 31}01, compressed: True, '
        'address: 0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf, coin symbol: ETH\n'
    )


@patch('sys.stdout', new_callable=StringIO)
def test_transprivkey_ethereum_private_key_to_bitcoin(sys_stdout):
    sys.argv = ['transprivkey', '-p', f'0x{"00" * 31}01', '-i', '-o', 'BTC']

    main()

    assert sys_stdout.getvalue() == (
        f'Private key: {KEY_1_WIF}, compressed: True, '
        'address: 1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH, coin symbol: BTC\n'
    )
