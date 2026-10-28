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
