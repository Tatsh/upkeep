local utils = import 'utils.libjsonnet';

{
  uses_user_defaults: true,
  description: 'Portage update helper commands.',
  keywords: ['administration', 'command line', 'gentoo'],
  project_name: 'upkeep',
  version: '1.6.1',
  want_main: true,
  want_appimage: false,
  want_flatpak: false,
  want_snap: false,
  has_multiple_entry_points: true,
  prettierignore+: ['*.service', '*.timer'],
  security_policy_supported_versions: { '1.6.x': ':white_check_mark:' },
  pyproject+: {
    project+: {
      scripts: {
        ecleans: 'upkeep.commands:ecleans_command',
        emerges: 'upkeep.commands:emerges_command',
        'rebuild-kernel': 'upkeep.commands:rebuild_kernel_command',
        'upgrade-kernel': 'upkeep.commands:upgrade_kernel_command',
      },
    },
    tool+: {
      poetry+: {
        group+: {
          tests+: {
            dependencies+: {
              levenshtein: utils.latestPypiPackageVersionCaret('levenshtein'),
            },
          },
        },
        include+: ['systemd'],
      },
    },
  },
}
