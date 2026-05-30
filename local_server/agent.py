#!/usr/bin/env python3
"""Remote Windows Control - Agent
Runs on the remote Windows machine (no public IP needed).
Usage: python agent.py --server http://SERVER_IP:80 --secret YOUR_SECRET
"""

import os
import sys
import json
import time
import base64
import hashlib
import random
import socket
import platform
import subprocess
import tempfile
import argparse

import requests

requests.packages.urllib3.disable_warnings()


class Agent:
    def __init__(self, server_url, secret, interval=5):
        self.server = server_url.rstrip("/")
        self.token = hashlib.sha256(secret.encode()).hexdigest()
        self.interval = interval
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
        })
        self.handlers = {
            "shell": self.handle_shell,
            "screenshot": self.handle_screenshot,
            "download": self.handle_download,
            "upload": self.handle_upload,
            "ps": self.handle_ps,
            "kill": self.handle_kill,
            "sysinfo": self.handle_sysinfo,
        }

    def run(self):
        print(f"[*] Agent started, polling {self.server} every ~{self.interval}s")
        while True:
            try:
                self.poll()
            except requests.ConnectionError:
                print(f"[!] Connection failed, retrying...")
            except Exception as e:
                print(f"[!] Error: {e}")
            jitter = self.interval * (0.7 + random.random() * 0.6)
            time.sleep(jitter)

    def poll(self):
        sysinfo = {
            "hostname": socket.gethostname(),
            "user": os.environ.get("USERNAME", os.environ.get("USER", "?")),
            "os": f"{platform.system()} {platform.release()}",
        }
        resp = self.session.post(f"{self.server}/api/sync", json=sysinfo, timeout=15)
        if resp.status_code != 200:
            print(f"[!] Sync failed: {resp.status_code}")
            return
        data = resp.json()
        for task in data.get("tasks", []):
            self.execute(task)

    def execute(self, task):
        tid = task["id"]
        ttype = task["type"]
        payload = task.get("payload", {})
        print(f"[>] Task {tid}: {ttype}")

        handler = self.handlers.get(ttype)
        if not handler:
            self.report(tid, False, error=f"Unknown task type: {ttype}")
            return

        try:
            result = handler(payload)
            self.report(tid, result.get("success", True),
                        data=result.get("data"), error=result.get("error"))
        except Exception as e:
            self.report(tid, False, error=str(e))

    def report(self, task_id, success, data=None, error=None):
        body = {"task_id": task_id, "success": success, "data": data, "error": error}
        try:
            self.session.post(f"{self.server}/api/report", json=body, timeout=15)
            status = "OK" if success else f"FAIL: {error}"
            print(f"[<] Task {task_id}: {status}")
        except Exception as e:
            print(f"[!] Report failed for {task_id}: {e}")

    # ───── Task Handlers ─────

    def handle_shell(self, payload):
        cmd = payload.get("cmd", "")
        timeout = payload.get("timeout", 120)
        use_powershell = payload.get("powershell", True)

        if use_powershell:
            args = ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd]
        else:
            args = ["cmd", "/c", cmd]

        try:
            proc = subprocess.run(
                args, capture_output=True, text=True, timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return {
                "success": True,
                "data": {
                    "stdout": proc.stdout[-50000:] if len(proc.stdout) > 50000 else proc.stdout,
                    "stderr": proc.stderr[-10000:] if len(proc.stderr) > 10000 else proc.stderr,
                    "exit_code": proc.returncode,
                },
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out after {timeout}s"}

    def handle_screenshot(self, payload):
        tmp = os.path.join(tempfile.gettempdir(), f"scr_{int(time.time())}.png")
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object Drawing.Bitmap $bounds.Width,$bounds.Height
$g = [Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.Location,[Drawing.Point]::Empty,$bounds.Size)
$bmp.Save('{tmp}')
$g.Dispose()
$bmp.Dispose()
"""
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if os.path.exists(tmp):
            with open(tmp, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()
            os.remove(tmp)
            return {"success": True, "data": {"image": img_data}}
        return {"success": False, "error": "Screenshot failed"}

    def handle_download(self, payload):
        """Read a file from this machine and send it back to the controller."""
        path = payload.get("path", "")
        if not os.path.exists(path):
            return {"success": False, "error": f"File not found: {path}"}
        size = os.path.getsize(path)
        if size > 50 * 1024 * 1024:
            return {"success": False, "error": f"File too large: {size} bytes (max 50MB)"}
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return {
            "success": True,
            "data": {
                "filename": os.path.basename(path),
                "file_data": data,
                "size": size,
            },
        }

    def handle_upload(self, payload):
        """Receive file data from controller and write it to this machine."""
        path = payload.get("path", "")
        file_data = payload.get("file_data", "")
        if not path:
            return {"success": False, "error": "No destination path specified"}
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(base64.b64decode(file_data))
        return {"success": True, "data": {"path": path, "size": os.path.getsize(path)}}

    def handle_ps(self, payload):
        cmd = "Get-Process | Select-Object Id,ProcessName,CPU,@{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | ConvertTo-Json -Compress"
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        try:
            processes = json.loads(proc.stdout)
            if isinstance(processes, dict):
                processes = [processes]
        except json.JSONDecodeError:
            processes = proc.stdout
        return {"success": True, "data": {"processes": processes}}

    def handle_kill(self, payload):
        pid = payload.get("pid")
        if not pid:
            return {"success": False, "error": "No PID specified"}
        proc = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return {
            "success": proc.returncode == 0,
            "data": {"stdout": proc.stdout.strip()},
            "error": proc.stderr.strip() if proc.returncode != 0 else None,
        }

    def handle_sysinfo(self, payload):
        cmds = {
            "hostname": "hostname",
            "os_info": "(Get-CimInstance Win32_OperatingSystem).Caption",
            "cpu": "(Get-CimInstance Win32_Processor).Name",
            "ram_gb": "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)",
            "ip_addresses": "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne '127.0.0.1'}).IPAddress -join ', '",
            "uptime": "(New-TimeSpan -Start (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).ToString('d\\.hh\\:mm\\:ss')",
            "disk": "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object { \"$($_.DeviceID) $([math]::Round($_.FreeSpace/1GB,1))/$([math]::Round($_.Size/1GB,1))GB\" }",
            "current_user": "$env:USERNAME",
        }
        info = {}
        for key, cmd in cmds.items():
            try:
                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    capture_output=True, text=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                info[key] = proc.stdout.strip()
            except Exception:
                info[key] = "N/A"
        return {"success": True, "data": info}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Remote Control Agent")
    p.add_argument("--server", required=True, help="Server URL, e.g. http://1.2.3.4:80")
    p.add_argument("--secret", required=True, help="Shared secret (must match server)")
    p.add_argument("--interval", type=int, default=5, help="Poll interval in seconds (default: 5)")
    args = p.parse_args()

    agent = Agent(args.server, args.secret, args.interval)
    agent.run()
