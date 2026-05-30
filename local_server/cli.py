#!/usr/bin/env python3
"""Remote Windows Control - CLI
Send commands to the server, which queues them for the remote agent.
Usage:
    python cli.py shell "dir C:\\"
    python cli.py screenshot
    python cli.py download "C:\\Users\\user\\file.txt" [local_save_path]
    python cli.py upload local_file.txt "C:\\remote\\dest.txt"
    python cli.py ps
    python cli.py kill 1234
    python cli.py sysinfo
    python cli.py status
    python cli.py history
"""

import os
import sys
import json
import time
import base64
import argparse

import requests

DEFAULT_SERVER = "http://127.0.0.1:80"


def send_task(server, task_type, payload, timeout=60):
    """Create a task and wait for the result."""
    resp = requests.post(f"{server}/ctrl/task", json={"type": task_type, "payload": payload})
    if resp.status_code != 200:
        print(f"[!] Failed to create task: {resp.status_code}")
        return None
    tid = resp.json()["task_id"]
    print(f"[*] Task {tid} created, waiting for agent...")

    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(f"{server}/ctrl/result/{tid}")
        data = resp.json()
        if data.get("result") is not None:
            return data["result"]
        time.sleep(1)

    print(f"[!] Timeout after {timeout}s (agent may not be connected)")
    return None


def cmd_shell(args):
    payload = {"cmd": args.command, "timeout": args.timeout}
    if args.cmd_exe:
        payload["powershell"] = False
    result = send_task(args.server, "shell", payload, timeout=args.timeout + 10)
    if not result:
        return
    data = result.get("data", {})
    if data.get("stdout"):
        print(data["stdout"])
    if data.get("stderr"):
        print(f"[stderr] {data['stderr']}", file=sys.stderr)
    if data.get("exit_code", 0) != 0:
        print(f"[exit code: {data.get('exit_code')}]")
    if result.get("error"):
        print(f"[!] {result['error']}")


def cmd_screenshot(args):
    result = send_task(args.server, "screenshot", {}, timeout=30)
    if not result:
        return
    if not result.get("success"):
        print(f"[!] {result.get('error', 'Failed')}")
        return
    img_data = result["data"]["image"]
    out_path = args.output or f"screenshot_{int(time.time())}.png"
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(img_data))
    print(f"[+] Screenshot saved: {out_path} ({len(img_data)} bytes)")


def cmd_download(args):
    result = send_task(args.server, "download", {"path": args.remote_path}, timeout=120)
    if not result:
        return
    if not result.get("success"):
        print(f"[!] {result.get('error', 'Failed')}")
        return
    data = result["data"]
    local_path = args.local_path or data.get("filename", "downloaded_file")
    with open(local_path, "wb") as f:
        f.write(base64.b64decode(data["file_data"]))
    print(f"[+] Downloaded: {args.remote_path} -> {local_path} ({data['size']} bytes)")


def cmd_upload(args):
    if not os.path.exists(args.local_path):
        print(f"[!] Local file not found: {args.local_path}")
        return
    with open(args.local_path, "rb") as f:
        file_data = base64.b64encode(f.read()).decode()
    payload = {"path": args.remote_path, "file_data": file_data}
    result = send_task(args.server, "upload", payload, timeout=120)
    if not result:
        return
    if result.get("success"):
        print(f"[+] Uploaded: {args.local_path} -> {args.remote_path}")
    else:
        print(f"[!] {result.get('error', 'Failed')}")


def cmd_ps(args):
    result = send_task(args.server, "ps", {}, timeout=30)
    if not result:
        return
    processes = result.get("data", {}).get("processes", [])
    if isinstance(processes, str):
        print(processes)
        return
    print(f"{'PID':>8}  {'CPU':>8}  {'Mem(MB)':>8}  Name")
    print("-" * 50)
    for p in sorted(processes, key=lambda x: x.get("MemMB", 0) or 0, reverse=True)[:50]:
        pid = p.get("Id", "?")
        name = p.get("ProcessName", "?")
        cpu = p.get("CPU")
        mem = p.get("MemMB", 0)
        cpu_str = f"{cpu:.1f}" if cpu else "0.0"
        print(f"{pid:>8}  {cpu_str:>8}  {mem:>8}  {name}")
    if len(processes) > 50:
        print(f"  ... and {len(processes) - 50} more")


def cmd_kill(args):
    result = send_task(args.server, "kill", {"pid": args.pid}, timeout=15)
    if not result:
        return
    if result.get("success"):
        print(f"[+] Process {args.pid} killed")
    else:
        print(f"[!] {result.get('error', 'Failed')}")


def cmd_sysinfo(args):
    result = send_task(args.server, "sysinfo", {}, timeout=30)
    if not result:
        return
    info = result.get("data", {})
    for key, val in info.items():
        print(f"  {key:>15}: {val}")


def cmd_status(args):
    try:
        resp = requests.get(f"{args.server}/ctrl/status")
        data = resp.json()
    except Exception as e:
        print(f"[!] Cannot reach server: {e}")
        return
    agent = data.get("agent", {})
    if not agent:
        print("[!] No agent connected yet")
    else:
        print(f"  Agent: {agent.get('hostname', '?')} ({agent.get('user', '?')})")
        print(f"  OS: {agent.get('os', '?')}")
        print(f"  Last seen: {agent.get('last_seen_ago', 'never')}")
    print(f"  Pending tasks: {data.get('pending', 0)}")
    print(f"  Completed tasks: {data.get('done', 0)}")


def cmd_history(args):
    try:
        resp = requests.get(f"{args.server}/ctrl/history")
        items = resp.json()
    except Exception as e:
        print(f"[!] Cannot reach server: {e}")
        return
    if not items:
        print("No tasks yet.")
        return
    for item in items:
        status_mark = {"done": "+", "pending": ".", "sent": ">"}
        mark = status_mark.get(item["status"], "?")
        preview = item.get("result_preview") or ""
        preview = preview.replace("\n", " ")[:80]
        print(f"  [{mark}] {item['created']} {item['id']} {item['type']:12} {preview}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remote Control CLI")
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"Server URL (default: {DEFAULT_SERVER})")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_shell = sub.add_parser("shell", help="Execute a shell command")
    p_shell.add_argument("command", help="Command to execute")
    p_shell.add_argument("--timeout", type=int, default=120, help="Command timeout (default: 120s)")
    p_shell.add_argument("--cmd-exe", action="store_true", help="Use cmd.exe instead of PowerShell")

    p_ss = sub.add_parser("screenshot", help="Take a screenshot")
    p_ss.add_argument("--output", "-o", help="Output file path")

    p_dl = sub.add_parser("download", help="Download a file from remote")
    p_dl.add_argument("remote_path", help="Remote file path")
    p_dl.add_argument("local_path", nargs="?", help="Local save path (optional)")

    p_ul = sub.add_parser("upload", help="Upload a file to remote")
    p_ul.add_argument("local_path", help="Local file path")
    p_ul.add_argument("remote_path", help="Remote destination path")

    p_ps = sub.add_parser("ps", help="List processes")

    p_kill = sub.add_parser("kill", help="Kill a process")
    p_kill.add_argument("pid", type=int, help="Process ID")

    sub.add_parser("sysinfo", help="Get system information")
    sub.add_parser("status", help="Check agent connection status")
    sub.add_parser("history", help="Show task history")

    args = parser.parse_args()

    handler = {
        "shell": cmd_shell,
        "screenshot": cmd_screenshot,
        "download": cmd_download,
        "upload": cmd_upload,
        "ps": cmd_ps,
        "kill": cmd_kill,
        "sysinfo": cmd_sysinfo,
        "status": cmd_status,
        "history": cmd_history,
    }
    handler[args.cmd](args)
