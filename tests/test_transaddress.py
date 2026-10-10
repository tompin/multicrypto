import os
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from multicrypto.commands.transaddress import main


@patch('sys.stdout', new_callable=StringIO)
def test_transaddress_succes(sys_stdout, tmpdir):
    output_dir = tmpdir.strpath
    sys.argv = [
        '',
        '-a',
        '1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG',
        '-i',
        'BTC',
        '-o',
        'ZEC',
        '-d',
        output_dir,
    ]

    main()

    res = '1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG (BTC) -> t1UKo1hnsd2xMrUgviSDRsZLVKEZ3yU4Sxr (ZEC)\n'
    res += 'Address QR code was saved in directory {}\n'.format(output_dir)
    assert sys_stdout.getvalue() == res
    assert os.path.isfile(os.path.join(output_dir, 't1UKo1hnsd2xMrUgviSDRsZLVKEZ3yU4Sxr.png'))


def test_transaddress_bech32_not_supported():
    sys.argv = ['', '-a', 'bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4', '-i', 'BTC', '-o', 'LTC']

    with pytest.raises(ValueError, match='Translating bech32'):
        main()
