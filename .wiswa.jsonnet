local utils = import 'utils.libjsonnet';

{
  description: 'Portage update helper commands.',
  keywords: ['administration', 'command line', 'gentoo'],
  project_name: 'upkeep',
  version: '1.6.1',
  want_main: true,
  copilot+: {
    intro: 'Upkeep is a set of commands to help with maintaining a Gentoo system.',
  },
  prettierignore+: ['*.service'],
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
