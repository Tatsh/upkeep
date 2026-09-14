local utils = import 'utils.libjsonnet';

{
  uses_user_defaults: true,
  description: 'Portage update helper commands.',
  keywords: ['administration', 'command line', 'gentoo'],
  project_name: 'upkeep',
  version: '1.7.1',
  want_main: true,
  want_appimage: false,
  want_flatpak: false,
  want_snap: false,
  has_multiple_entry_points: false,
  supported_platforms: ['linux'],
  prettierignore+: ['*.service', '*.timer'],
  python_deps+: {
    main+: {
      tomlkit: utils.latestPypiPackageVersionCaret('tomlkit'),
    },
  },
  security_policy_supported_versions: { '1.7.x': ':white_check_mark:' },
  pyproject+: {
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
