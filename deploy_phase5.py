import os, paramiko
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"deploy_phase5_log.txt")
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

BASE=r"C:\Users\razzr\Claude\Projects\MagicBridge\MagicBridgeV2"
FILES=[
    (BASE+r"\services\magicbridge-net\app.py","/opt/magicbridge/services/magicbridge-net/app.py"),
    (BASE+r"\web\index.html","/opt/magicbridge/web/index.html"),
]
run("command rw 2>/dev/null || mount -o remount,rw /")
sftp=cli.open_sftp()
ok=True
for local,remote in FILES:
    sftp.put(local,remote); sftp.chmod(remote,0o644)
    m=os.path.getsize(local)==sftp.stat(remote).st_size
    log("%s : %s"%(remote,"OK" if m else "MISMATCH")); ok=ok and m
sftp.close()
run("command ro 2>/dev/null || true")
log("deploy ok: %s"%ok)
log("net syntax: "+run("python3 -c \"compile(open('/opt/magicbridge/services/magicbridge-net/app.py').read(),'x','exec')\" 2>&1 && echo CLEAN"))
log("restart net: "+run("systemctl restart magicbridge-net && sleep 1 && systemctl is-active magicbridge-net"))

log("=== test /net/latency (WiFi quality + gateway RTT) ===")
log(run("curl -s http://127.0.0.1:8410/latency"))
log("=== test /net/clients (who's viewing the console) ===")
log(run("curl -s http://127.0.0.1:8410/clients"))
log("=== test /net/tailscale/peers ===")
log(run("curl -s http://127.0.0.1:8410/tailscale/peers"))
cli.close(); log("=== done ===")
