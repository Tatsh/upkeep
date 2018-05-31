"""Module with Portage helper commands."""
from setuptools import setup

setup(
    name='pezu',
    version='0.0.1',
    author='Andrew Udvare',
    author_email='audvare@gmail.com',
    url='https://github.com/Tatsh/pezu',
    license='LICENSE.txt',
    description='Portage update helper scripts.',
    long_description=open('README.md').read(),
    py_modules=['pezu'],
    entry_points={
        'console_scripts': [
            'ecleans = pezu:ecleans',
            'emerges = pezu:emerges',
            'esync = pezu:esync',
            # 'rebuild-kernel = pezu:rebuild_kernel_command',
            # 'upgrade-kernel = pezu:upgrade_kernel_command',
        ]
    }
)
