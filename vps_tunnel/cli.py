#!/usr/bin/env python3
"""CLI for controlling remote Windows through the web panel API.
Runs on Mac (or any machine). Talks to app.py via VPS tunnel.

Usage:
    python cli.py --server http://VPS_IP:9090 --password YOUR_PASSWORD shell "dir C:\\"
    python cli.py screenshot
    python cli.py download "C:\\Users\\user\\file.txt" [local_path]
    python cli.py upload local_file.txt "C:\\remote\\dest.txt"
    python cli.py ps
    python cli.py kill 1234
    python cli.py sysinfo
    python cli.py files "C:\\"
"""

import os
import sys
import json
import base64
import argparse

import requests

SERVER = ""
SESSION = requests.Session()


def login(server, password):
    resp = SESSION.post(f"{server}/login", data={"password": password}, allow_redirects=False)
    if resp.status_code in (302, 200) and "session" in SESSION.cookies.get_dict():
        return True
    resp = SESSION.post(f"{server}/login", json={"password": password})
    return resp.status_code == 200


def cmd_shell(args):
    payload = {"cmd": args.command, "timeout": args.timeout}
    if args.cmd_exe:
        payload["powershell"] = False
    resp = SESSION.post(f"{SERVER}/api/exec", json=payload, timeout=args.timeout + 10)
    data = resp.json()
    if data.get("stdout"):
        print(data["stdout"])
    if data.get("stderr"):
        print(f"[stderr] {data['stderr']}", file=sys.stderr)
    if data.get("exit_code", 0) != 0:
        print(f"[exit code: {data.get('exit_code')}]")


def cmd_screenshot(args):
    resp = SESSION.get(f"{SERVER}/api/screenshot", timeout=30)
    data = resp.json()
    if data.get("error"):
        print(f"[!] {data['error']}")
        return
    out_path = args.output or f"screenshot.png"
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(data["image"]))
    print(f"[+] Screenshot saved: {out_path}")


def cmd_download(args):
    resp = SESSION.get(f"{SERVER}/api/download", params={"path": args.remote_path}, timeout=120, stream=True)
    if resp.status_code != 200:
        print(f"[!] {resp.json().get('error', 'Failed')}")
        return
    cd = resp.headers.get("Content-Disposition", "")
    filename = args.local_path or cd.split("filename=")[-1].strip('"') or "downloaded_file"
    with open(filename, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
    print(f"[+] Downloaded: {args.remote_path} -> {filename}")


def cmd_upload(args):
    if not os.path.exists(args.local_path):
        print(f"[!] Local file not found: {args.local_path}")
        return
    with open(args.local_path, "rb") as f:
        resp = SESSION.post(f"{SERVER}/api/upload",
                            files={"file": (os.path.basename(args.local_path), f)},
                            data={"path": args.remote_path}, timeout=120)
    data = resp.json()
    if data.get("error"):
        print(f"[!] {data['error']}")
    else:
        print(f"[+] Uploaded: {args.local_path} -> {data['path']} ({data['size']} bytes)")


def cmd_ps(args):
    resp = SESSION.get(f"{SERVER}/api/processes", timeout=30)
    processes = resp.json()
    print(f"{'PID':>8}  {'CPU':>8}  {'Mem(MB)':>8}  Name")
    print("-" * 50)
    for p in processes[:50]:
        pid = p.get("Id", "?")
        name = p.get("ProcessName", "?")
        cpu = p.get("CPU")
        mem = p.get("MemMB", 0)
        cpu_str = f"{cpu:.1f}" if cpu else "0.0"
        print(f"{pid:>8}  {cpu_str:>8}  {mem:>8}  {name}")
    if len(processes) > 50:
        print(f"  ... and {len(processes) - 50} more")


def cmd_kill(args):
    resp = SESSION.post(f"{SERVER}/api/kill", json={"pid": args.pid}, timeout=15)
    data = resp.json()
    if data.get("ok"):
        print(f"[+] Process {args.pid} killed")
    else:
        print(f"[!] {data.get('msg', 'Failed')}")


def cmd_sysinfo(args):
    resp = SESSION.get(f"{SERVER}/api/sysinfo", timeout=30)
    for key, val in resp.json().items():
        print(f"  {key:>15}: {val}")


def cmd_files(args):
    resp = SESSION.get(f"{SERVER}/api/files", params={"path": args.path}, timeout=15)
    data = resp.json()
    if data.get("error"):
        print(f"[!] {data['error']}")
        return
    print(f"  Path: {data['path']}\n")
    for e in data["entries"]:
        kind = "DIR " if e["is_dir"] else "FILE"
        size = "" if e["is_dir"] else f"{e['size']:>10}"
        print(f"  [{kind}] {size}  {e['mtime']}  {e['name']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remote Control CLI (via VPS)")
    parser.add_argument("--server", default=os.environ.get("REMOTE_SERVER", "http://127.0.0.1:9090"),
                        help="Web panel URL (default: $REMOTE_SERVER or http://127.0.0.1:9090)")
    parser.add_argument("--password", default=os.environ.get("REMOTE_PASSWORD", "admin"),
                        help="Web panel password (default: $REMOTE_PASSWORD or admin)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_shell = sub.add_parser("shell", help="Execute a shell command")
    p_shell.add_argument("command", help="Command to execute")
    p_shell.add_argument("--timeout", type=int, default=120)
    p_shell.add_argument("--cmd-exe", action="store_true", help="Use cmd.exe instead of PowerShell")

    p_ss = sub.add_parser("screenshot", help="Take a screenshot")
    p_ss.add_argument("--output", "-o", help="Output file path")

    p_dl = sub.add_parser("download", help="Download file from remote")
    p_dl.add_argument("remote_path", help="Remote file path")
    p_dl.add_argument("local_path", nargs="?", help="Local save path")

    p_ul = sub.add_parser("upload", help="Upload file to remote")
    p_ul.add_argument("local_path", help="Local file path")
    p_ul.add_argument("remote_path", help="Remote destination path")

    p_ps = sub.add_parser("ps", help="List processes")

    p_kill = sub.add_parser("kill", help="Kill a process")
    p_kill.add_argument("pid", type=int, help="Process ID")

    sub.add_parser("sysinfo", help="System information")

    p_files = sub.add_parser("files", help="List directory contents")
    p_files.add_argument("path", nargs="?", default="C:\\", help="Directory path")

    args = parser.parse_args()
    SERVER = args.server

    if not login(SERVER, args.password):
        print("[!] Login failed")
        sys.exit(1)

    handler = {
        "shell": cmd_shell, "screenshot": cmd_screenshot,
        "download": cmd_download, "upload": cmd_upload,
        "ps": cmd_ps, "kill": cmd_kill, "sysinfo": cmd_sysinfo,
        "files": cmd_files,
    }
    handler[args.cmd](args)
