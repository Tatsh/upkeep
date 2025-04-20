from __future__ import annotations

from .constants import MINIMUM_ESELECT_LINES

__all__ = ('KernelConfigMissing', 'KernelError', 'NoKernelToUpgradeTo', 'NoValueIsUnselected',
           'TooManyLinesFromEselect')


class KernelError(FileNotFoundError):
    pass


class KernelConfigMissing(KernelError):
    def __init__(self) -> None:
        super().__init__('Will not build without a .config file present.')


class NoKernelToUpgradeTo(KernelError):
    def __init__(self) -> None:
        super().__init__('No kernel to upgrade to.')


class TooManyLinesFromEselect(KernelError):
    def __init__(self) -> None:
        super().__init__(f'Found more than {MINIMUM_ESELECT_LINES} lines in eselect output.')


class NoValueIsUnselected(KernelError):
    def __init__(self) -> None:
        super().__init__('No value is unselected in eselect output.')
