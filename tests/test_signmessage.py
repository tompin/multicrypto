import sys
from base64 import b64decode
from io import StringIO
from unittest.mock import patch

from multicrypto.coins import coins
from multicrypto.commands.signmessage import main
from multicrypto.ecdsa import verify_signature


@patch('sys.stdout', new_callable=StringIO)
def test_transaddress_succes(sys_stdout):
    sys.argv = [
        '',
        '-c',
        'BTC',
        '-pKzReaUKzSaGarrhFhjNMweTrpUx4gqX1KCMFSWJx9374kYNHpmSu',
        '-m',
        'Hello World!',
    ]

    main()

    assert (
        sys_stdout.getvalue()
        == 'H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=\n'
    )


@patch('sys.stdout', new_callable=StringIO)
def test_signmessage_p2wpkh(sys_stdout):
    message = 'Zażółć gęślą jaźń ' * 20
    sys.argv = [
        '',
        '-c',
        'BTC',
        '-p',
        'L4rK1yDtCWekvXuE6oXD9jCYfFNV2cWRpVuPLBcCU2z8TrisoyY1',
        '-t',
        'p2wpkh',
        '-m',
        message,
    ]

    main()

    signature = sys_stdout.getvalue().strip()
    assert b64decode(signature)[0] in range(39, 43)
    assert verify_signature(
        coins['BTC'], message, signature, 'bc1qngw83fg8dz0k749cg7k3emc7v98wy0c74dlrkd'
    )


@patch('sys.stdout', new_callable=StringIO)
def test_signmessage_address_type_not_supported(sys_stdout, caplog):
    sys.argv = [
        '',
        '-c',
        'DOGE',
        '-p',
        'L4rK1yDtCWekvXuE6oXD9jCYfFNV2cWRpVuPLBcCU2z8TrisoyY1',
        '-t',
        'p2wpkh',
        '-m',
        'Hello',
    ]

    main()

    assert sys_stdout.getvalue() == ''
    assert 'not supported for dogecoin' in caplog.text


# Example of personal_sign from the documentation of web3.py
ETH_PRIVATE_KEY = '0xb25c7db31feed9122727bf0939dc769a96564b2de4c4726d035b36ecf1e5b364'
ETH_SIGNATURE = (
    '0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb3'
    '3e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce1c'
)


@patch('sys.stdout', new_callable=StringIO)
def test_signmessage_ethereum(sys_stdout):
    sys.argv = ['', '-c', 'ETH', '-p', ETH_PRIVATE_KEY, '-m', 'I♥SF']

    main()

    assert sys_stdout.getvalue() == ETH_SIGNATURE + '\n'


@patch('sys.stdout', new_callable=StringIO)
def test_signmessage_ethereum_incorrect_private_key(sys_stdout, caplog):
    sys.argv = ['', '-c', 'ETH', '-m', 'Hi']
    sys.argv += ['-p', 'KzReaUKzSaGarrhFhjNMweTrpUx4gqX1KCMFSWJx9374kYNHpmSu']

    main()

    assert 'Ethereum private key must have 64 hexadecimal digits' in caplog.text
    assert sys_stdout.getvalue() == ''


@patch('sys.stdout', new_callable=StringIO)
def test_signmessage_ethereum_rejects_address_type(sys_stdout, caplog):
    sys.argv = ['', '-c', 'TETH', '-p', ETH_PRIVATE_KEY, '-m', 'Hi', '-t', 'p2wpkh']

    main()

    assert 'Ethereum addresses have no address types' in caplog.text
    assert sys_stdout.getvalue() == ''
