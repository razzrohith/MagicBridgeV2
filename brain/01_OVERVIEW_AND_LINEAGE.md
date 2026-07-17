# 01 — Overview & Lineage

## What MagicBridge is

MagicBridge is a **self-hosted KVM-over-IP appliance**: a small box you plug into a target
computer's HDMI + USB (+ optionally its ATX power header). From any browser you then see the
target's screen and control its keyboard and mouse over the network, as if you were sitting
at it — even while it's in BIOS, booting, or with no OS.

But a plain KVM is a commodity. **MagicBridge's actual identity is its stealth / anonymity /
spoofing suite**: to the target machine and the network, the bridge presents itself as
ordinary, realistic hardware (a real Logitech receiver, a real Dell monitor, a spoofable
MAC) with **zero fingerprints** that reveal it's a KVM, a Raspberry Pi, or a PiKVM. That,
plus quality-of-life touches (human-like typing on paste, mouse jiggler, quick clips), is the
"soul" of the product. If you ever find yourself building a generic KVM cockpit, you've lost
the plot — re-read this.

**Owner / vendor:** Raj (razzrohith on GitHub). It's his personal product, used to remotely
control his own laptops. Local-first, privacy-leaning; he's wary of cloud phone-home.

---

## The lineage (how we got here)

Think of it as five generations. The names "RazzBridge" and "V3" are informal labels for
phases; the shipping product name has been **MagicBridge** (V1) and **MagicBridgeV2** (V2+).

### Gen 0 — TinyPilot / PiKVM (the inspiration)
The whole category comes from open-source KVM-over-IP projects: **TinyPilot** (Voyager 3) and
**PiKVM**. Early design decisions were made by comparing against these. Two of their
enterprise features were **deliberately excluded** from MagicBridge's scope (see
`brain/04_FEATURES.md`): **virtual media** (mounting an ISO as a fake USB drive) and
**serial console server**. Raj considered these IT-recovery features irrelevant to his
single-target personal use. *(Note: virtual media later became available for free once we
moved to kvmd, but Raj still doesn't want it surfaced.)*

### Gen 1 — MagicBridge V1 ("the Pi 4 project", a.k.a. RazzBridge era)
A **DIY KVM hand-built on a Raspberry Pi 4** running Debian/Raspberry Pi OS. This is the
original MagicBridge and where the soul was forged. Key facts:
- **Video:** started with a **MacroSilicon MS2109 USB HDMI dongle** streaming **MJPEG over
  HTTP** via ustreamer/nginx. This was capped at ~5 fps and got progressively laggier the
  longer you used it (MJPEG-over-TCP has no frame-dropping, so backlog compounds).
- **Video upgrade (2026-07-05):** swapped to a **CSI capture board (C790 / TC358743)** +
  **Janus WebRTC / H.264**, modeled on PiKVM/TinyPilot. This retired the whole MJPEG-lag
  saga. Transport dropdown defaulted to "WebRTC (C790/CSI) ★" with MJPEG as fallback.
- **The stealth suite lived here:** USB identity spoofing (VID/PID/serial/manufacturer, with
  "verified" preset flags like Logitech Unifying as default), MAC spoofing with reboot
  persistence, safe-mode, EDID cloning, mouse jiggler presets, Escape hold-to-exit, human
  typing jitter on paste, clips, macros, a hidden AI agent, an update indicator.
- **Look:** a distinctive **cyberpunk cyan (#00e5ff) / violet (#b026ff) HUD** for the stealth
  panel; the main app used a muted graphite theme.
- **Software:** two big Python apps — `magicbridge.py` (the main KVM app, ~Flask) and
  `stealth-dashboard.py` (the stealth panel, grew to 2200+ lines) — plus `oled.py`,
  `mb-provision.sh` (WiFi AP-failover captive portal for onboarding at new locations),
  mDNS aliases, RAM-only logs, LUKS-encrypted config, fan control.
- **Ops model:** everything was deployed by ad-hoc `mb_*.py` paramiko scripts run from the
  Windows File Explorer address bar; git came later (repo github.com/razzrohith/MagicBridge,
  reconciled 2026-07-09 at commit 13246c7).

### Gen 2 — The migration decision (2026-07-11)
Raj considered moving to the **official PiKVM V4 Mini** (a polished CM4-based KVM box). A
full 16-page migration plan + 67-feature matrix were produced. Conclusion: **Hybrid
strategy** — keep PiKVM's excellent native kvmd core (video/HID/MSD/ATX/OLED/EDID/WOL/VNC/
keymaps) and **re-implement only MagicBridge's unique layer** (stealth spoofing, AI agent,
network toolkit) as add-on services. Moving to the V4 Mini instantly solved 3 long-blocked
V1 items — WebRTC/H.264, OLED, EDID spoofing — all native on the new hardware.

### Gen 3 — MagicBridgeV2 (the current product, 2026-07-11 → now)
The chosen strategy became **"fork + rebrand"**: build **on top of the stock PiKVM OS**, keep
kvmd untouched underneath, and layer MagicBridge on top so it feels like Raj's own product/OS
— not a visible patch. Legal because kvmd/ustreamer are GPLv3 (we ship under GPLv3 with
attribution in `NOTICE`).
- **Repo:** github.com/razzrohith/MagicBridgeV2 (separate from V1's repo).
- **Install model:** flash official PiKVM OS → one command `magic-install.sh` rebrands +
  installs the add-on layer.
- Built across ~6 internal phases (base install, own KVM core in our UI, full management
  surface, deferred features, soul-restore, hardening) plus a late 6-phase polish pass. See
  the debug journal and tracker for the blow-by-blow.

### Gen "V3" — informal name for the current PiKVM-hardware build
When Raj says "let's call this MagicBridgeV2 (PiKVM hardware) / MagicBridgeV3", he means the
**same MagicBridgeV2 codebase running on the real V4 Mini** — i.e. *right now*. There is no
separate V3 codebase yet; it's a label for "the current, hardware-validated state." If a true
V3 is ever started (e.g. a from-source custom PiKVM OS image with MagicBridge baked in — an
idea Raj has floated), it would get its own repo/plan.

---

## Where things physically live (dev side)

| Thing | Location |
|-------|----------|
| **Edit here** (Cowork-mounted build folder, source of truth for edits) | `C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\` |
| **Git repo** (canonical, pushes to GitHub) | `E:\Startup\MagicbridgeV2\` |
| **GitHub remote** | github.com/razzrohith/MagicBridgeV2 (branch `main`) |
| **On the Pi** (deployed services + UI) | `/opt/magicbridge/` |
| **On the Pi** (kvmd config we also touch) | `/etc/kvmd/` (override.d, nginx, totp, vnc) |
| V1 (old) reference source | `MAGICBRIDGE_HANDBOOK.md` + `pi_source/` in the Projects\MagicBridge parent folder |

⚠️ The build folder is **NOT a git repo**. Editing there and only SFTP-deploying leaves git
behind. Always run `sync_and_push.py` after changes. See `brain/06_DEPLOY_RUNBOOK.md`.
