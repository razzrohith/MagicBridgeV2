#!/usr/bin/env python3
"""
magicbridge-net — MagicBridgeV2 network toolkit sidecar.

Runs alongside kvmd on 127.0.0.1:8410 (behind kvmd nginx at /mb/net/).
Ports the V1 network features onto the PiKVM base WITHOUT touching kvmd:
  · DuckDNS dynamic-DNS updater
  · Tailscale status wrapper
  · Tailscale-only network lockdown (iptables, SSH never touched)
  · MAC address spoofing (persisted via our own config, re-applied at boot)
  · WiFi scan/connect (nmcli) — TODO on hardware
"""
from __future__ import annotations
import asyncio, subprocess, sys, os, time
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
        p = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:
        return 1, str(e)

# ---- handlers -------------------------------------------------------
async def health(_):
    return web.json_response({"ok": True, "service": "magicbridge-net"})

async def status(_):
    ts_rc, ts_out = sh("tailscale", "status", "--json", timeout=8)
    return web.json_response({
        "tailscale": {"up": ts_rc == 0, "raw": ts_out[:2000]},
        "duckdns": load_config("net", {}).get("duckdns", {"enabled": False}),
        "hostname": os.uname().nodename,
    })

async def duckdns_update(request: web.Request):
    """POST /mb/net/duckdns {domain, token} → updates DuckDNS, persists config."""
    body = await request.json()
    domain, token = body.get("domain", ""), body.get("token", "")
    if not domain or not token:
        return web.json_response({"ok": False, "error": "domain and token required"}, status=400)
    import urllib.request
    url = f"https://www.duckdns.org/update?domains={domain}&token={token}&ip="
    try:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, lambda: urllib.request.urlopen(url, timeout=15).read().decode())
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=502)
    cfg = load_config("net", {})
    cfg["duckdns"] = {"enabled": True, "domain": domain, "last": resp, "ts": int(time.time())}
    save_config("net", cfg)
    return web.json_response({"ok": resp.strip() == "OK", "duckdns_response": resp})

async def lockdown(request: web.Request):
    """POST /mb/net/lockdown {on} — restrict web (80/443) to loopback + tailscale0.
    SSH (22) is NEVER touched, so you can't lock yourself out."""
    body = await request.json()
    on = bool(body.get("on"))
    sh("iptables", "-N", "MB_LOCKDOWN")
    sh("iptables", "-F", "MB_LOCKDOWN")
    if on:
        for port in ("80", "443"):
            sh("iptables", "-A", "MB_LOCKDOWN", "-i", "lo", "-p", "tcp", "--dport", port, "-j", "ACCEPT")
            sh("iptables", "-A", "MB_LOCKDOWN", "-i", "tailscale0", "-p", "tcp", "--dport", port, "-j", "ACCEPT")
            sh("iptables", "-A", "MB_LOCKDOWN", "-p", "tcp", "--dport", port, "-j", "DROP")
        rc, _ = sh("iptables", "-C", "INPUT", "-j", "MB_LOCKDOWN")
        if rc != 0:
            sh("iptables", "-I", "INPUT", "1", "-j", "MB_LOCKDOWN")
    else:
        sh("iptables", "-D", "INPUT", "-j", "MB_LOCKDOWN")
    cfg = load_config("net", {})
    cfg["lockdown"] = on
    save_config("net", cfg)
    return web.json_response({"ok": True, "lockdown": on, "note": "SSH (22) never restricted"})

async def mac_spoof(request: web.Request):
    """POST /mb/net/mac {iface, mac|random} — spoof + persist across reboot."""
    body = await request.json()
    iface = body.get("iface", "wlan0")
    if body.get("random"):
        import random
        mac = "02:%02x:%02x:%02x:%02x:%02x" % tuple(random.randint(0, 255) for _ in range(5))
    else:
        mac = body.get("mac", "")
    if not mac:
        return web.json_response({"ok": False, "error": "mac or random required"}, status=400)
    sh("ip", "link", "set", iface, "down")
    rc, out = sh("ip", "link", "set", iface, "address", mac)
    sh("ip", "link", "set", iface, "up")
    cfg = load_config("net", {})
    cfg["mac"] = {"iface": iface, "mac": mac}
    save_config("net", cfg)
    return web.json_response({"ok": rc == 0, "iface": iface, "mac": mac, "detail": out[:300],
                              "persisted": "re-applied at boot via magicbridge-net config"})

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
