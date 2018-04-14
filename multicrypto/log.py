import logging
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
