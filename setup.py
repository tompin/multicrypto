from codecs import open
from os import path

from setuptools import setup, find_packages

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='multicrypto',
    version='0.1.10',
    description='Tool for translating and creating custom addresses for various cryptocurrencies',
    long_description=long_description,
    author='tompin',
    author_email='tompin@tuta.io',
    url='https://github.com/tompin/multicrypto',
    license='http://opensource.org/licenses/MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Security :: Cryptography',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    keywords='cryptocurrency, address, transaction',
    packages=find_packages(exclude=['htmlcov', 'tests']),
    install_requires=['fastecdsa==1.6.1', 'pysha3==1.0.2', 'Pillow==5.1.0', 'qrcode==6.0'],
    entry_points={
        'console_scripts': [
            'transaddress=multicrypto.commands.transaddress:main',
            'transprivkey=multicrypto.commands.transprivkey:main',
            'genaddress=multicrypto.commands.genaddress:main',
            'sendcrypto=multicrypto.commands.sendcrypto:main',
            'checkaddress=multicrypto.commands.checkaddress:main',
            'sweepaddress=multicrypto.commands.sweepaddress:main',
        ],
    },
)
