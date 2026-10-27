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
