import os
import sys
from io import StringIO
from unittest.mock import patch

from multicrypto.commands.transaddress import main


@patch('sys.stdout', new_callable=StringIO)
def test_transaddress_succes(sys_stdout, tmpdir):
    output_dir = tmpdir.strpath
    sys.argv = ['', '-a', '1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG', '-i', 'BTC', '-o', 'ZEC', '-d',
                output_dir]

    main()

    res = '1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG (BTC) -> t1UKo1hnsd2xMrUgviSDRsZLVKEZ3yU4Sxr (ZEC)\n'
    res += 'Address QR code was saved in directory {}\n'.format(output_dir)
    assert sys_stdout.getvalue() == res
    assert os.path.isfile(os.path.join(output_dir, 't1UKo1hnsd2xMrUgviSDRsZLVKEZ3yU4Sxr.png'))
