import os
import sys
from io import StringIO
from unittest.mock import patch

from multicrypto.commands.transprivkey import main


@patch('sys.stdout', new_callable=StringIO)
def test_transprivkey_succes(sys_stdout, tmpdir):
    output_dir = tmpdir.strpath
    sys.argv = ['transprivkey', '-p', 'KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp', '-o',
                'ZEC', '-d', output_dir]

    main()

    res = 'Private key: KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp' \
          ', compressed: True, address: t1gU3ts9oBgy4gtc3y9FmrgbSBrSStN1WK4, coin symbol: ZEC\n' \
          'QR codes were saved in directory {}\n'.format(output_dir)
    assert sys_stdout.getvalue() == res
    assert os.path.isfile(os.path.join(output_dir, 't1gU3ts9oBgy4gtc3y9FmrgbSBrSStN1WK4.png'))
    assert os.path.isfile(
        os.path.join(output_dir, 't1gU3ts9oBgy4gtc3y9FmrgbSBrSStN1WK4_private_key.png'))
