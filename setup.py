"""Module with Portage helper commands."""
from distutils.core import setup

setup(
    name='pezu',
    version='0.0.1',
    author='Andrew Udvare',
    author_email='audvare@gmail.com',
    url='https://github.com/Tatsh/pezu',
    license='LICENSE.txt',
    description='Portage update helper scripts.',
    long_description=open('README.md').read(),
    entry_points={
        'console_scripts': [
            'ecleans = pezu:ecleans',
            'emerges = pezu:emerges',
            'esync = pezu:esync',
        ]
    }
)
