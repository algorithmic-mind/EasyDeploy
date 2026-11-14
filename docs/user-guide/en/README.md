# EasyDeploy user guide (Phase 0)

## Install

> The installer changes the system (Docker, Nginx, firewall). Run it only on a fresh, disposable server or VM.

Requirements: Ubuntu Server 22.04 / 24.04 / 26.04 (amd64 or arm64), root, ≥ 1 GB RAM, ≥ 10 GB free disk.

One command (latest release from GitHub, SHA-256 verified):

```bash
curl -fsSL https://raw.githubusercontent.com/algorithmic-mind/EasyDeploy/main/installer/install.sh -o install.sh && sudo bash install.sh
```

Without access to GitHub on the server: download `easydeploy-<ver>-linux-<arch>.tar.gz` and `SHA256SUMS`
elsewhere, copy them with `install.sh`, then `sudo bash install.sh --release-file easydeploy-<ver>-linux-<arch>.tar.gz`.

From source (development):

```bash
cd frontend && npm ci && npm run build && cd ..
sudo bash installer/install.sh --from-source --yes
```

Restricted networks: fill `installer/mirrors/ir.env` with mirrors you trust and pass `--mirror-profile ir`.

At the end the installer prints the panel URL `https://<ip>:<port>/<entrance>`, the username and the
password **once**. The browser warns about the self-signed certificate; that is expected.

## First login

1. Open the full URL including the security entrance; without it the panel answers "Not Found".
2. Sign in, then open the user menu → **Account** and enable two-factor authentication. Save the recovery codes.
3. Switch the language to Persian from the top bar to get the full RTL layout; the Jalali calendar is in **Account**.

## Recover access (on the server, as root)

`edctl user-info`, `edctl reset-password`, `edctl reset-2fa`, `edctl reset-entrance`, `edctl reset-allowlist`,
`edctl reset-bind-domain`, `edctl set-port <port>`, `edctl doctor`, `edctl status` (`--lang fa` for Persian).

## Uninstall

`sudo bash /opt/easydeploy/current/installer/uninstall.sh` keeps user data by default; `--purge --yes`
removes everything.
