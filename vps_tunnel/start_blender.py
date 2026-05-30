#!/usr/bin/env python3
"""Start SSH tunnel for Blender MCP (port 9876).
Run on the remote Windows machine alongside start_all.py.

Usage: python start_blender.py --vps 49.233.189.223 --vps-pass YOUR_VPS_PASSWORD

Then on Mac, add to ~/.claude/settings.json:
{
  "mcpServers": {
    "blender": {
      "command": "python3",
      "args": ["<path>/blender_mcp_bridge.py", "--host", "49.233.189.223", "--port", "9876"]
    }
  }
}
"""

import subprocess
import sys
import os
import argparse

base = os.path.dirname(os.path.abspath(__file__))

p = argparse.ArgumentParser(description="Start Blender MCP tunnel")
p.add_argument("--vps", required=True, help="VPS IP address")
p.add_argument("--vps-user", default="root")
p.add_argument("--vps-pass", required=True, help="VPS SSH password")
p.add_argument("--blender-port", type=int, default=9876, help="Blender MCP port (default: 9876)")
p.add_argument("--vps-port", type=int, default=9876, help="Port on VPS (default: 9876)")
args = p.parse_args()

flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

subprocess.Popen(
    [sys.executable, os.path.join(base, "tunnel.py"),
     "--vps", args.vps, "--vps-user", args.vps_user, "--vps-pass", args.vps_pass,
     "--remote-port", str(args.vps_port), "--local-port", str(args.blender_port)],
    creationflags=flags,
)
print(f"[+] Blender MCP tunnel: VPS:{args.vps_port} -> localhost:{args.blender_port}")
print(f"[+] Mac Claude MCP: python3 blender_mcp_bridge.py --host {args.vps} --port {args.vps_port}")
