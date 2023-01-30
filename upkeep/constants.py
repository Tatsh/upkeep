# SPDX-License-Identifier: MIT
from typing import Final, Mapping

__all__ = (
    'CONFIG_GZ',
    'DEFAULT_USER_CONFIG',
    'DISABLE_GETBINPKG_ENV_DICT',
    'GRUB_CFG',
    'INTEL_UC',
    'KERNEL_SOURCE_DIR',
    'OLD_KERNELS_DIR',
    'SPECIAL_ENV',
)

CONFIG_GZ: Final[str] = '/proc/config.gz'
DEFAULT_USER_CONFIG: Final[str] = '/etc/upkeeprc'
# --getbinpkg=n is broken when FEATURES=getbinpkg
# https://bugs.gentoo.org/759067
DISABLE_GETBINPKG_ENV_DICT: Final[Mapping[str,
                                          str]] = dict(FEATURES='-getbinpkg')
GRUB_CFG: Final[str] = '/boot/grub/grub.cfg'
INTEL_UC: Final[str] = '/boot/intel-uc.img'
KERNEL_SOURCE_DIR: Final[str] = '/usr/src/linux'
OLD_KERNELS_DIR: Final[str] = '/var/lib/upkeep/old-kernels'
SPECIAL_ENV: Final[tuple[str, ...]] = ('CONFIG_PROTECT', 'CONFIG_PROTECT_MASK',
                                       'FEATURES', 'HOME', 'LANG', 'MAKEOPTS',
                                       'PATH', 'SHELL', 'SSH_AGENT_PID',
                                       'SSH_AUTH_SOCK', 'TERM', 'USE')
