import sys
from io import StringIO
from unittest.mock import patch

from multicrypto.commands.signmessage import main


@patch('sys.stdout', new_callable=StringIO)
def test_transaddress_succes(sys_stdout):
    sys.argv = [
        '',
        '-c',
        'BTC',
        '-p' 'KzReaUKzSaGarrhFhjNMweTrpUx4gqX1KCMFSWJx9374kYNHpmSu',
        '-m',
        'Hello World!',
    ]

    main()

    assert (
        sys_stdout.getvalue()
        == 'H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=\n'
    )
