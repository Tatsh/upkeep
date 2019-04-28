# Easier Gentoo system maintenance

This is a set of commands to simplify maintaining a Gentoo system.

## esync

This command needs `eix` installed to fully function. It runs `eix-sync`. This is intended for use as a cron job. I use it daily.

This command can run `layman -S` for you if you pass `-l` or `--run-layman`.

## emerges

This command will do the following:

* Update Portage
* Update `@world` with options `--with-bdeps=y`, `--update`, `--deep`, `--newuse`
* Update live installations of packages (`@live-rebuild`)
* Run `emerge @preserved-rebuild`
* Run `systemctl daemon-reexec` (if applicable)
* Update the kernel

There are flags to disable most parts of this functionality, such as `--no-upgrade-kernel`. Pass `--help` to see all the options.

### Automatic kernel update process

The automatic kernel update will only work if there are 2 kernels displayed with the command `eselect --brief kernel list`. The first one in the list must be the active kernel. The second one is the one to upgrade to. After switching to the new kernel, a `.config` must exist in `/usr/src/linux` or the command will not run `make`. If the configuration exists at `/proc/config.gz` it will be used.

If `emerges` fails to build the kernel because of the state of `eselect kernel list`, you can fix it and re-run the update by running `upgrade-kernel`.

The old kernel data in `/boot` will be stored in `/root/.upkeep/old-kernels`.

Only GRUB (`grub-mkconfig`) and Dracut are supported for the kernel update. There is currently no way to skip Dracut or GRUB. Valid configurations must be present in `/etc`.

If you want to only rebuild the kernel, run `rebuild-kernel`.

## ecleans

This command will run the following commands (or equivalents):

* `emerge --depclean`
* `emerge @preserved-rebuild`
* `revdep-rebuild`
* `eclean-dist --deep`
* `rm -fR /var/tmp/portage/*`
