"""
mbcommon - shared helpers for MagicBridgeV2 add-on services.

Keeps every sidecar consistent: config loading, branding, logging, and paths
that respect PiKVM's READ-ONLY root filesystem.

Storage model (important on PiKVM OS):
  /etc/magicbridge      -> install-time DEFAULTS only (read-only at runtime)
  /var/lib/magicbridge  -> runtime-mutable state + user config (WRITABLE)

load_config() reads runtime state first, then falls back to the install
default, then to the caller's default. save_config() only ever writes to the
writable state dir, and marks files 0600 (they may hold API keys / creds).
Both dirs are overridable via MB_STATE_DIR / MB_CONFIG_DIR (used by tests).
"""
from __future__ import annotations
import json
import logging
import os
from pathlib import Path

INSTALL_ROOT = Path(os.environ.get("MB_ROOT", "/opt/magicbridge"))
STATE_DIR = Path(os.environ.get("MB_STATE_DIR", "/var/lib/magicbridge"))   # writable
CONFIG_DIR = Path(os.environ.get("MB_CONFIG_DIR", "/etc/magicbridge"))     # read-only defaults


def get_logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    return log


_log = get_logger("mbcommon")


def load_branding() -> dict:
    env = {}
    p = INSTALL_ROOT / "branding" / "branding.env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def load_config(name: str, default: dict | None = None) -> dict:
    """Runtime state (writable dir) wins over install default over caller default."""
    for base in (STATE_DIR, CONFIG_DIR):
        data = _read_json(base / f"{name}.json")
        if isinstance(data, dict):
            return data
    return dict(default or {})


def save_config(name: str, data: dict) -> bool:
    """Persist to the WRITABLE state dir only (never /etc). Files are 0600.
    Returns True on success; logs and returns False on failure instead of raising,
    so a handler never 500s just because a write failed."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(STATE_DIR, 0o700)
        except Exception:
            pass
        target = STATE_DIR / f"{name}.json"
        tmp = STATE_DIR / f".{name}.json.tmp"
        tmp.write_text(json.dumps(data, indent=2))
        try:
            os.chmod(tmp, 0o600)
        except Exception:
            pass
        os.replace(tmp, target)   # atomic
        return True
    except Exception as e:
        _log.error("save_config(%s) failed: %s", name, e)
        return False


# --- kvmd API base (creds/URL live in kvmd.json; defaults match PiKVM) ---
KVMD_BASE = os.environ.get("MB_KVMD_URL", "https://127.0.0.1/api")
