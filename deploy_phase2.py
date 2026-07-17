#!/usr/bin/env python3
"""Deploy Phase 2 (Power page cleanup: MSD + WoL removed, ATX kept w/ honest note)."""
import os
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy_phase2_log.txt")
def log(m):
    open(LOG, "a", encoding="utf-8").write(str(m) + "\n"); print(m)

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
    local = r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\web\index.html"
    remote = "/opt/magicbridge/web/index.html"
    sftp.put(local, remote); sftp.chmod(remote, 0o644)
    ok = os.path.getsize(local) == sftp.stat(remote).st_size
    log("index.html deploy: %s" % ("OK" if ok else "MISMATCH"))
    sftp.close()
    run("command ro 2>/dev/null || true")

    for path in ["https://127.0.0.1/mb/ui/"]:
        rc, out = run("curl -sk -o /dev/null -w '%{http_code}' " + path)
        log("curl %s -> %s" % (path, out))
    cli.close()
    log("=== done ===")
main()
