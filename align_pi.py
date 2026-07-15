#!/usr/bin/env python3
r"""Align the Pi's /opt/magicbridge git tree with GitHub (origin/main).
Files already match from the SFTP deploy; this just makes the tree clean so
future git pulls work. Run:
  cmd /c python C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\align_pi.py
Check align_pi_log.txt
"""
import os
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "align_pi_log.txt")
def log(m):
    open(LOG, "a", encoding="utf-8").write(str(m) + "\n"); print(m)
def main():
    open(LOG, "w").close()
    import paramiko
    cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect("172.16.20.209", username="root", password="root", timeout=15,
                allow_agent=False, look_for_keys=False)
    def run(cmd, t=60):
        ch = cli.get_transport().open_session(); ch.settimeout(t); ch.exec_command(cmd)
        out = b""
        while True:
            d = ch.recv(65535)
            if not d: break
            out += d
        return ch.recv_exit_status(), out.decode(errors="replace").strip()
    rc, o = run("git -C /opt/magicbridge log -1 --oneline"); log("Pi HEAD before: " + o)
    run("command -v rw >/dev/null && rw || mount -o remount,rw /")
    rc, o = run("cd /opt/magicbridge && git fetch origin main 2>&1 && git reset --hard origin/main 2>&1")
    log("fetch+reset:\n" + o)
    run("command -v ro >/dev/null && ro || mount -o remount,ro /")
    rc, o = run("git -C /opt/magicbridge log -1 --oneline"); log("Pi HEAD after: " + o)
    rc, o = run("git -C /opt/magicbridge status --short"); log("Pi tree status: " + (o or "(clean)"))
    rc, o = run("systemctl is-active kvmd kvmd-nginx magicbridge-net"); log("services: " + o.replace("\n", " "))
    cli.close(); log("=== done ===")
main()
