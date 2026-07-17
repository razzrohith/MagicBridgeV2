#!/usr/bin/env python3
"""Deploy Phase 1 UI redesign (glass theme, hidden Stealth link, custom login page)
to the Pi over SFTP. Pi is reachable now at 192.168.1.37 (WiFi provisioning fixed).
Run: cmd /c python C:\\Users\\razzr\\Claude\\Projects\\MagicBridge\\MagicBridgeV2\\deploy_phase1_ui.py
"""
import os
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy_phase1_ui_log.txt")
def log(m):
    open(LOG, "a", encoding="utf-8").write(str(m) + "\n"); print(m)

BASE = r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2"
FILES = [
    (BASE + r"\web\index.html", "/opt/magicbridge/web/index.html"),
    (BASE + r"\web\stealth\index.html", "/opt/magicbridge/web/stealth/index.html"),
    (BASE + r"\web\login_index.html", "/usr/share/kvmd/web/login/index.html"),
]

def main():
    open(LOG, "w").close()
    import paramiko
    cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect("192.168.1.37", username="root", password="root", timeout=15,
                allow_agent=False, look_for_keys=False)
    def run(cmd, t=20):
        ch = cli.get_transport().open_session(); ch.settimeout(t); ch.exec_command(cmd)
        out = b""
        while True:
            d = ch.recv(65535)
            if not d: break
            out += d
        return ch.recv_exit_status(), out.decode(errors="replace").strip()

    run("command rw 2>/dev/null || mount -o remount,rw /")
    sftp = cli.open_sftp()
    ok = True
    for local, remote in FILES:
        try:
            size_local = os.path.getsize(local)
            sftp.put(local, remote)
            sftp.chmod(remote, 0o644)
            size_remote = sftp.stat(remote).st_size
            match = size_local == size_remote
            log("%s -> %s : local=%d remote=%d %s" % (local, remote, size_local, size_remote, "OK" if match else "MISMATCH"))
            ok = ok and match
        except Exception as e:
            log("FAIL %s -> %s : %s" % (local, remote, e))
            ok = False
    sftp.close()
    run("command ro 2>/dev/null || true")
    log("deploy ok: %s" % ok)

    # quick sanity: nginx still healthy, pages return 200
    rc, out = run("nginx -t 2>&1 | tail -3")
    log("nginx -t: " + out)
    for path in ["https://127.0.0.1/login/", "https://127.0.0.1/mb/ui/", "https://127.0.0.1/stealth/"]:
        rc, out = run("curl -sk -o /dev/null -w '%{http_code}' " + path)
        log("curl %s -> %s" % (path, out))
    cli.close()
    log("=== done ===")

main()
