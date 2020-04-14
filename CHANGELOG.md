# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

* Added support for managing the kernel booted by systemd-boot. Bootloader
  detection (GRUB or systemd-boot) is automatic.
* Added support for onfiguration file at `/etc/upkeeprc`. Currently only used
  for signing EFI executables for use with Secure boot, only when systemd-boot
  is detected as the system's bootloader.
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
