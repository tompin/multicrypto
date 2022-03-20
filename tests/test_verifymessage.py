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
