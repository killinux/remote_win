---
name: remote-win
description: Control the remote Windows machine via VPS tunnel. Use when the user wants to run commands, take screenshots, browse files, or manage processes on the remote Windows.
---

# Remote Windows Control

This project provides a VPS tunnel setup to control a remote Windows machine from Mac.

## Architecture

```
Mac (CLI/Browser) --HTTP--> VPS (49.233.189.223:9090) <--SSH Reverse Tunnel-- Remote Windows (app.py :8080)
```

## Quick Start

All CLI commands run from `vps_tunnel/` directory:

```bash
cd vps_tunnel
python3 cli.py --server http://49.233.189.223:9090 --password haoning <command>
```

## Available Commands

| Command | Example | Description |
|---------|---------|-------------|
| `shell` | `shell "dir C:\\"` | Execute PowerShell command (add `--cmd-exe` for cmd.exe) |
| `screenshot` | `screenshot -o screen.png` | Take a screenshot of the remote desktop |
| `files` | `files "C:\\Users"` | List directory contents |
| `download` | `download "C:\\path\\file.txt" local.txt` | Download a file from remote |
| `upload` | `upload local.txt "C:\\path\\dest.txt"` | Upload a file to remote |
| `ps` | `ps` | List running processes |
| `kill` | `kill 1234` | Kill a process by PID |
| `sysinfo` | `sysinfo` | Show system information |

## Remote Machine Specs

- **OS**: Windows 11
- **CPU**: Intel i9-14900HX
- **GPU**: NVIDIA RTX 4090 Laptop
- **RAM**: 64GB
- **Hostname**: killinux

## Browser Access

Open http://49.233.189.223:9090 in a browser, password: `haoning`. The web panel has tabs for Terminal, Files, Processes, and System.

## Blender MCP

Remote Blender is accessible via MCP (configured in `.mcp.json`). The bridge (`blender_mcp_bridge.py`) translates MCP stdio protocol to Blender's TCP socket protocol via VPS tunnel.

- Blender addon uses TCP socket on port 9876 (not HTTP SSE)
- Bridge connects: Mac -> VPS:9876 -> Remote Windows Blender:9876
- Available MCP tools: `send_code_to_blender`, `get_scene_info`, `test_connection`

Blender MCP requires the addon's "Start MCP Server" button to be clicked in Blender UI first.

## Troubleshooting

If connection fails, the remote Windows may need to restart `start_all.py`:
```
python start_all.py --vps 49.233.189.223 --vps-pass haoning --password haoning
```
