# Module: installer, edctl, deploy files

## Installer (`installer/install.sh`, v0)
Steps (each idempotent, logged to `/var/log/easydeploy/install.log`): preflight → mirrors → packages →
docker → release → users → python → config → redis → database → lego → nginx → systemd → firewall →
edctl → health → summary.

Modes: `--from-source [path]` (development; uv installs CPython 3.12 + locked deps), `--release-file <tgz>`
or running `install.sh` from an extracted release (bundled CPython + wheelhouse, `--no-index`).
Signed online releases and offline bundles: Phase 6.

Mirror profiles are data files: `installer/mirrors/{global,ir,custom}.env` (the owner fills `ir.env`).

Re-running over an installation needs `--reinstall`; it keeps the database, secrets, admin password,
entrance and port.

Testing: `bats installer/tests` (helpers only) and `scripts/vm-test.sh root@<disposable-vm>`;
CI runs a full install on fresh GitHub runners (`installer-e2e.yml`).

## edctl
`status`, `start|stop|restart [agent|api|worker]`, `logs`, `user-info`, `reset-password [--prompt]`,
`reset-2fa`, `reset-entrance [--value|--disable]`, `reset-allowlist`, `reset-bind-domain`,
`set-port <port>` (nginx -t + rollback, UFW), `doctor`, `version`. `--json`, `--lang en|fa`.
Management commands run as the `easydeploy` user via `runuser`.

## Deploy files
`deploy/systemd/*` (units, target, tmpfiles), `deploy/nginx/*` (conf.d include, default 444 servers,
panel template with `@TOKENS@`, snippets), `deploy/redis/easydeploy.conf`, `deploy/logrotate/easydeploy`.
