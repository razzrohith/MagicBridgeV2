import os, paramiko, time
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"test_vnc2_log.txt")
def log(m): open(LOG,"a",encoding="utf-8").write(str(m)+"\n"); print(m)
open(LOG,"w").close()
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("192.168.1.37", username="root", password="root", timeout=15, allow_agent=False, look_for_keys=False)
def run(cmd,t=30):
    ch=cli.get_transport().open_session(); ch.settimeout(t); ch.exec_command(cmd)
    out=b""
    while True:
        d=ch.recv(65535)
        if not d: break
        out+=d
    return out.decode(errors="replace").strip()
run("command rw 2>/dev/null || mount -o remount,rw /")
sftp=cli.open_sftp()
sftp.put(r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2\services\magicbridge-net\app.py","/opt/magicbridge/services/magicbridge-net/app.py")
sftp.chmod("/opt/magicbridge/services/magicbridge-net/app.py",0o644); sftp.close()
run("command ro 2>/dev/null || true")
log("restart net: "+run("systemctl restart magicbridge-net && sleep 1 && systemctl is-active magicbridge-net"))

log("=== VNC ON via endpoint ===")
log(run("curl -s -X POST http://127.0.0.1:8410/vnc -H 'Content-Type: application/json' -d '{\"on\":true}'", t=35))
time.sleep(2)
log("active: "+run("systemctl is-active kvmd-vnc"))
log("listening :5900: "+run("ss -lntp 2>/dev/null | grep ':5900' || echo NO"))
log("boot symlink present: "+run("ls -la /etc/systemd/system/multi-user.target.wants/kvmd-vnc.service 2>&1"))
log("rootfs ro again: "+run("mount | grep 'on / ' | grep -o 'ro,\\|rw,'"))
log("=== VNC status endpoint ===")
log(run("curl -s http://127.0.0.1:8410/vnc"))
log("=== VNC OFF via endpoint (leave it off as default) ===")
log(run("curl -s -X POST http://127.0.0.1:8410/vnc -H 'Content-Type: application/json' -d '{\"on\":false}'", t=35))
time.sleep(1)
log("active after off: "+run("systemctl is-active kvmd-vnc"))
log("boot symlink after off: "+run("ls /etc/systemd/system/multi-user.target.wants/kvmd-vnc.service 2>&1 || echo REMOVED"))
cli.close(); log("=== done ===")
