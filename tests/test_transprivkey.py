import sys
from io import StringIO
from unittest.mock import patch

from multicrypto.commands.transprivkey import main


@patch.object(sys, 'argv', [
    'transprivkey', '-p', 'KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp', '-o', 'HUSH'])
@patch('sys.stdout', new_callable=StringIO)
def test_transprivkey_succes(sys_stdout):
    main()

    res = 'Private key: KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp' \
          ', compressed: True, address: t1gU3ts9oBgy4gtc3y9FmrgbSBrSStN1WK4, coin symbol: HUSH\n'
    assert sys_stdout.getvalue() == res
