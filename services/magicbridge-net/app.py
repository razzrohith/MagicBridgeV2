#!/usr/bin/env python3
"""
magicbridge-net — MagicBridgeV2 network toolkit sidecar.

Runs alongside kvmd on 127.0.0.1:8410 (behind kvmd nginx at /mb/net/).
Ports the V1 network features onto the PiKVM base WITHOUT touching kvmd:
  · DuckDNS dynamic-DNS updater (systemd-timer friendly)
  · Tailscale + Funnel status/toggle wrappers
  · Tailscale-only network lockdown (iptables, SSH never touched)
  · MAC address spoofing (persisted via our own unit, survives reboot)
  · WiFi scan/connect (nmcli)

This is a skeleton with the endpoint surface + DuckDNS implemented end-to-end
as the reference pattern; the remaining handlers are stubbed with clear TODOs
and get filled in one-by-one during hardware bring-up (see docs/PORTING.md).
"""
from __future__ import annotations
import asyncio, subprocess, sys, os, time
from pathlib import Path
sys.path.insert(0, "/opt/magicbridge/services/common")
try:
    from mbcommon import get_logger, load_config, save_config
except Exception:  # dev-machine fallback
    import logging
    def get_logger(n): logging.basicConfig(level=logging.INFO); return logging.getLogger(n)
    def load_config(n, d=None): return dict(d or {})
    def save_config(n, d): pass

from aiohttp import web

log = get_logger("mb-net")
PORT = int(os.environ.get("MB_NET_PORT", "8410"))

def sh(*args, timeout=15) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:
        return 1, str(e)

# ---- handlers -------------------------------------------------------
async def health(_): return web.json_response({"ok": True, "service": "magicbridge-net"})

async def status(_):
    ts_rc, ts_out = sh("tailscale", "status", "--json", timeout=8)
    return web.json_response({
        "tailscale": {"up": ts_rc == 0, "raw": ts_out[:2000]},
        "duckdns": load_config("net", {}).get("duckdns", {"enabled": False}),
        "hostname": os.uname().nodename,
    })

async def duckdns_update(request: web.Request):
    """POST /mb/net/duckdns  {domain, token} → updates DuckDNS, persists config."""
    body = await request.json()
    domain, token = body.get("domain", ""), body.get("token", "")
    if not domain or not token:
        return web.json_response({"ok": False, "error": "domain and token required"}, status=400)
    import urllib.request
    url = f"https://www.duckdns.org/update?domains={domain}&token={token}&ip="
    try:
        # offload blocking call so we never stall the event loop (V1 lesson)
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, lambda: urllib.request.urlopen(url, timeout=15).read().decode())
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=502)
    cfg = load_config("net", {}); cfg.setdefault("duckdns", {})
    cfg["duckdns"] = {"enabled": True, "domain": domain, "last": resp, "ts": int(time.time())}
    save_config("net", cfg)
    return web.json_response({"ok": resp.strip() == "OK", "duckdns_response": resp})

async def lockdown(request: web.Request):
    """POST /mb/net/lockdown {on: bool} — Tailscale-only access (SSH untouched)."""
    body = await request.json()
    on = bool(body.get("on"))
    # TODO(hw): port mb-lockdown.sh iptables logic; verify against kvmd's own ports.
    return web.json_response({"ok": True, "todo": "iptables lockdown port pending hardware", "requested": on})

async def mac_spoof(request: web.Request):
    """POST /mb/net/mac {iface, mac|random} — spoof + persist across reboot."""
    body = await request.json()
    # TODO(hw): port MAC spoof + _persist_mac() as our own systemd unit.
    return web.json_response({"ok": True, "todo": "mac spoof port pending hardware", "req": body})

def build_app() -> web.Application:
    app = web.Application()
    app.add_routes([
        web.get("/health", health),
        web.get("/status", status),
        web.post("/duckdns", duckdns_update),
        web.post("/lockdown", lockdown),
        web.post("/mac", mac_spoof),
    ])
    return app

if __name__ == "__main__":
    log.info("magicbridge-net starting on 127.0.0.1:%d", PORT)
    web.run_app(build_app(), host="127.0.0.1", port=PORT, print=None)
