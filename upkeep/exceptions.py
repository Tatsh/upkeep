"""Exceptions."""
from __future__ import annotations

from .constants import MINIMUM_ESELECT_LINES

__all__ = ('KernelConfigMissing', 'KernelError', 'NoKernelToUpgradeTo', 'NoValueIsUnselected',
           'TooManyLinesFromEselect')


class KernelError(FileNotFoundError):
    """Generic Kernel-related error."""


class KernelConfigMissing(KernelError):
    """Raised when trying to build a kernel without a .config file present."""
    def __init__(self) -> None:
        super().__init__('Will not build without a .config file present.')


class NoKernelToUpgradeTo(KernelError):
    """Raised when there is no newer kernel version to upgrade to."""
    def __init__(self) -> None:
        super().__init__('No kernel to upgrade to.')


class TooManyLinesFromEselect(KernelError):
    """Raised when there are too many lines in the output from ``eselect kernel list``."""
    def __init__(self) -> None:
        super().__init__(f'Found more than {MINIMUM_ESELECT_LINES} lines in eselect output.')


class NoValueIsUnselected(KernelError):
    """Raised when no value is unselected in the output from ``eselect kernel list``."""
    def __init__(self) -> None:
        super().__init__('No value is unselected in eselect output.')
