# Easier Gentoo system maintenance

<!-- WISWA-GENERATED-README:START -->

[![Python versions](https://img.shields.io/pypi/pyversions/upkeep.svg?color=blue&logo=python&logoColor=white)](https://www.python.org/)
[![PyPI - Version](https://img.shields.io/pypi/v/upkeep)](https://pypi.org/project/upkeep/)
[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/upkeep)](https://github.com/Tatsh/upkeep/tags)
[![License](https://img.shields.io/github/license/Tatsh/upkeep)](https://github.com/Tatsh/upkeep/blob/master/LICENSE.txt)
[![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/upkeep/v1.7.1/master)](https://github.com/Tatsh/upkeep/compare/v1.7.1...master)
[![CodeQL](https://github.com/Tatsh/upkeep/actions/workflows/codeql.yml/badge.svg)](https://github.com/Tatsh/upkeep/actions/workflows/codeql.yml)
[![QA](https://github.com/Tatsh/upkeep/actions/workflows/qa.yml/badge.svg)](https://github.com/Tatsh/upkeep/actions/workflows/qa.yml)
[![Tests](https://github.com/Tatsh/upkeep/actions/workflows/tests.yml/badge.svg)](https://github.com/Tatsh/upkeep/actions/workflows/tests.yml)
[![Coverage Status](https://coveralls.io/repos/github/Tatsh/upkeep/badge.svg?branch=master)](https://coveralls.io/github/Tatsh/upkeep?branch=master)
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-blue?logo=dependabot)](https://github.com/dependabot)
[![Documentation Status](https://readthedocs.org/projects/upkeep/badge/?version=latest)](https://upkeep.readthedocs.org/?badge=latest)
[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![uv](https://img.shields.io/badge/uv-261230?logo=astral)](https://docs.astral.sh/uv/)
[![pytest](https://img.shields.io/badge/pytest-zz?logo=Pytest&labelColor=black&color=black)](https://docs.pytest.org/en/stable/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Downloads](https://static.pepy.tech/badge/upkeep/month)](https://pepy.tech/project/upkeep)
[![Stargazers](https://img.shields.io/github/stars/Tatsh/upkeep?logo=github&style=flat)](https://github.com/Tatsh/upkeep/stargazers)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Tatsh/upkeep/master.svg)](https://results.pre-commit.ci/latest/github/Tatsh/upkeep/master)
[![Prettier](https://img.shields.io/badge/Prettier-black?logo=prettier)](https://prettier.io/)

[![@Tatsh](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpublic.api.bsky.app%2Fxrpc%2Fapp.bsky.actor.getProfile%2F%3Factor=did%3Aplc%3Auq42idtvuccnmtl57nsucz72&query=%24.followersCount&label=Follow+%40Tatsh&logo=bluesky&style=social)](https://bsky.app/profile/Tatsh.bsky.social)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Tatsh-black?logo=buymeacoffee)](https://buymeacoffee.com/Tatsh)
[![Libera.Chat](https://img.shields.io/badge/Libera.Chat-Tatsh-black?logo=liberadotchat)](irc://irc.libera.chat/Tatsh)
[![Mastodon Follow](https://img.shields.io/mastodon/follow/109370961877277568?domain=hostux.social&style=social)](https://hostux.social/@Tatsh)
[![Patreon](https://img.shields.io/badge/Patreon-Tatsh2-F96854?logo=patreon)](https://www.patreon.com/Tatsh2)

<!-- WISWA-GENERATED-README:STOP -->

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

## Commands

Everything lives under a single `upkeep` command:

| Command                 | Purpose                                                       |
| ----------------------- | ------------------------------------------------------------- |
| `upkeep all`            | Sync, update, and clean in one pass.                          |
| `upkeep emerges`        | Update Portage, `@world`, and the kernel.                     |
| `upkeep ecleans`        | Remove build leftovers, unused packages, and stale distfiles. |
| `upkeep upgrade-kernel` | Select the newest kernel and build it.                        |
| `upkeep rebuild-kernel` | Rebuild the currently selected kernel.                        |

`-d`/`--debug` enables debug logging and is accepted on either side of the subcommand name, so
`upkeep -d all` and `upkeep all -d` are equivalent. Pass `--help` to any subcommand to see its
options.

## all

A single command for a full maintenance pass:

- `emerge --sync`, wrapped by any configured hooks. Skip it with `--no-sync`.
- Everything `upkeep emerges` does, including the kernel upgrade.
- Everything `upkeep ecleans` does. Skip it with `--no-clean`.

```shell
upkeep all --no-sync
```

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

`eselect kernel list` sorts its entries by version, so the highest-numbered entry is the newest
kernel available. That entry is selected and built. If it is already selected there is nothing to
do. After switching to the new kernel, a `.config` must exist in `/usr/src/linux` or the command
will not run `make`. If the configuration exists at `/proc/config.gz` it will be used.

If `upkeep emerges` fails to build the kernel because of the state of
`eselect kernel list`, you can fix it and re-run the update by running
`upkeep upgrade-kernel`.

The old kernel data in `/boot` will be stored in `/root/.upkeep/old-kernels`.

If you want to only rebuild the kernel, run `upkeep rebuild-kernel`.

## Configuration

All commands read `/etc/upkeeprc` (override with `--config`). It is TOML and every table is
optional.

```toml
[emerge]
# Appended to the @world update.
extra_args = ['--backtrack=1000', '--keep-going', '--usepkg=n']

[ecleans]
# ${PORTAGE_TMPDIR}/portage is always purged and does not need to be listed.
extra_purge_dirs = ['/home/portage']

[sync]
post = ["git -C /root/overlay remote set-url origin git@github.com:user/overlay"]
pre = ['/usr/local/sbin/prepare-ssh-agent']
```

Sync hook entries are split with `shlex.split` and run directly, without a shell. They cannot
change the environment of the `upkeep` process itself, so anything that must export a variable
(an `ssh-agent` socket, for example) belongs in a wrapper script that sets the variable and then
runs `upkeep all`. The variables listed in `upkeep.constants.SPECIAL_ENV` — including
`SSH_AUTH_SOCK`, `FEATURES`, `MAKEOPTS`, and `USE` — are passed through from that environment, so
`FEATURES=-getbinpkg upkeep all` works as expected.

## ecleans

This command will run the following commands (or equivalents):

- Delete the contents of `${PORTAGE_TMPDIR}/portage` (queried from `portageq`, so it follows
  wherever you have actually pointed `PORTAGE_TMPDIR`) and any `extra_purge_dirs`
- `emerge --depclean`
- `emerge @preserved-rebuild`
- `revdep-rebuild`
- `eclean-dist --deep`
- `eclean-pkg --deep`
- `emaint --fix all`
- Delete zero-length files under `PKGDIR`
