#!/usr/bin/env python3
"""Remote Windows Control - Server
Runs on your local machine (the one with a public IP).
Usage: python server.py --secret YOUR_SECRET [--port 80]
"""

import os
import uuid
import time
import hashlib
import argparse
from threading import Lock
from flask import Flask, request, jsonify

app = Flask(__name__)

lock = Lock()
tasks = {}
results = {}
agent_info = {}

SECRET = ""


def get_token():
    return hashlib.sha256(SECRET.encode()).hexdigest()


def check_auth():
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    return token == get_token()


def is_local():
    return request.remote_addr in ("127.0.0.1", "::1", "::ffff:127.0.0.1")


# ───── Agent API (remote, requires auth) ─────

@app.route("/api/sync", methods=["POST"])
def sync():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    body = request.json or {}
    with lock:
        agent_info.update({k: v for k, v in body.items() if k != "tasks"})
        agent_info["last_seen"] = time.time()
        pending = [t for t in tasks.values() if t["status"] == "pending"]
        for t in pending:
            t["status"] = "sent"
    return jsonify({"tasks": pending})


@app.route("/api/report", methods=["POST"])
def report():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    body = request.json or {}
    tid = body.get("task_id")
    with lock:
        if tid in tasks:
            tasks[tid]["status"] = "done"
            results[tid] = {
                "success": body.get("success", True),
                "data": body.get("data"),
                "error": body.get("error"),
                "ts": time.time(),
            }
    return jsonify({"ok": True})


# ───── Controller API (localhost only, no auth) ─────

@app.route("/ctrl/task", methods=["POST"])
def create_task():
    if not is_local():
        return "", 403
    body = request.json
    tid = uuid.uuid4().hex[:8]
    with lock:
        tasks[tid] = {
            "id": tid,
            "type": body["type"],
            "payload": body.get("payload", {}),
            "status": "pending",
            "created": time.time(),
        }
    return jsonify({"task_id": tid})


@app.route("/ctrl/result/<tid>")
def get_result(tid):
    if not is_local():
        return "", 403
    with lock:
        return jsonify({"task": tasks.get(tid), "result": results.get(tid)})


@app.route("/ctrl/status")
def status():
    if not is_local():
        return "", 403
    with lock:
        info = dict(agent_info)
        if "last_seen" in info:
            info["last_seen_ago"] = f"{time.time() - info['last_seen']:.0f}s ago"
        return jsonify({
            "agent": info,
            "pending": sum(1 for t in tasks.values() if t["status"] in ("pending", "sent")),
            "done": sum(1 for t in tasks.values() if t["status"] == "done"),
            "total": len(tasks),
        })


@app.route("/ctrl/history")
def history():
    if not is_local():
        return "", 403
    with lock:
        items = []
        for tid, t in sorted(tasks.items(), key=lambda x: x[1]["created"], reverse=True):
            items.append({
                "id": tid,
                "type": t["type"],
                "status": t["status"],
                "created": time.strftime("%H:%M:%S", time.localtime(t["created"])),
                "result_preview": _preview(results.get(tid)),
            })
        return jsonify(items[:50])


def _preview(r):
    if not r:
        return None
    d = r.get("data", {})
    if isinstance(d, dict):
        if "stdout" in d:
            return d["stdout"][:200]
        if "image" in d:
            return f"[screenshot {len(d['image'])} bytes]"
        if "file_data" in d:
            return f"[file {d.get('filename', '?')} {len(d['file_data'])} bytes]"
    return str(d)[:200]


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Remote Control Server")
    p.add_argument("--port", type=int, default=80)
    p.add_argument("--secret", required=True, help="Shared secret for agent auth")
    args = p.parse_args()

    SECRET = args.secret

    print(f"[*] Server: http://0.0.0.0:{args.port}")
    print(f"[*] Auth token: {get_token()}")
    print(f"[*] Agent connect cmd:")
    print(f"    python agent.py --server http://YOUR_PUBLIC_IP:{args.port} --secret {args.secret}")
    print()

    app.run(host="0.0.0.0", port=args.port, threaded=True)
