import os, paramiko
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"probe_svc_sandbox_log.txt")
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
log("=== magicbridge-net.service unit (user + sandboxing) ===")
log(run("systemctl cat magicbridge-net 2>&1"))
log("=== what user does it run as (runtime) ===")
log(run("systemctl show magicbridge-net -p User -p ProtectSystem -p ReadWritePaths -p ReadOnlyPaths -p MainPID 2>&1"))
log("=== after rw from ROOT shell, is /etc/systemd/system writable? ===")
log(run("command -v rw >/dev/null && rw; touch /etc/systemd/system/.mbtest 2>&1 && echo WRITABLE && rm -f /etc/systemd/system/.mbtest; command -v ro >/dev/null && ro"))
cli.close(); log("=== done ===")
