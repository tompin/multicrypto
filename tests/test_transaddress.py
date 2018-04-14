import sys
from io import StringIO
from unittest.mock import patch

from multicrypto.transaddress import main


@patch.object(sys, 'argv', [
    '', '-a', '1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG', '-i', 'BTC', '-o', 'HUSH'])
@patch('sys.stdout', new_callable=StringIO)
def test_transaddress_succes(sys_stdout):
    main()

    res = '1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG (BTC) -> t1UKo1hnsd2xMrUgviSDRsZLVKEZ3yU4Sxr (HUSH)\n'
    assert sys_stdout.getvalue() == res
