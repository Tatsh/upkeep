# SPDX-License-Identifier: MIT
__all__ = ('KernelConfigMissing', 'KernelError')


class KernelError(FileNotFoundError):
    pass


class KernelConfigMissing(KernelError):
    def __init__(self) -> None:
        super().__init__('Will not build without a .config file present')
