"""Typing helpers."""
from __future__ import annotations

from typing import TypedDict

__all__ = ('EcleansConfig', 'EmergeConfig', 'SyncConfig', 'UpkeepConfig')


class EcleansConfig(TypedDict, total=False):
    """Configuration for the ``ecleans`` command."""

    extra_purge_dirs: list[str]
    """
    Directories whose contents are deleted in addition to Portage's build directory.

    Portage's own build directory (``${PORTAGE_TMPDIR}/portage``) is always purged and does not
    need to be listed here.
    """


class EmergeConfig(TypedDict, total=False):
    """Configuration for ``emerge`` invocations."""

    extra_args: list[str]
    """Additional arguments appended to the ``@world`` update."""


class SyncConfig(TypedDict, total=False):
    """Configuration for the repository sync step of ``do-everything``."""

    post: list[str]
    """Commands run after ``emerge --sync``. Each entry is split with :py:func:`shlex.split`."""
    pre: list[str]
    """Commands run before ``emerge --sync``. Each entry is split with :py:func:`shlex.split`."""


class UpkeepConfig(TypedDict, total=False):
    """Top-level contents of the configuration file."""

    ecleans: EcleansConfig
    """The ``[ecleans]`` table."""
    emerge: EmergeConfig
    """The ``[emerge]`` table."""
    sync: SyncConfig
    """The ``[sync]`` table."""
