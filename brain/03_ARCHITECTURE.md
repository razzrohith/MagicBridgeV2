# 03 — Architecture

## The layered picture

```
[Target PC] ──HDMI + USB-OTG (+ATX)──▶ PiKVM V4 Mini (CM4, PiKVM OS, read-only rootfs)
                                          │
   ┌───────────────────────────────────────┴───────────────────────────────────────┐
   │  NATIVE LAYER — kvmd (PiKVM's daemon, GPLv3). UNTOUCHED. Does the hardware.     │
   │  • video: HDMI→H.264/WebRTC (Janus) + MJPEG    • HID: USB keyboard/mouse gadget │
   │  • ATX power  • OLED  • EDID  • VNC (kvmd-vnc)  • MSD  • keymaps  • auth/TOTP    │
   └───────────────────────────────────────┬───────────────────────────────────────┘
                                            │  our services call kvmd's HTTP API
   ┌───────────────────────────────────────┴───────────────────────────────────────┐
   │  MAGICBRIDGE ADD-ON LAYER (/opt/magicbridge)                                    │
   │  • magicbridge-net     :8410  — network toolkit (WiFi, Tailscale, DuckDNS,      │
   │                                  MAC, monitor/EDID, VNC toggle, TOTP, telemetry)│
   │  • magicbridge-stealth :8411  — USB identity spoofing, stealth password, backup │
   │  • magicbridge-agent   :8412  — AI agent + macros (disabled by default)         │
   │  • web/ (our UI, served statically by nginx)                                    │
   │  • common/ — mbcommon.py (config/paths/branding), kvmd_client.py (kvmd API)     │
   └───────────────────────────────────────┬───────────────────────────────────────┘
                                            ▼
                    kvmd-nginx  TLS :443  (the single front door)
     Browser (MagicBridgeV2 UI)  ·  VNC :5900 (optional)  ·  kvmd API  ·  Janus WS
```

Design principle: **never edit kvmd's own files.** We only *add* — override snippets, extra
nginx location blocks, our own services. That keeps kvmd upgradeable underneath us.

---

## The three add-on services (Python aiohttp, run as root, no sandbox except ProtectHome)

All live in `/opt/magicbridge/services/<name>/app.py`, each a small aiohttp server on
localhost, reached through nginx at `/mb/<area>/`.

### `magicbridge-net` — 127.0.0.1:8410 → nginx `/mb/net/`
The network + system toolkit. Key endpoints:
- `/sys` — uptime/load/hostname (kvmd's `/api/info` has **no** uptime field).
- `/status` — Tailscale up?, DuckDNS, hostname, **live MAC** of active iface.
- `/latency` — WiFi signal (dBm + quality %), tx bitrate, RTT to gateway.
- `/clients` — who's viewing the console now (established :443 peers, with hostname + LAN/
  tailscale/remote classification).
- `/tailscale`, `/tailscale/install`, `/tailscale/funnel`, `/tailscale/peers` — Tailscale mgmt.
- `/wifi`, `/wifi/saved`, `/wifi/forget`, `/wifi/scan` — WiFi manager.
- `/monitor` (+ `/edid`) — realistic monitor/EDID spoofing via `kvmd-edidconf`.
- `/vnc`, `/totp*` — VNC toggle + 2FA (the editors are surfaced on the stealth page).
- `/mac`, `/lockdown`, `/duckdns`, `/wol`, `/led`, `/logs`, `/update`, `/update/apply`.

### `magicbridge-stealth` — 127.0.0.1:8411 → nginx `/mb/stealth/`
The USB-identity / anonymity brain. Endpoints: `/identity` (GET/POST), `/randomize`,
`/serial/random`, `/safe-mode`, `/backup`, `/restore`, `/lock-status`, `/unlock`,
`/password`. Applying an identity rewrites the OTG override then **rebuilds the USB gadget**
(a delicate operation — see debug journal). Gated by a **separate stealth password** (hash+
salt) so a live kvmd session alone can't reflash the gadget identity.

### `magicbridge-agent` — 127.0.0.1:8412 → nginx `/mb/agent/`
AI natural-language → keystrokes + macro runner. **Disabled by default** (feature flag) —
Raj decides when to reveal it. The AI tab in the UI is deliberately hidden behind a single
flag.

### Shared: `services/common/`
- `mbcommon.py` — logging, branding, and **config load/save**. Config lives in
  `/var/lib/magicbridge/*.json` (runtime, writable) with fallback to `/etc/magicbridge/`
  (install defaults). **`save_config()` now toggles the read-only rootfs rw/ro** — without
  that, nothing persisted (a real bug we fixed; see journal).
- `kvmd_client.py` — thin wrapper over kvmd's API (ATX/MSD/HID/GPIO/streamer/info) with the
  admin creds.

---

## nginx routing (`/etc/kvmd/nginx/magicbridge.conf`, included into kvmd's server block)

| Route | Serves |
|-------|--------|
| `location = /` | `return 302 /mb/ui/` — **our cockpit is the default landing page** |
| `/mb/ui/` | static alias → `/opt/magicbridge/web/` (the cockpit). `error_page 401/403 → /login/` |
| `/stealth/` | static alias → `/opt/magicbridge/web/stealth/` (the stealth panel) |
| `/mb/net/` | proxy → 127.0.0.1:8410 (`proxy_read_timeout 180s` for slow installs like Tailscale) |
| `/mb/stealth/` | proxy → 127.0.0.1:8411 |
| `/mb/agent/` | proxy → 127.0.0.1:8412 |
| `/login/`, `/kvm/`, `/api/`, `/streamer/`, `/janus/`, `/share/` | kvmd's own (rebranded) pages/APIs |

⚠️ nginx here is **kvmd's** nginx: config is generated from `/etc/kvmd/nginx/nginx.conf.mako`
into `/run/kvmd/nginx.conf`. Our block is included via a `sed` line added to the `.mako`.
Never run `nginx -t` against stock `/etc/nginx/nginx.conf` — it fails on a missing
`/var/log/nginx/access.log`; that path is a known false alarm.

---

## The read-only rootfs model (internalize this)

The PiKVM root filesystem is mounted **read-only** for reliability. To write anything under
`/etc`, `/opt`, `/usr`, `/var/lib` you must first unlock it:
- `rw` (PiKVM helper) or `mount -o remount,rw /` to unlock.
- `ro` or `mount -o remount,ro /` to relock.
- `/run` and a few `/var/lib/*` subdirs are tmpfs (always writable, but wiped on reboot).

**This is the single biggest source of "silent no-op" bugs in the whole project.** Any code
that writes config, enables a service, saves credentials, or rebuilds the gadget must wrap the
write in rw/ro. See the debug journal for the many times this bit us (save_config, Tailscale
install, VNC enable, WiFi creds, TOTP secret, EDID).

Two subtleties:
- **A shell function must NOT be named `rw`/`ro`** — `rw(){ … rw … }` recurses into itself
  forever (bash resolves the name to the function). Name helpers `mb_rw`/`mb_ro` and call
  `command rw`. This crashed the captive portal once.
- **`systemctl enable` fails with EROFS even after `rw`** (its symlink write goes through a
  path that doesn't observe the remount). A plain `os.symlink()` after `rw` works fine. So to
  persist a service across boot, create the `…/multi-user.target.wants/<unit>.service` symlink
  directly and use `systemctl start`/`stop` for the immediate action (that's how VNC toggle
  works now).

---

## Config / state file locations on the Pi

| Path | What |
|------|------|
| `/opt/magicbridge/` | our services + web UI (git-tracked tree; `align_pi.py` resets it) |
| `/var/lib/magicbridge/*.json` | runtime config (stealth identity, net, stealth_auth). **Writable dir but on the RO rootfs → needs rw to write.** |
| `/etc/magicbridge/kvmd.json` | install-time defaults (admin/admin) |
| `/etc/kvmd/override.d/00-magicbridge.yaml` | our boot kvmd overrides (streamer defaults, OTG identity + realistic serial) |
| `/etc/kvmd/override.d/90-magicbridge-otg.yaml` | live OTG identity written by the stealth service (wins over 00-) |
| `/etc/kvmd/nginx/magicbridge.conf` | our nginx location blocks |
| `/etc/kvmd/totp.secret` | 2FA secret (kvmd reads it; empty = 2FA off) |
| `/etc/kvmd/vncpasswd`, `/etc/kvmd/vnc/` | VNC auth + SSL (pre-configured) |
| `/etc/wpa_supplicant/wpa_supplicant-wlan0.conf` | saved WiFi networks |
| `/sys/kernel/config/usb_gadget/kvmd/` | the live USB gadget (configfs) — source of truth for what the target sees |
