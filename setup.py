# SPDX-License-Identifier: MIT
"""Module with Portage helper commands."""
import subprocess as sp

from setuptools import Command, setup


class BuildDocumentationCommand(Command):
    """A custom command to generate documentation with Sphinx."""

    description = 'Generate documentation.'
    user_options = [('type=', 'M', 'type of documentation')]

    # pylint: disable=attribute-defined-outside-init
    def initialize_options(self) -> None:
        self.type = 'help'
        # pylint: enable=attribute-defined-outside-init

    def finalize_options(self) -> None:
        pass

    def run(self) -> None:
        sp.run(('sphinx-build', '-M', self.type, 'docs', 'build'), check=True)


ENTRY_POINTS = {
    'console_scripts': (
        'ecleans = upkeep:ecleans',
        'emerges = upkeep:emerges',
        'esync = upkeep:esync',
        'rebuild-kernel = upkeep:rebuild_kernel_command',
        'upgrade-kernel = upkeep:upgrade_kernel_command',
    ),
}
EXTRAS_REQUIRE = {
    'dev': [
        'mypy',
        'mypy-extensions',
        'pylint',
        'rope',
    ],
    'docs': ['sphinx'],
    'testing': [
        # 'mock',
        'pytest',
        'pytest-cov',
        # 'pytest-mock',
    ]
}

with open('README.md') as f:
    setup(
        author='Andrew Udvare',
        author_email='audvare@gmail.com',
        cmdclass={'build_docs': BuildDocumentationCommand},
        description='Portage update helper scripts.',
        entry_points=ENTRY_POINTS,
        extras_require=EXTRAS_REQUIRE,
        license='LICENSE.txt',
        long_description=f.read(),
        long_description_content_type='text/markdown',
        name='upkeep',
        py_modules=['upkeep'],
        python_requires='>=3.9',
        test_suite='tests',
        tests_require=('coveralls', 'pytest', 'pytest-cov', 'pytest-mock'),
        url='https://github.com/Tatsh/upkeep',
        version='1.3.1',
    )
