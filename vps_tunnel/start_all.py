#!/usr/bin/env python3
"""One-click launcher: starts app.py (web panel) and tunnel.py (SSH tunnel).
Run on the remote Windows machine.

Usage: python start_all.py --password YOUR_PASSWORD --vps VPS_IP --vps-pass VPS_SSH_PASSWORD
"""

import subprocess
import sys
import os
import argparse

base = os.path.dirname(os.path.abspath(__file__))

p = argparse.ArgumentParser(description="Start web panel + SSH tunnel")
p.add_argument("--password", default="admin", help="Web panel login password")
p.add_argument("--port", type=int, default=8080, help="Web panel port (default: 8080)")
p.add_argument("--vps", required=True, help="VPS IP address")
p.add_argument("--vps-user", default="root", help="VPS SSH user (default: root)")
p.add_argument("--vps-pass", required=True, help="VPS SSH password")
p.add_argument("--vps-port", type=int, default=9090, help="Port to open on VPS (default: 9090)")
args = p.parse_args()

flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

subprocess.Popen(
    [sys.executable, os.path.join(base, "app.py"),
     "--password", args.password, "--port", str(args.port)],
    creationflags=flags,
)
print(f"[+] Web panel started on :{args.port}")

subprocess.Popen(
    [sys.executable, os.path.join(base, "tunnel.py"),
     "--vps", args.vps, "--vps-user", args.vps_user, "--vps-pass", args.vps_pass,
     "--remote-port", str(args.vps_port), "--local-port", str(args.port)],
    creationflags=flags,
)
print(f"[+] Tunnel started: VPS:{args.vps_port} -> localhost:{args.port}")
print(f"[+] Access from Mac: http://{args.vps}:{args.vps_port}")
