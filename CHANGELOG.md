# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.1/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `upkeep all` command. Runs `emerge --sync` (skip with `--no-sync`), then `emerges`, then
  `ecleans` (skip with `--no-clean`).
- `-d`/`--debug` is accepted on either side of the subcommand name, so `upkeep -d all` and
  `upkeep all -d` are equivalent.
- `upkeep --version` and `python -m upkeep`.
- `/etc/upkeeprc` is now read. It is TOML and supports `[emerge] extra_args`,
  `[ecleans] extra_purge_dirs`, and `[sync] pre`/`post` hook commands. The `--config` option
  previously existed but was ignored.
- `ecleans` now runs `eclean-pkg --deep` and `emaint --fix all`, and deletes zero-length files
  under `PKGDIR`.

### Changed

- **Breaking:** the separate `ecleans`, `emerges`, `rebuild-kernel`, and `upgrade-kernel`
  executables are replaced by subcommands of a single `upkeep` command. Replace `emerges` with
  `upkeep emerges`, and so on.
- `-v`/`--verbose` on `emerges` now only passes `--verbose` to `emerge`. Use `-d`/`--debug` for
  debug logging.
- `ecleans` purges `${PORTAGE_TMPDIR}/portage` as reported by `portageq` instead of the hardcoded
  `/var/tmp/portage`, and does so before the `emerge` steps rather than after.
- The kernel upgrade now selects the highest-numbered entry from `eselect kernel list` instead of
  refusing to act unless exactly two entries are present.

### Fixed

- `emerges --exclude` now passes the given atom to `emerge` unchanged. Previously the value was
  iterated character by character, producing one broken `--exclude=` argument per letter.
- `ecleans` evaluated its `/var/tmp/portage` glob at import time, so it deleted only what existed
  when the process started and missed everything the run itself created.
- `upgrade_kernel` consumed the `eselect kernel list` output generator twice. Depending on which
  entry was selected, the second pass saw a partially drained iterator and reported
  `NoValueIsUnselected` instead of the real state.
- `emerges` passes `--with-bdeps=y` to the `@world` update, which the README already documented.

### Removed

- `TooManyLinesFromEselect` exception and the `MINIMUM_ESELECT_LINES` constant.
- `DISABLE_GETBINPKG_ENV_DICT` constant. It was never referenced; set `FEATURES=-getbinpkg` in the
  environment instead, which `minenv()` passes through.

## [1.7.1] - 2026-05-02

### Removed

- Standalone PyInstaller binaries for Windows and macOS. Upkeep targets Gentoo Linux exclusively,
  so the binary release artefacts and the corresponding workflow have been dropped.

## [1.7.0] - 2026-04-26

### Added

- Logging output to commands.

### Removed

- `esync` command. Use `emerge --sync`.

## [1.6.0]

### Added

- Added support for managing the kernel booted by systemd-boot. Bootloader detection (GRUB or
  systemd-boot) is automatic.
- Added support for automatic signing of EFI binaries. To use this feature, `app-crypt/sbsigntools`
  must be installed and `/etc/upkeeprc` must exist with a format like the following:

  ```ini
  [systemd-boot]
  sign-key = my-db.key
  sign-cert = my-db.crt
  ```

- Added [documentation](https://upkeep.readthedocs.io/en/latest/) to all public functions and
  commands.
- Added help text to all command line arguments.

### Changed

- Improved `^C` (Ctrl+C) interruptions to be more user friendly.
- `ecleans` no longer ignores exit codes from the commands it executes.
- `upkeep.utils.rebuild_kernel` and `upgrade_kernel` functions raise more specific exceptions.

[unreleased]: https://github.com/Tatsh/upkeep/compare/v1.7.1...HEAD
[1.7.1]: https://github.com/Tatsh/upkeep/compare/v1.7.0...v1.7.1
[1.7.0]: https://github.com/Tatsh/upkeep/compare/v1.6.1...v1.7.0
[1.6.0]: https://github.com/Tatsh/upkeep/compare/v1.5.0...v1.6.0
