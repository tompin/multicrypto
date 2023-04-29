from codecs import open
from os import path

from setuptools import setup, find_packages

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='multicrypto',
    version='0.1.17',
    description='Tool for translating and creating custom addresses for various cryptocurrencies',
    long_description=long_description,
    long_description_content_type='text/markdown',
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
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    keywords='cryptocurrency, address, transaction',
    packages=find_packages(exclude=['htmlcov', 'tests']),
    install_requires=['pypng==0.0.21', 'PyQRCode==1.2.1', 'pycryptodome==3.17', 'requests==2.27.1'],
    entry_points={
        'console_scripts': [
            'checkaddress=multicrypto.commands.checkaddress:main',
            'genaddress=multicrypto.commands.genaddress:main',
            'sendcrypto=multicrypto.commands.sendcrypto:main',
            'signmessage=multicrypto.commands.signmessage:main',
            'sweepaddress=multicrypto.commands.sweepaddress:main',
            'transaddress=multicrypto.commands.transaddress:main',
            'transprivkey=multicrypto.commands.transprivkey:main',
            'verifymessage=multicrypto.commands.verifymessage:main',
        ],
    },
)
