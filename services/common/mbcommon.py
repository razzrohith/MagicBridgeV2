"""
mbcommon — shared helpers for MagicBridgeV2 add-on services.

Keeps every sidecar consistent: config loading, branding, logging, and a
thin client to talk to the local kvmd API (so we extend kvmd, not fight it).
"""
from __future__ import annotations
import json, logging, os, ssl
from pathlib import Path

INSTALL_ROOT = Path(os.environ.get("MB_ROOT", "/opt/magicbridge"))
STATE_DIR = Path("/var/lib/magicbridge")      # writable even on read-only rootfs
CONFIG_DIR = Path("/etc/magicbridge")

def get_logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    return log

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

def load_config(name: str, default: dict | None = None) -> dict:
    """Per-service JSON config in /etc/magicbridge/<name>.json (falls back to default)."""
    p = CONFIG_DIR / f"{name}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return dict(default or {})

def save_config(name: str, data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / f"{name}.json").write_text(json.dumps(data, indent=2))

# --- kvmd API client (localhost) -------------------------------------
KVMD_BASE = os.environ.get("MB_KVMD_URL", "https://127.0.0.1/api")

def kvmd_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE   # kvmd uses a self-signed cert locally
    return ctx
