"""Exceptions."""
from __future__ import annotations

__all__ = ('ConfigError', 'KernelConfigMissing', 'KernelError', 'NoKernelToUpgradeTo',
           'NoValueIsUnselected')


class ConfigError(ValueError):
    """Raised when the configuration file cannot be parsed."""
    def __init__(self, path: str) -> None:
        super().__init__(f'Invalid configuration in `{path}`.')


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


class NoValueIsUnselected(KernelError):
    """Raised when ``eselect kernel list`` lists no usable entries."""
    def __init__(self) -> None:
        super().__init__('No usable entries in eselect output.')
