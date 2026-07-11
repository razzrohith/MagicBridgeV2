# MagicBridgeV2 — Porting / Merge Tracker

Living checklist for merging MagicBridge V1 features onto the kvmd base, "one by one".
Legend: ☐ todo · ◐ in progress · ☑ done · ⊘ dropped (kvmd covers it / obsolete)

## Native — adopt kvmd, delete V1 code
- ⊘ Video transport / H.264 / WebRTC / capture  → kvmd + ustreamer (native on V4 Mini)
- ⊘ HID keyboard/mouse, on-screen keyboard, paste  → kvmd-hid
- ⊘ MSD virtual drive, ATX power, reboot/shutdown  → kvmd (new capability)
- ⊘ OLED, EDID spoofing, WOL, mouse jiggler, keymaps  → kvmd (native)
- ⊘ RAM-only logs, LUKS  → superseded by PiKVM read-only rootfs

## Port — MagicBridge add-on layer (services/)
- ◐ magicbridge-stealth  — USB identity switch, safe-mode, custom fields, random serial  (CODE DONE; hw-validate gadget rebuild)
- ◐ magicbridge-agent    — AI natural-language runner + macros (keys server-side)  (CODE DONE; hw-validate key events)
- ◐ magicbridge-net      — DuckDNS✓, lockdown✓, MAC✓; Tailscale/Funnel/WiFi wrappers TODO
- ☑ magicbridge-common   — mbcommon.py + kvmd_client.py (ATX/MSD/HID/GPIO/streamer/info)

## Redesign
- ◐ Web UI  → professional MagicBridgeV2 cockpit in web/index.html (kvmd + our APIs)  (BUILT; served at /mb/ui/)
- ☐ Auth    → reconcile with kvmd-auth; our panel uses kvmd session where possible
- ☐ Config backup/restore  → target /etc/kvmd/override.d + our config
- ☐ Update channel  → OS via pikvm-update; our layer via magic-install.sh --update

## Rebranding (branding/ + magic-install.sh)
- ☐ Hostname + mDNS aliases
- ☐ OLED splash text/logo
- ☐ Web UI title / favicon / logo / theme
- ☐ MOTD / SSH banner
- ☐ nginx server_name + cert CN/SAN

## Known risks (from the migration plan)
- USB identity live-switch fights kvmd's static gadget + read-only FS → prototype first on real HW.
- Full-speed USB cap may break MSD (needs high-speed) → keep optional/off.
- Keeping our own UI is the biggest single chunk → build against kvmd's documented API.

## Hardware validation (once V4 Mini arrives — TODAY)
- ☐ Flash official PiKVM OS, first boot, confirm native KVM works
- ☐ Run magic-install.sh, confirm rebrand + services up
- ☐ Verify capture (TC358743), OLED, ATX, MSD end-to-end
- ☐ Validate each ported service against live kvmd
