#!/usr/bin/env python3
"""
magicbridge-net - MagicBridgeV2 network toolkit sidecar.

Runs alongside kvmd on 127.0.0.1:8410 (behind kvmd nginx at /mb/net/).
Ports V1's network features onto the PiKVM base WITHOUT touching kvmd:
  - DuckDNS dynamic-DNS updater
  - Tailscale status wrapper
  - Tailscale-only network lockdown (iptables; SSH never touched)
  - MAC address spoofing (persisted; re-applied at boot)
  - WiFi scan/connect (nmcli) - TODO on hardware
"""
from __future__ import annotations
import asyncio
import os
import subprocess
import sys
import time

sys.path.insert(0, "/opt/magicbridge/services/common")
try:
    from mbcommon import get_logger, load_config, save_config
except Exception:  # dev-machine fallback
    import logging

    def get_logger(n):
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(n)

    def load_config(n, d=None):
        return dict(d or {})

    def save_config(n, d):
        pass

from aiohttp import web

log = get_logger("mb-net")
PORT = int(os.environ.get("MB_NET_PORT", "8410"))


def sh(*args, timeout=15):
    try:
        p = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:
        return 1, str(e)


async def health(_):
    return web.json_response({"ok": True, "service": "magicbridge-net"})


async def status(_):
    ts_rc, ts_out = sh("tailscale", "status", "--json", timeout=8)
    return web.json_response({
        "tailscale": {"up": ts_rc == 0, "raw": ts_out[:2000]},
        "duckdns": load_config("net", {}).get("duckdns", {"enabled": False}),
        "hostname": os.uname().nodename,
    })


async def duckdns_update(request):
    body = await request.json()
    domain = body.get("domain", "")
    token = body.get("token", "")
    if not domain or not token:
        return web.json_response({"ok": False, "error": "domain and token required"}, status=400)
    import urllib.request
    url = f"https://www.duckdns.org/update?domains={domain}&token={token}&ip="
    try:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None, lambda: urllib.request.urlopen(url, timeout=15).read().decode())
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=502)
    cfg = load_config("net", {})
    cfg["duckdns"] = {"enabled": True, "domain": domain, "last": resp, "ts": int(time.time())}
    save_config("net", cfg)
    return web.json_response({"ok": resp.strip() == "OK", "duckdns_response": resp})


async def lockdown(request):
    body = await request.json()
    on = bool(body.get("on"))
    sh("iptables", "-N", "MB_LOCKDOWN")
    sh("iptables", "-F", "MB_LOCKDOWN")
    if on:
        for port in ("80", "443"):
            sh("iptables", "-A", "MB_LOCKDOWN", "-i", "lo", "-p", "tcp", "--dport", port, "-j", "ACCEPT")
            sh("iptables", "-A", "MB_LOCKDOWN", "-i", "tailscale0", "-p", "tcp", "--dport", port, "-j", "ACCEPT")
            sh("iptables", "-A", "MB_LOCKDOWN", "-p", "tcp", "--dport", port, "-j", "DROP")
        rc, _out = sh("iptables", "-C", "INPUT", "-j", "MB_LOCKDOWN")
        if rc != 0:
            sh("iptables", "-I", "INPUT", "1", "-j", "MB_LOCKDOWN")
    else:
        sh("iptables", "-D", "INPUT", "-j", "MB_LOCKDOWN")
    cfg = load_config("net", {})
    cfg["lockdown"] = on
    save_config("net", cfg)
    return web.json_response({"ok": True, "lockdown": on, "note": "SSH (22) never restricted"})


async def mac_spoof(request):
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
    return web.json_response({
        "ok": rc == 0, "iface": iface, "mac": mac, "detail": out[:300],
        "persisted": "re-applied at boot via magicbridge-net config",
    })


async def tailscale_ctl(request):
    body = await request.json()
    action = body.get("action", "status")
    if action == "up":
        rc, out = sh("tailscale", "up", "--accept-routes", timeout=30)
    elif action == "down":
        rc, out = sh("tailscale", "down", timeout=15)
    else:
        rc, out = sh("tailscale", "status", timeout=10)
    return web.json_response({"ok": rc == 0, "action": action, "detail": out[:1500]})


async def wifi_connect(request):
    """POST /mb/net/wifi {ssid, password} — add/connect a Wi-Fi network via wpa_supplicant."""
    body = await request.json()
    ssid = body.get("ssid", "")
    pw = body.get("password", "")
    if not ssid:
        return web.json_response({"ok": False, "error": "ssid required"}, status=400)
    conf = "/etc/wpa_supplicant/wpa_supplicant-wlan0.conf"
    # generate a network block and append (rw toggle for PiKVM read-only FS)
    sh("bash", "-c", "command -v rw >/dev/null && rw || mount -o remount,rw /")
    try:
        rc, block = sh("wpa_passphrase", ssid, pw)
        if rc != 0:
            return web.json_response({"ok": False, "error": block[:300]}, status=502)
        try:
            with open(conf, "a") as f:
                f.write("\n" + block + "\n")
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)
        sh("systemctl", "restart", "wpa_supplicant@wlan0")
    finally:
        sh("bash", "-c", "command -v ro >/dev/null && ro || true")
    cfg = load_config("net", {}); cfg["wifi"] = {"ssid": ssid}; save_config("net", cfg)
    return web.json_response({"ok": True, "ssid": ssid, "note": "added; may take a few seconds to associate"})


def build_app():
    app = web.Application()
    app.add_routes([
        web.get("/health", health),
        web.get("/status", status),
        web.post("/duckdns", duckdns_update),
        web.post("/lockdown", lockdown),
        web.post("/mac", mac_spoof),
        web.post("/tailscale", tailscale_ctl),
        web.post("/wifi", wifi_connect),
    ])
    return app


if __name__ == "__main__":
    log.info("magicbridge-net starting on 127.0.0.1:%d", PORT)
    web.run_app(build_app(), host="127.0.0.1", port=PORT, print=None)
