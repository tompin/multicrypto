from codecs import open
from os import path

from setuptools import setup, find_packages

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='multicrypto',
    version='0.1.4',
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
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    keywords='cryptocurrencies',
    packages=find_packages(exclude=['htmlcov', 'tests']),
    install_requires=['fastecdsa==1.6.1', 'pysha3==1.0.2'],
    entry_points={
        'console_scripts': [
            'transaddress=multicrypto.transaddress:main',
            'transprivkey=multicrypto.transprivkey:main',
            'genaddress=multicrypto.genaddress:main',
        ],
    },
)
