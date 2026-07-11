# MagicBridgeV2 — Feature Map

How MagicBridgeV2 combines **kvmd-native power** with the **MagicBridge add-on layer**.
"Native" = provided by PiKVM/kvmd, exposed through our UI. "Added" = MagicBridge service.

## Powered by kvmd (native — we reuse, never rebuild)
| Feature | How MagicBridgeV2 uses it |
|---|---|
| H.264 / WebRTC + MJPEG video | Live screen panel; "Open full console" opens kvmd's player |
| Keyboard / mouse HID | kvmd HID; our agent + macros type via `/api/hid/print` |
| **Virtual media (MSD)** | Screen tab → mount ISO / boot from virtual USB (`/api/msd`) |
| **ATX power control** | Screen tab → on / off / reset / force-off (`/api/atx`) |
| OLED front panel | Rebranded MagicBridge splash via kvmd-oled override |
| EDID spoofing | kvmd edidconf (native) |
| Wake-on-LAN | kvmd WOL plugin |
| VNC access | kvmd-vnc (bonus, no extra work) |
| GPIO / relays | `kvmd_client.gpio_*` for LEDs, custom channels |
| Full keymaps | kvmd keymaps (fixes V1's US-only gap) |
| System health / Prometheus | `/api/info`; surfaced in System tab |
| Read-only crash-proof OS | PiKVM OS (supersedes V1 RAM-logs / LUKS) |

## Added by MagicBridgeV2 (our services)
| Feature | Service | Endpoint |
|---|---|---|
| USB identity spoofing + presets | magicbridge-stealth | `/mb/stealth/identity` |
| Random serial | magicbridge-stealth | `/mb/stealth/serial/random` |
| USB safe-mode | magicbridge-stealth | `/mb/stealth/safe-mode` |
| AI natural-language agent | magicbridge-agent | `/mb/agent/run` |
| Macro save / run | magicbridge-agent | `/mb/agent/macros` |
| Server-side API keys (fixes V1 gap) | magicbridge-agent | `/mb/agent/config` |
| DuckDNS dynamic DNS | magicbridge-net | `/mb/net/duckdns` |
| Tailscale-only lockdown | magicbridge-net | `/mb/net/lockdown` |
| MAC spoofing (+persist) | magicbridge-net | `/mb/net/mac` |
| Tailscale status | magicbridge-net | `/mb/net/status` |
| Professional rebranded UI | web/ (nginx) | `/mb/ui/` |

## Ports (localhost, behind kvmd nginx :443)
`8410` net · `8411` stealth · `8412` agent · kvmd owns `:443` / streamer / API.
