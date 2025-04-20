# Easier Gentoo system maintenance

[![QA](https://github.com/Tatsh/upkeep/actions/workflows/qa.yml/badge.svg)](https://github.com/Tatsh/upkeep/actions/workflows/qa.yml)
[![Tests](https://github.com/Tatsh/upkeep/actions/workflows/tests.yml/badge.svg)](https://github.com/Tatsh/upkeep/actions/workflows/tests.yml)
[![Coverage Status](https://coveralls.io/repos/github/Tatsh/upkeep/badge.svg?branch=master)](https://coveralls.io/github/Tatsh/upkeep?branch=master)
[![Documentation Status](https://readthedocs.org/projects/upkeep/badge/?version=latest)](https://upkeep.readthedocs.org/?badge=latest)
[![PyPI - Version](https://img.shields.io/pypi/v/upkeep)](https://pypi.org/project/upkeep/)
[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/upkeep)](https://github.com/Tatsh/upkeep/tags)
[![License](https://img.shields.io/github/license/Tatsh/upkeep)](https://github.com/Tatsh/upkeep/blob/master/LICENSE.txt)
[![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/upkeep/v1.6.0/master)](https://github.com/Tatsh/upkeep/compare/v1.6.0...master)

This is a set of commands to simplify maintaining a Gentoo system.

## Installation

### Poetry

```shell
poetry add upkeep
```

### Pip

```shell
pip install upkeep
```

## esync

This command needs `eix` installed to fully function. It runs `eix-sync`. This
is intended for use as a cron job. I use it daily.

This command can run `layman -S` for you if you pass `-l` or `--run-layman`.

## emerges

This command will do the following:

- Update Portage
- Update `@world` with options `--with-bdeps=y`, `--update`, `--deep`,
  `--newuse`
- Update live installations of packages (`@live-rebuild`)
- Run `emerge @preserved-rebuild`
- Run `systemctl daemon-reexec` (if applicable)
- Update the kernel

There are flags to disable most parts of this functionality, such as
`--no-upgrade-kernel`. Pass `--help` to see all the options.

## Automatic kernel update process

Older versions of this tool supported various ways to update the kernel to boot from. However this
is better left to the configuration and hooks of `kernelinstall` which is invoked by `make install`.

The automatic kernel update will only work if there are 2 kernels displayed
with the command `eselect --brief kernel list`. The first one in the list must
be the active kernel. The second one is the one to upgrade to. After switching
to the new kernel, a `.config` must exist in `/usr/src/linux` or the command
will not run `make`. If the configuration exists at `/proc/config.gz` it will
be used.

If `emerges` fails to build the kernel because of the state of
`eselect kernel list`, you can fix it and re-run the update by running
`upgrade-kernel`.

The old kernel data in `/boot` will be stored in `/root/.upkeep/old-kernels`.

If you want to only rebuild the kernel, run `rebuild-kernel`.

## ecleans

This command will run the following commands (or equivalents):

- `emerge --depclean`
- `emerge @preserved-rebuild`
- `revdep-rebuild`
- `eclean-dist --deep`
- `rm -fR /var/tmp/portage/*`
