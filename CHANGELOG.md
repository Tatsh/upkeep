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

* `ecleans` no longer ignores exit codes from the commands it executes.
* Improved `^C` (Ctrl+C) interruptions to be more user friendly.
* Added [documentation](https://upkeep.readthedocs.io/en/latest/) to all public
  functions and commands.
* Added help text to all command line arguments.
