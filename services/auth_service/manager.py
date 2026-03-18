"""
Auth manager: HMAC-signed tokens, admin password (PAM + bcrypt fallback),
per-IP lockout. Token format: <expiry_unix_int>.<hmac_hex>.
"""

import configparser
import hmac
import os
import secrets
import time
from pathlib import Path

import bcrypt

_AUTH_CONF = "config/auth.conf"
_AUTH_CONF_ENV = "RPI_ENGINEER_AUTH_CONF"
_LOCKOUT_WINDOW = 600.0
_LOCKOUT_THRESHOLD = 20
_TOKEN_EXPIRY_SECONDS = 14400

_failed: dict[str, list[float]] = {}


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "config").is_dir() and (p / "AGENTS.md").exists():
            return p
        p = p.parent
    return Path.cwd()


def _auth_conf_path() -> Path:
    if _AUTH_CONF_ENV in os.environ:
        return Path(os.environ[_AUTH_CONF_ENV])
    return _repo_root() / _AUTH_CONF


def _read_config() -> configparser.ConfigParser:
    path = _auth_conf_path()
    cfg = configparser.ConfigParser()
    if path.exists():
        try:
            with open(path) as f:
                raw = f.read()
            if raw.strip() and not raw.lstrip().startswith("["):
                raw = "[auth]\n" + raw
            cfg.read_string(raw)
        except Exception:
            pass
    if not cfg.has_section("auth"):
        cfg.add_section("auth")
    return cfg


def _write_config(cfg: configparser.ConfigParser) -> None:
    path = _auth_conf_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        cfg.write(f)


def _get_or_create_token_secret() -> str:
    cfg = _read_config()
    secret = cfg.get("auth", "token_secret", fallback=None)
    if not secret or not secret.strip():
        secret = secrets.token_hex(32)
        cfg.set("auth", "token_secret", secret)
        _write_config(cfg)
    return secret.strip()


# Ensure token_secret exists on module load
def _ensure_secret() -> None:
    _get_or_create_token_secret()


_ensure_secret()


def verify_token(token: str) -> bool:
    """Format: <expiry_unix_int>.<hmac_hex>. Returns False on any error."""
    try:
        if not token or "." not in token:
            return False
        parts = token.strip().split(".", 1)
        if len(parts) != 2:
            return False
        expiry_str, sig = parts[0].strip(), parts[1]
        secret = _get_or_create_token_secret()
        expected = hmac.new(secret.encode(), expiry_str.encode(), "sha256").hexdigest()
        if not hmac.compare_digest(expected, sig):
            return False
        expiry = int(expiry_str)
        return expiry > time.time()
    except Exception:
        return False


def create_token() -> str:
    """Create token with expiry in 14400 seconds."""
    expiry = int(time.time()) + _TOKEN_EXPIRY_SECONDS
    secret = _get_or_create_token_secret()
    payload = str(expiry)
    signature = hmac.new(secret.encode(), payload.encode(), "sha256").hexdigest()
    return f"{expiry}.{signature}"


def validate_admin_password(password: str) -> bool:
    """
    Validate the admin password.

    Priority:
    1. If `password_hash` exists in auth config, try bcrypt first.
    2. If bcrypt fails (or no hash exists), fall back to PAM authentication for the `rpi-engineer` system user.
    """

    if not password:
        return False

    cfg = _read_config()
    stored = cfg.get("auth", "password_hash", fallback=None) or ""
    if stored.strip():
        try:
            if bcrypt.checkpw(password.encode(), stored.strip().encode()):
                return True
        except Exception:
            # Ignore bcrypt errors and fall back to PAM.
            pass

    # No bcrypt hash configured; fall back to PAM (keeps older deployments working).
    admin_user = os.environ.get("RPI_ENGINEER_SERVICE_USER", "rpi-engineer")
    try:
        import pam

        p = pam.pam()
        return bool(p.authenticate(admin_user, password))
    except ImportError:
        return False
    except Exception:
        return False


def _prune(ip: str) -> None:
    now = time.time()
    cutoff = now - _LOCKOUT_WINDOW
    if ip in _failed:
        _failed[ip] = [t for t in _failed[ip] if t > cutoff]
        if not _failed[ip]:
            del _failed[ip]


def record_failed_attempt(ip: str) -> bool:
    """Append current time for ip; prune entries older than 600s. Return True if count >= 20."""
    now = time.time()
    if ip not in _failed:
        _failed[ip] = []
    _failed[ip].append(now)
    cutoff = now - _LOCKOUT_WINDOW
    _failed[ip] = [t for t in _failed[ip] if t > cutoff]
    return len(_failed[ip]) >= _LOCKOUT_THRESHOLD


def is_locked_out(ip: str) -> bool:
    """True if ip has >= 20 entries in _failed within the last 600 seconds."""
    _prune(ip)
    return len(_failed.get(ip, [])) >= _LOCKOUT_THRESHOLD


def clear_lockout(ip: str) -> None:
    """Remove ip from _failed."""
    if ip in _failed:
        del _failed[ip]
