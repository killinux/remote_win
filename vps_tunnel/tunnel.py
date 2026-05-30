#!/usr/bin/env python3
"""SSH reverse tunnel — run on the remote Windows machine.
Forwards VPS_PORT on the VPS to LOCAL_PORT on this machine.

Usage: python tunnel.py --vps 49.233.189.223 --vps-pass haoning --remote-port 8080 --local-port 8080
Then http://49.233.189.223:8080 will reach this machine's port 8080.
"""

import argparse
import select
import socket
import threading
import time
import paramiko


def reverse_forward_tunnel(server_port, local_host, local_port, transport):
    transport.request_port_forward("", server_port)
    print(f"[+] Reverse tunnel active: VPS:{server_port} -> localhost:{local_port}")
    while transport.is_active():
        chan = transport.accept(1)
        if chan is None:
            continue
        t = threading.Thread(target=handler, args=(chan, local_host, local_port), daemon=True)
        t.start()


def handler(chan, host, port):
    try:
        sock = socket.socket()
        sock.connect((host, port))
    except Exception as e:
        print(f"[!] Cannot connect to {host}:{port}: {e}")
        chan.close()
        return
    while True:
        r, _, _ = select.select([sock, chan], [], [], 5)
        if sock in r:
            data = sock.recv(4096)
            if not data:
                break
            chan.sendall(data)
        if chan in r:
            data = chan.recv(4096)
            if not data:
                break
            sock.sendall(data)
    chan.close()
    sock.close()


def main():
    p = argparse.ArgumentParser(description="SSH Reverse Tunnel")
    p.add_argument("--vps", required=True, help="VPS IP address")
    p.add_argument("--vps-user", default="root")
    p.add_argument("--vps-pass", required=True, help="VPS SSH password")
    p.add_argument("--vps-port", type=int, default=22, help="VPS SSH port")
    p.add_argument("--remote-port", type=int, default=8080, help="Port to open on VPS")
    p.add_argument("--local-port", type=int, default=8080, help="Local port to forward to")
    args = p.parse_args()

    while True:
        try:
            print(f"[*] Connecting to {args.vps}:{args.vps_port}...")
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                args.vps,
                port=args.vps_port,
                username=args.vps_user,
                password=args.vps_pass,
                timeout=10,
            )
            transport = client.get_transport()
            transport.set_keepalive(30)
            print(f"[+] Connected to {args.vps}")
            reverse_forward_tunnel(args.remote_port, "127.0.0.1", args.local_port, transport)
        except KeyboardInterrupt:
            print("\n[*] Stopped")
            break
        except Exception as e:
            print(f"[!] Error: {e}, reconnecting in 5s...")
            time.sleep(5)


if __name__ == "__main__":
    main()
