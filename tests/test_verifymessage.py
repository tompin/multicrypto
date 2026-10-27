import sys
from io import StringIO
from unittest.mock import patch

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
