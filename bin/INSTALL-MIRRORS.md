# Install mirrors and offline use

When GitHub is unreachable from the device (e.g. restricted networks, LTE hotspots that block or stall GitHub), you can use a **mirror** or a **local source** so the installer never talks to GitHub.

There are **no official public mirrors** for this project. Any mirror is one you or your organization host. This doc describes how to use mirrors and how to run fully offline.

## Using a mirror

### `bin/install.sh` (git clone / git fetch)

| Variable | Default | Purpose |
|----------|---------|---------|
| `RPI_ENGINEER_REPO_URL` | `https://github.com/chibashr/RPi-EngineerIAB.git` | Git remote URL for clone and fetch |
| `RPI_ENGINEER_REPO_BRANCH` | `main` | Branch to clone or reset to |

Example (use your own Git server):

```bash
sudo RPI_ENGINEER_REPO_URL="https://git.example.com/team/RPi-EngineerIAB.git" \
     RPI_ENGINEER_REPO_BRANCH="main" \
     NONINTERACTIVE=1 DEBIAN_FRONTEND=noninteractive \
     bash bin/install.sh
```

### `bin/install-and-bootstrap.sh` (tarball download)

| Variable | Default | Purpose |
|----------|---------|---------|
| `RPI_ENGINEER_REPO_ARCHIVE_URL` | GitHub `.../archive/refs/heads/main.tar.gz` | URL of the repo tarball |
| `RPI_ENGINEER_REPO_ARCHIVE_TOP` | `RPi-EngineerIAB-main` | Top-level directory inside the tarball |

Example (use your mirror’s tarball):

```bash
curl -fsSL https://raw.githubusercontent.com/chibashr/RPi-EngineerIAB/main/bin/install-and-bootstrap.sh | \
  sudo RPI_ENGINEER_REPO_ARCHIVE_URL="https://mirror.example.com/rpi-engineer/main.tar.gz" \
       RPI_ENGINEER_REPO_ARCHIVE_TOP="RPi-EngineerIAB-main" \
  bash
```

If your mirror tarball uses a different top-level directory (e.g. `rpi-engineer-main`), set `RPI_ENGINEER_REPO_ARCHIVE_TOP` to that name.

## Running fully offline (no mirror, no GitHub)

When the device cannot reach any mirror or GitHub:

1. **Copy the repo onto the device** (USB, SCP from another machine, etc.), e.g. to `/tmp/rpi-src`.
2. Run the installer from that copy so it deploys from local source and does not run `git clone` or `git fetch`:

   ```bash
   cd /tmp/rpi-src
   sudo NONINTERACTIVE=1 DEBIAN_FRONTEND=noninteractive bin/install.sh
   sudo NONINTERACTIVE=1 DEBIAN_FRONTEND=noninteractive bin/install-and-bootstrap.sh
   ```

If the app is already installed at `/opt/rpi-engineer` and you only need to re-run the installer and bootstrap without network:

```bash
cd /opt/rpi-engineer
sudo RPI_ENGINEER_SKIP_CLONE=1 NONINTERACTIVE=1 DEBIAN_FRONTEND=noninteractive bin/install.sh
sudo NONINTERACTIVE=1 DEBIAN_FRONTEND=noninteractive bin/install-and-bootstrap.sh
```

See `bin/install-and-bootstrap.sh` (header comments) for all tunables (WAN interface, hotspot SSID/password, API base URL).

## Setting up your own mirror

### Option A: Serve a tarball (for install-and-bootstrap.sh)

1. On a machine that can reach GitHub (or your Git server), create a tarball:

   ```bash
   git clone --depth 1 --branch main https://github.com/chibashr/RPi-EngineerIAB.git /tmp/RPi-EngineerIAB
   tar -czf rpi-engineer-main.tar.gz -C /tmp RPi-EngineerIAB
   ```

2. Serve `rpi-engineer-main.tar.gz` over HTTP/HTTPS (e.g. nginx, Apache, or a simple `python3 -m http.server`).
3. On the Pi, run the bootstrap script with:

   ```bash
   RPI_ENGINEER_REPO_ARCHIVE_URL="http://your-server/rpi-engineer-main.tar.gz"
   RPI_ENGINEER_REPO_ARCHIVE_TOP="RPi-EngineerIAB"
   ```

   (Use the actual top-level directory name inside your tarball for `RPI_ENGINEER_REPO_ARCHIVE_TOP`.)

### Option B: Git server (for install.sh clone/fetch)

1. Clone or mirror the repo to your Git server (Gitea, GitLab, GitHub Enterprise, or a bare repo behind nginx).
2. Use `RPI_ENGINEER_REPO_URL` and `RPI_ENGINEER_REPO_BRANCH` when running `bin/install.sh` as in the table above.

### Option C: Proxy GitHub archive URL

If you have an internal proxy that can reach GitHub, point `RPI_ENGINEER_REPO_ARCHIVE_URL` at the proxy (e.g. `https://proxy.example.com/github/chibashr/RPi-EngineerIAB/archive/refs/heads/main.tar.gz`). The tarball format and top-level directory should match GitHub’s (`RPi-EngineerIAB-main`).
