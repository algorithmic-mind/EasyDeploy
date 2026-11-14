# Module: installer, edctl, deploy files

## Installer (`installer/install.sh`, v0)
Steps (each idempotent, logged to `/var/log/easydeploy/install.log`): preflight → mirrors → packages →
docker → release → users → python → config → redis → database → lego → nginx → systemd → firewall →
edctl → health → summary.

Modes:
* **Bootstrap (one command):** `install.sh` run on its own (no `lib/` next to it) downloads
  `<base>/latest/download/VERSION` (or uses `--version`), then `<base>/download/v<ver>/easydeploy-<ver>-linux-<arch>.tar.gz`
  and `SHA256SUMS`, verifies the checksum (fails closed), extracts to `/var/tmp/easydeploy-bootstrap.*` and execs the
  bundled installer with the same arguments. `<base>` defaults to the GitHub Releases of the repository; override
  with `--release-url` / `ED_RELEASE_URL` for a mirror with the same layout.
* `--release-file <tgz>` (needs `SHA256SUMS` next to it) or running `install.sh` from an extracted release
  (bundled CPython + wheelhouse, `--no-index`).
* `--from-source [path]` (development; uv installs CPython 3.12 + locked deps).

Releases are published by `.github/workflows/release.yml` on `v*` tags (amd64 + arm64, SHA256SUMS, VERSION) and
verified by installing them with the one-line command on a fresh runner. Signatures (minisign) and offline bundles:
Phase 6.

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
