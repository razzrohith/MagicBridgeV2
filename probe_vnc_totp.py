import os, paramiko
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"probe_vnc_totp_log.txt")
def log(m): open(LOG,"a",encoding="utf-8").write(str(m)+"\n"); print(m)
open(LOG,"w").close()
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("192.168.1.37", username="root", password="root", timeout=15, allow_agent=False, look_for_keys=False)
def run(cmd,t=25):
    ch=cli.get_transport().open_session(); ch.settimeout(t); ch.exec_command(cmd)
    out=b""
    while True:
        d=ch.recv(65535)
        if not d: break
        out+=d
    return out.decode(errors="replace").strip()

log("=== TOTP: how does kvmd auth read it? ===")
log("totp.secret exists: "+run("ls -la /etc/kvmd/totp.secret 2>&1"))
log("kvmd auth totp config: "+run("grep -rn 'totp\\|secret_file' /etc/kvmd/*.yaml /usr/share/kvmd/configs.default/kvmd/*.yaml 2>/dev/null | head"))
log("kvmd auth internal scheme (where totp path is defaulted): "+run("grep -rn -A2 'totp' /usr/lib/python3*/site-packages/kvmd/apps/__init__.py /usr/lib/python3*/site-packages/kvmd/plugins/auth/*.py 2>/dev/null | head -25"))
log("=== VNC: package + config + auth ===")
log("kvmd-vnc unit: "+run("systemctl cat kvmd-vnc 2>&1 | head -20"))
log("vnc config exists: "+run("ls -la /etc/kvmd/vnc* 2>&1; ls /etc/kvmd/vnc/ 2>&1"))
log("vnc passwd / vncpasswd: "+run("ls -la /etc/kvmd/vncpasswd 2>&1; command -v kvmd-vnc-passwd 2>&1"))
log("current vnc status: "+run("systemctl is-active kvmd-vnc 2>&1; systemctl is-enabled kvmd-vnc 2>&1"))
log("vnc recent errors (if any): "+run("journalctl -u kvmd-vnc -n 12 --no-pager -o cat 2>&1 | tail -12"))
cli.close(); log("=== done ===")
