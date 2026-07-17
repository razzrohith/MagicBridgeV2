# 04 — Features (done · native · pending · dropped)

Legend: ✅ done & working · 🟢 native (kvmd gives it free) · 🟡 pending/deferred · ⛔ dropped/out-of-scope

## The UI, page by page (cockpit at `/mb/ui/`)

### Screen & Control
- ✅ Live video — **WebRTC/H.264 by default** (shares the one hardware encoder via Janus
  fan-out), MJPEG as fallback. 🟢 capture/encode is native kvmd.
- ✅ Keyboard + mouse over the binary control WebSocket (`/api/ws`). Absolute + **relative**
  mouse (relative needs the `usb_rel` gadget switch), wheel, quick combos (incl. Win+L, Task
  Mgr), fullscreen.
- ✅ **Click-to-capture / Esc-to-release** (no more hold-to-exit trap).
- ✅ On-screen keyboard (sticky modifiers, sends over WS without grabbing the real keyboard).
- ✅ **Paste with human-like typing** — `typeHuman()`: per-char randomized delays, pauses after
  punctuation/spaces, occasional think-pause, Style (human/instant) + Speed selectors, Stop.
- ✅ Video quality controls (JPEG quality / target FPS / resolution → `/api/streamer/set_params`).
- ✅ Screenshot capture.

### Power
- ✅ ATX power control (on/reset/soft-off/force-off) — kept with an honest "needs the header
  wired" note (kvmd can't sense whether the ATX pins are physically connected).
- 🟢 GPIO card (auto-hides — the V4 Mini has no GPIO channels).
- ⛔ **Virtual Media (MSD)** — removed from the UI (Raj's scope exclusion). Native in kvmd but
  not surfaced.
- ⛔ **Wake-on-LAN** — removed (can't wake anything over a WiFi-only link with no wired target NIC).

### Network
- ✅ **WiFi manager** — connect/save, list saved networks with which one is connected, **Forget**.
  Backed by `wpa_supplicant-wlan0.conf` with the plain-quoted-psk write (never `wpa_passphrase`).
- ✅ **Tailscale** — install / bring-up (surfaces the login link) / down / Funnel / Lockdown.
  *(Sign-in itself is a manual step for Raj.)*
- ✅ DuckDNS dynamic DNS.

### Automation
- ✅ **Clips** — saved text snippets (browser localStorage, ≤30), one-click paste via human typing.
- ✅ **Mouse jiggler** — net-zero idle-prevention with interval, pauses on real input (kvmd native jiggler).
- 🟡 **AI Agent + macros** — built but **hidden behind a feature flag** (Raj decides when to reveal).

### System (view-only telemetry + maintenance)
- ✅ Device / Health cards (CPU temp, throttling, **uptime** via `/mb/net/sys`, stream encoder, video res/fps/bitrate).
- ✅ **Network quality** — WiFi SSID, signal (dBm + %), link rate, RTT to gateway.
- ✅ **Connected clients** — count + who's viewing (IP/hostname, LAN/tailscale/remote tag).
- ✅ **Tailscale peers** — hostname/OS/location/online.
- ✅ **Device identity (view-only)** — spoofed USB device + serial, MAC, spoofed monitor, safe-mode,
  VNC exposure, 2FA state. **Editing lives only on the stealth page** (anonymity rule).
- ✅ Maintenance — check/apply update (git self-update), reboot/shutdown, HID connect/disconnect,
  Activity LED on/off, OLED state.
- ✅ Logs viewer (journald tail), Advanced/native tools (web terminal + native KVM fallback).

## The stealth panel (`/stealth/` — hidden, no link in the main UI, password-gated)
- ✅ **USB identity spoofing** — realistic presets (Logitech Unifying **default**, Logitech
  MK270, Microsoft, Dell KM636, HP) + custom VID/PID/mfr/product/serial, Apply (rebuilds
  gadget), Randomize, Randomize-serial. **Realistic serials, never CAFEBABE.**
- ✅ **MAC spoofing** — apply / randomize, persists.
- ✅ **Monitor / EDID spoofing** — realistic monitors (Dell U2720Q/P2419H, LG, Samsung, Asus,
  HP, BenQ, Acer, Generic), realistic ASCII serial.
- ✅ **Safe mode** (minimise exposed USB interfaces).
- ✅ **VNC** toggle + **2FA (TOTP)** enroll/verify/disable (both verified working; off by default).
- ✅ WiFi, DuckDNS, Tailscale/Funnel/Lockdown, config **backup/restore**, logs.
- ✅ **Separate stealth password** lock (hash+salt, independent of the kvmd login).
- ✅ Restyled to the professional glass theme (dropped the neon cyberpunk HUD in the V2 polish).

## Branding / anonymity
- ✅ Fully rebranded — hostname `magicbridge`, OLED splash, UI title/logo, MOTD, custom login
  page (not stock PiKVM), `location = / → /mb/ui/` default. Zero visible PiKVM/RPi/kvmd tells.
- ✅ Main page = view-only identity; stealth page = edit (Raj's rule).

## Native (kvmd gives these free — we didn't build them)
🟢 H.264/WebRTC video · HID gadget · MSD · ATX · OLED · EDID engine · VNC · full keymaps ·
video watchdog · ffmpeg fallback · capture auto-detect · main-KVM auth · login rate-limiting ·
session logging · log retention.

## Dropped / retired / out-of-scope
⛔ Virtual media (scope exclusion) · serial console server (scope exclusion) · fan control
(V4 Mini is fanless) · LUKS (superseded by read-only rootfs) · RAM-tmpfs logs (kvmd native) ·
standalone Janus HTTP proxy (dead) · MJPEG as the primary transport (WebRTC won).

## Known gaps / aspirational (never fully existed, incl. in V1)
🟡 Real bidirectional OS clipboard sync (the #1 aspirational gap) · keyboard layouts beyond US ·
full-speed USB cap + aux 3rd HID (deep gadget tweaks) · folding the `/usr/share/kvmd/web`
rebrands into `magic-install.sh` so a fresh flash reproduces the whole face.
