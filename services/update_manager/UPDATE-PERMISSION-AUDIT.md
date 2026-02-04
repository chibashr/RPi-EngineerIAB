# Update Permission Audit

**Date:** 2025-02-04  
**Author:** chibashr  
**Context:** Web UI update fails with "Permission denied" when unlinking files during `git reset --hard`.

---

## Summary

The update flow tries `sudo bin/apply-update.sh` first. When sudo fails (e.g. container with `no-new-privileges`), it falls back to running `git fetch` and `git reset --hard` in-process as the API user. That fallback fails when the repo is owned by root or another user, because the API user cannot unlink or overwrite those files.

---

## Current Flow (from code audit)

| Step | Location | Behavior |
|------|----------|----------|
| 1 | `manager.py:_perform_update` | Tries `sudo bin/apply-update.sh` with NOPASSWD (installer adds sudoers rule) |
| 2 | `manager.py` | If stderr contains "no new privileges" or "adjust the container", falls back to in-process git |
| 3 | `manager.py` | Runs `git remote set-url`, `git fetch`, `git reset --hard` as current user |
| 4 | Failure | `git reset --hard` fails with "error: unable to unlink old '...': Permission denied" |

**Key functions:**
- `_sudo_unavailable_message()` – returns true only for "no new privileges" or "adjust the container"
- `apply-update.sh` – requires root; does `git fetch` + `git reset --hard` + write version file

---

## Sudo Password Prompt via Web UI

### Can it work?

**When sudo fails with "no new privileges" (container):** No. Sudo cannot run at all. A password would not help.

**When sudo fails with "password required" (no sudoers rule):** Yes, technically. You could:
1. Add a password field in the updates UI
2. Send it to the server over HTTPS
3. Run `echo "$password" | sudo -S bin/apply-update.sh ...`

### Why it is not recommended

1. **Security:** Password travels over the network (even if HTTPS), lives in server memory, and could be logged.
2. **No TTY:** `sudo -S` reads from stdin; the subprocess has no TTY, so it would need the password piped in. That works, but storing/handling it is risky.
3. **Your case:** Your log shows "sudo unavailable (e.g. container), trying without sudo...", which means `_sudo_unavailable_message` matched. Sudo is blocked by the environment (e.g. `no_new_privs`), not by a missing password. A password prompt would not change that.

### Conclusion

A sudo password prompt in the Web UI is not a viable fix for the container / no-new-privileges case and is not recommended for security reasons.

---

## Remediations

### 1. Run container without `no-new-privileges` (preferred when using sudo)

If you run in Docker, avoid `--security-opt=no-new-privileges` so sudo can elevate. Ensure the installer has run so the sudoers rule exists:

```bash
# /etc/sudoers.d/rpi-engineer-apply-update
rpi-engineer ALL=(root) NOPASSWD: /opt/rpi-engineer/bin/apply-update.sh
```

### 2. Make the repo writable by the API user

When sudo cannot run, the fallback needs write access:

```bash
# As root:
chmod -R g+w /opt/rpi-engineer
chmod -R g+w /opt/rpi-engineer/.git
# Ensure API user is in the group that owns the install dir
usermod -aG <group> rpi-engineer
```

### 3. Install to a directory owned by the service user

Set `RPI_ENGINEER_ROOT` to a path owned by the API user (e.g. `/home/rpi-engineer/app`). Then the in-process git fallback can write without root.

### 4. Add "Run update manually" command to the UI

Add a button that copies the exact command to run via SSH:

```bash
sudo /opt/rpi-engineer/bin/apply-update.sh \
  "https://github.com/chibashr/RPi-EngineerIAB.git" \
  main \
  /opt/rpi-engineer \
  /etc/rpi-engineer/version \
  <target_hash>
```

This helps when the Web UI cannot apply updates (e.g. container, permissions).

### 5. Improve error message when fallback fails

When `git reset` fails with "Permission denied", surface a clearer message and link to troubleshooting docs.

### 6. Exclude dev-only paths from update (optional)

Paths like `.cursor/`, `.planning/` are often dev-only. If they are in the repo and owned by a different user, they can cause permission errors. Options:
- Add them to `.gitignore` and stop tracking them (if appropriate)
- Or fix ownership so the API user can modify them during update

---

## Files Touched by Audit

| File | Role |
|------|------|
| `services/update_manager/manager.py` | Update logic, sudo fallback, `_sudo_unavailable_message` |
| `bin/apply-update.sh` | Root-only script; git fetch + reset |
| `bin/install.sh` | Adds NOPASSWD sudoers for apply-update.sh |
| `services/api_gateway/websockets.py` | WebSocket handler for `/ws/updates/apply` |
| `services/api_gateway/routes/updates.py` | REST `POST /api/v1/updates/apply` |
| `web/js/pages/updates.js` | Apply button, WebSocket + REST fallback |
| `web/docs/troubleshooting/common-issues.html` | Existing permission-related docs |

---

## Recommended Next Steps

1. **Short term:** Use remediation 2 or 3 (make repo writable or install to user-owned dir).
2. **Medium term:** Implement remediation 4 (copy manual command) and 5 (clearer error message).
3. **Avoid:** Sudo password prompt in the Web UI for the reasons above.

---

## Fix Applied (architecture-aligned)

1. **Manual update command in UI** – When an update is available, the Updates page shows a copyable command to run via SSH (already implemented).
2. **Clearer error on permission denied** – When `git reset` fails with "Permission denied", the message points to the manual command and troubleshooting docs (already implemented).
3. **Installer: optional group-writable install dir** – If `RPI_ENGINEER_UPDATE_WITHOUT_SUDO=1` is set during install, the installer runs `chmod -R g+w` on the install directory so the service user can run the in-process git fallback when sudo is unavailable (e.g. container with no-new-privileges). Use for new installs where sudo will not be used for updates.
4. **Documentation** – Troubleshooting (common-issues.html) documents the manual command, manual chmod, and the `RPI_ENGINEER_UPDATE_WITHOUT_SUDO=1` option for new installs.
