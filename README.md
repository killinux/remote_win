# Remote Windows Control

远程控制 Windows 机器，适用于远程没有公网 IP 的场景。

## 快速使用（方案二 + Blender MCP）

### 远程 Windows 每次开机执行：

```bash
cd E:\code\othercode\remote_win\vps_tunnel

# 启动 Web 控制面板 + 隧道
python start_all.py --vps 49.233.189.223 --vps-pass haoning --password haoning

# 启动 Blender MCP 隧道（Blender 需先打开且 blender-mcp 已启动）
python start_blender.py --vps 49.233.189.223 --vps-pass haoning
```

### Mac 上使用：

**浏览器控制：** 打开 http://49.233.189.223:9090 ，密码 `haoning`

**Claude CLI 控制：**
```bash
cd vps_tunnel
export REMOTE_SERVER=http://49.233.189.223:9090
export REMOTE_PASSWORD=haoning
python cli.py shell "dir C:\\"
python cli.py screenshot
python cli.py sysinfo
```

**Claude 连接 Blender MCP：** 在 Mac 的 `~/.claude/settings.json` 中添加：
```json
{
  "mcpServers": {
    "blender": {
      "url": "http://49.233.189.223:9876/sse"
    }
  }
}
```

---

## 方案一：[local_server/](local_server/) — 本机 Server 控制远程

- 本机（有公网 IP）跑 HTTP Server
- 远程 Windows 跑 Agent 定期轮询
- 本机 Claude 通过 CLI 发命令

适合：本机有公网 IP 且长期在线

## 方案二：[vps_tunnel/](vps_tunnel/) — Mac 通过 VPS 控制远程

- 远程 Windows 跑 Web 控制面板 + SSH 反向隧道连 VPS
- Mac 浏览器或 Claude CLI 通过 VPS 访问

适合：本机没有公网 IP，或需要从任意设备访问

## Blender MCP

通过 VPS 隧道暴露远程 Blender 的 MCP 服务（端口 9876），Mac 上的 Claude 可以直接操作远程 Blender。
