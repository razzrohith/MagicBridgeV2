import os, paramiko
LOG=os.path.join(os.path.dirname(os.path.abspath(__file__)),"probe_edid_flags_log.txt")
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
log("=== kvmd-edidconf --help (all flags) ===")
log(run("kvmd-edidconf --help 2>&1"))
log("=== does kvmd-otg default serial come from a config? grep CAFEBABE ===")
log(run("grep -rn 'CAFEBABE' /usr/lib/python*/site-packages/kvmd/ 2>/dev/null | head; grep -rn 'CAFEBABE' /etc/kvmd/ 2>/dev/null | head"))
log("=== kvmd otg config default serial ===")
log(run("python3 -c \"import yaml,glob; \nimport subprocess; print(subprocess.run(['grep','-rn','serial','/usr/lib/python3.13/site-packages/kvmd/apps/otg/'],capture_output=True,text=True).stdout[:1500])\" 2>&1 | head -20"))
cli.close(); log("=== done ===")
