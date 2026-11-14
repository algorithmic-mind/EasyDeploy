#!/usr/bin/env bash
# EasyDeploy upgrade (§8.3) — delivered in Phase 6 together with signed releases and `edctl update`.
# Until then, re-run the installer over an existing installation:
#   sudo bash install.sh --reinstall [--release-file <tarball> | --from-source]
# It keeps the database, secrets, admin password, entrance and panel port.
set -Eeuo pipefail
echo "upgrade.sh arrives in Phase 6 (signed releases, automatic rollback)." >&2
echo "For now: sudo bash install.sh --reinstall --release-file <tarball>   (data and settings are kept)" >&2
exit 2
