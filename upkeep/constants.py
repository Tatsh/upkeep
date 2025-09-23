"""Shared constants."""
from __future__ import annotations

__all__ = ('CONFIG_GZ', 'DEFAULT_USER_CONFIG', 'DISABLE_GETBINPKG_ENV_DICT', 'GRUB_CFG', 'INTEL_UC',
           'KERNEL_SOURCE_DIR', 'MINIMUM_ESELECT_LINES', 'OLD_KERNELS_DIR', 'SPECIAL_ENV')

CONFIG_GZ = '/proc/config.gz'
"""Path to the compressed kernel configuration file."""
DEFAULT_USER_CONFIG = '/etc/upkeeprc'
"""Default user configuration file path."""
# --getbinpkg=n is broken when FEATURES=getbinpkg
# https://bugs.gentoo.org/759067
DISABLE_GETBINPKG_ENV_DICT = {'FEATURES': '-getbinpkg'}
"""Environment dictionary to disable getbinpkg."""
GRUB_CFG = '/boot/grub/grub.cfg'
"""GRUB configuration file path."""
INTEL_UC = '/boot/intel-uc.img'
"""Intel microcode update image path."""
KERNEL_SOURCE_DIR = '/usr/src/linux'
"""Kernel source directory path."""
OLD_KERNELS_DIR = '/var/lib/upkeep/old-kernels'
"""Directory to store old kernels in."""
SPECIAL_ENV = ('CONFIG_PROTECT', 'CONFIG_PROTECT_MASK', 'FEATURES', 'HOME', 'LANG', 'MAKEOPTS',
               'PATH', 'PORTAGE_COMPRESSION_COMMAND', 'SHELL', 'SSH_AGENT_PID', 'SSH_AUTH_SOCK',
               'TERM', 'USE')
"""Environment variables to preserve when running commands."""
MINIMUM_ESELECT_LINES = 2
"""Minimum number of lines expected from ``eselect kernel list`` output."""
