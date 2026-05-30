#!/usr/bin/env python3
"""MCP stdio bridge for remote Blender.
Run on Mac. Connects to Blender's TCP socket via VPS tunnel,
exposes it as a stdio MCP server for Claude.

Usage in ~/.claude/settings.json:
{
  "mcpServers": {
    "blender": {
      "command": "python3",
      "args": ["/path/to/blender_mcp_bridge.py", "--host", "49.233.189.223", "--port", "9876"]
    }
  }
}
"""

import sys
import json
import socket
import argparse

BLENDER_HOST = "49.233.189.223"
BLENDER_PORT = 9876


def send_to_blender(host, port, message, timeout=30):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    sock.sendall(json.dumps(message).encode())
    buf = b""
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            json.loads(buf)
            break
        except json.JSONDecodeError:
            continue
        except socket.timeout:
            break
    sock.close()
    return json.loads(buf) if buf else {"error": "No response"}


def handle_initialize(req_id):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "blender-remote", "version": "1.0.0"},
        },
    }


def handle_tools_list(req_id):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": [
                {
                    "name": "send_code_to_blender",
                    "description": "Execute Python code in remote Blender. Use bpy module to manipulate scenes, objects, materials, etc.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python code to execute in Blender",
                            }
                        },
                        "required": ["code"],
                    },
                },
                {
                    "name": "get_scene_info",
                    "description": "Get current Blender scene information including objects, materials, and hierarchy.",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "test_connection",
                    "description": "Test connection to remote Blender.",
                    "inputSchema": {"type": "object", "properties": {}},
                },
            ]
        },
    }


def handle_tool_call(req_id, name, args):
    try:
        if name == "send_code_to_blender":
            resp = send_to_blender(
                BLENDER_HOST,
                BLENDER_PORT,
                {"type": "code", "code": args.get("code", "")},
            )
            text = f"Blender response:\n{json.dumps(resp, indent=2, ensure_ascii=False)}"
        elif name == "get_scene_info":
            resp = send_to_blender(
                BLENDER_HOST, BLENDER_PORT, {"type": "get_scene_info"}
            )
            text = f"Scene info:\n{json.dumps(resp, indent=2, ensure_ascii=False)}"
        elif name == "test_connection":
            resp = send_to_blender(
                BLENDER_HOST,
                BLENDER_PORT,
                {"type": "code", "code": 'print("Hello from Claude!")'},
            )
            text = f"Connection OK!\n{json.dumps(resp, indent=2, ensure_ascii=False)}"
        else:
            text = f"Unknown tool: {name}"
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": text}]},
        }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            },
        }


def main():
    global BLENDER_HOST, BLENDER_PORT
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=BLENDER_HOST)
    p.add_argument("--port", type=int, default=BLENDER_PORT)
    args = p.parse_args()
    BLENDER_HOST = args.host
    BLENDER_PORT = args.port

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method", "")
        req_id = req.get("id")

        if method == "initialize":
            resp = handle_initialize(req_id)
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            resp = handle_tools_list(req_id)
        elif method == "tools/call":
            params = req.get("params", {})
            resp = handle_tool_call(
                req_id, params.get("name", ""), params.get("arguments", {})
            )
        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            }

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
