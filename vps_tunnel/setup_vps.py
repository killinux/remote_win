#!/usr/bin/env python3
"""One-time VPS setup: enable SSH GatewayPorts + nginx reverse proxy.
Run from any machine that can SSH to the VPS.

Usage: python setup_vps.py --host VPS_IP --password VPS_SSH_PASSWORD [--tunnel-port 9090] [--nginx-port 8081]
"""

import argparse
import paramiko
import time


def run(ssh, cmd, timeout=30):
    print(f">>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}")
    return out


def main():
    p = argparse.ArgumentParser(description="Setup VPS for SSH reverse tunnel")
    p.add_argument("--host", required=True, help="VPS IP address")
    p.add_argument("--user", default="root", help="SSH user (default: root)")
    p.add_argument("--password", required=True, help="SSH password")
    p.add_argument("--tunnel-port", type=int, default=9090, help="Tunnel port on VPS (default: 9090)")
    p.add_argument("--nginx-port", type=int, default=8081, help="Nginx proxy port (default: 8081)")
    args = p.parse_args()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(args.host, username=args.user, password=args.password, timeout=10)
    print(f"[+] Connected to {args.host}\n")

    # 1. Enable GatewayPorts
    run(ssh, "grep -q '^GatewayPorts' /etc/ssh/sshd_config "
            "&& sed -i 's/^GatewayPorts.*/GatewayPorts yes/' /etc/ssh/sshd_config "
            "|| echo 'GatewayPorts yes' >> /etc/ssh/sshd_config")
    run(ssh, "systemctl restart sshd")
    print("[+] sshd: GatewayPorts enabled\n")

    # 2. Firewall
    run(ssh, f"firewall-cmd --permanent --add-port={args.tunnel_port}/tcp "
            f"--add-port={args.nginx_port}/tcp 2>/dev/null; "
            "firewall-cmd --reload 2>/dev/null; echo 'firewall ok'")

    # 3. Nginx reverse proxy (optional)
    run(ssh, "which nginx >/dev/null 2>&1 && echo 'nginx found' || echo 'nginx not installed'")
    nginx_conf = f"""server {{
    listen {args.nginx_port};
    server_name _;
    location / {{
        proxy_pass http://127.0.0.1:{args.tunnel_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }}
}}"""
    run(ssh, f"cat > /etc/nginx/conf.d/tunnel.conf << 'EOF'\n{nginx_conf}\nEOF")
    run(ssh, "nginx -t 2>&1 && systemctl reload nginx && echo 'nginx ok' || echo 'nginx skip'")

    print(f"\n{'='*50}")
    print(f"[+] VPS ready!")
    print(f"[+] Direct access:  http://{args.host}:{args.tunnel_port}")
    print(f"[+] Via nginx:      http://{args.host}:{args.nginx_port}")
    print(f"\n[+] On remote Windows, run:")
    print(f"    python start_all.py --vps {args.host} --vps-pass {args.password} --password YOUR_WEB_PASSWORD")

    ssh.close()


if __name__ == "__main__":
    main()
