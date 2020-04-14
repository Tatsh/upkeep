# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

* Added support for managing the kernel booted by systemd-boot. Bootloader
  detection (GRUB or systemd-boot) is automatic.
* Added support for automatic signing of EFI binaries. To use this feature,
  `app-crypt/sbsigntools` must be installed and `/etc/upkeeprc` must exist with
  a format like the following:

  ```ini
  [systemd-boot]
  sign-key = my-db.key
  sign-cert = my-db.crt
  ```

* Added experimental `-H` or `--split-heavy` option to `emerges`. This will
  cause `emerges` to attempt to build *heavier* packages like Chromium
  after the leaner packages are built. This may cause issues if there are two
  heavy packages that are also dependent on each other. Currently, these
  packages are considered *heavy*:
  * `app-office/libreoffice`
  * `dev-java/icedtea`
  * `dev-qt/qtwebengine`
  * `dev-qt/qtwebkit`
  * `kde-frameworks/kdewebkit`
  * `mail-client/thunderbird`
  * `net-libs/webkit-gtk`
  * `sys-devel/clang`
  * `sys-devel/gcc`
  * `sys-devel/llvm`
  * `www-client/chromium`
  * `www-client/firefox`
* `ecleans` no longer ignores exit codes from the commands it executes.
* Improved `^C` (Ctrl+C) interruptions to be more user friendly.
* Added [documentation](https://upkeep.readthedocs.io/en/latest/) to all public
  functions and commands.
* Added help text to all command line arguments.
