local utils = import 'utils.libjsonnet';

(import 'defaults.libjsonnet') + {
  // Project-specific
  description: 'Portage update helper commands.',
  keywords: ['administration', 'command line', 'gentoo'],
  project_name: 'upkeep',
  version: '1.6.1',
  want_main: true,
  citation+: {
    'date-released': '2025-04-19',
  },
  pyproject+: {
    project+: {
      scripts: {
        ecleans: 'upkeep.commands:ecleans_command',
        emerges: 'upkeep.commands:emerges_command',
        esync: 'upkeep.commands:esync_command',
        'rebuild-kernel': 'upkeep.commands:rebuild_kernel_command',
        'upgrade-kernel': 'upkeep.commands:upgrade_kernel_command',
      },
    },
    tool+: {
      poetry+: {
        dependencies+: {
          click: '^8.1.8',
        },
        group+: {
          tests+: {
            dependencies+: {
              levenshtein: '^0.27.1',
            },
          },
        },
        include+: ['systemd'],
      },
    },
  },
  // Common
  authors: [
    {
      'family-names': 'Udvare',
      'given-names': 'Andrew',
      email: 'audvare@gmail.com',
      name: '%s %s' % [self['given-names'], self['family-names']],
    },
  ],
  local funding_name = '%s2' % std.asciiLower(self.github_username),
  github_username: 'Tatsh',
  github+: {
    funding+: {
      ko_fi: funding_name,
      liberapay: funding_name,
      patreon: funding_name,
    },
  },
}
