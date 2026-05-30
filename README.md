# Remote Windows Control

远程控制 Windows 机器的两种方案，适用于远程机器没有公网 IP 的场景。

## 方案一：[local_server/](local_server/) — 本机 Server 控制远程

- 本机（有公网 IP）跑 HTTP Server
- 远程 Windows 跑 Agent 定期轮询
- 本机 Claude 通过 CLI 发命令

适合：本机有公网 IP 且长期在线

## 方案二：[vps_tunnel/](vps_tunnel/) — Mac 通过 VPS 控制远程

- 远程 Windows 跑 Web 控制面板 + SSH 反向隧道连 VPS
- Mac 浏览器通过 VPS 访问 Web 控制面板

适合：本机没有公网 IP，或需要从任意设备（手机/Mac/其他电脑）访问
