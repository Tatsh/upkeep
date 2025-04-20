from __future__ import annotations

__all__ = ('CONFIG_GZ', 'DEFAULT_USER_CONFIG', 'DISABLE_GETBINPKG_ENV_DICT', 'GRUB_CFG', 'INTEL_UC',
           'KERNEL_SOURCE_DIR', 'MINIMUM_ESELECT_LINES', 'OLD_KERNELS_DIR', 'SPECIAL_ENV')

CONFIG_GZ = '/proc/config.gz'
DEFAULT_USER_CONFIG = '/etc/upkeeprc'
# --getbinpkg=n is broken when FEATURES=getbinpkg
# https://bugs.gentoo.org/759067
DISABLE_GETBINPKG_ENV_DICT = {'FEATURES': '-getbinpkg'}
GRUB_CFG = '/boot/grub/grub.cfg'
INTEL_UC = '/boot/intel-uc.img'
KERNEL_SOURCE_DIR = '/usr/src/linux'
OLD_KERNELS_DIR = '/var/lib/upkeep/old-kernels'
SPECIAL_ENV = ('CONFIG_PROTECT', 'CONFIG_PROTECT_MASK', 'FEATURES', 'HOME', 'LANG', 'MAKEOPTS',
               'PATH', 'PORTAGE_COMPRESSION_COMMAND', 'SHELL', 'SSH_AGENT_PID', 'SSH_AUTH_SOCK',
               'TERM', 'USE')
MINIMUM_ESELECT_LINES = 2
