# Remote Windows Control

远程控制 Windows 机器，适用于远程没有公网 IP 的场景。

> 说明：下文密码一律以占位符 `<VPS_PASS>`（VPS SSH 密码）/ `<PANEL_PASS>`（Web 面板密码）表示，
> 真实密码不写进本仓库。实际执行时替换占位符即可。

## 链路架构

```
Mac ──► VPS (49.233.189.223, Linux 跳板) ──► Windows (Blender 3.6.x)
         │  22    SSH 跳板（常通）
         │  9090  Web 面板隧道（app.py，常驻）
         │  9876  BlenderMCP 隧道（绑 Blender，易掉）
```

两条隧道都是 Windows 端用 `ssh -R` 反挂到 VPS 的反向隧道。

## 快速使用（方案二 + Blender MCP）

### 远程 Windows 每次开机执行：

```bash
cd E:\code\othercode\remote_win\vps_tunnel

# 启动 Web 控制面板 + 9090 隧道
python start_all.py --vps 49.233.189.223 --vps-pass <VPS_PASS> --password <PANEL_PASS>

# 启动 Blender MCP 9876 隧道（Blender 需先打开且 blender-mcp 已 Start）
python start_blender.py --vps 49.233.189.223 --vps-pass <VPS_PASS>
```

### Mac 上使用：

**浏览器控制：** 打开 http://49.233.189.223:9090 ，密码 `<PANEL_PASS>`

**Claude CLI 控制：**
```bash
cd vps_tunnel
export REMOTE_SERVER=http://49.233.189.223:9090
export REMOTE_PASSWORD=<PANEL_PASS>
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

## 故障排查：连不上远端 Blender（`Connection refused`）

绝大多数情况是 **9876 反向隧道掉了**（绑 Blender 开关，易掉），不是 Blender、也不是 Mac 的 MCP 配置问题。

### 1. 在 Mac 上定位故障段

```bash
nc -z -w4 49.233.189.223 22    # SSH 跳板
nc -z -w4 49.233.189.223 9090  # Web 面板
nc -z -w4 49.233.189.223 9876  # BlenderMCP 隧道
```

- `22`+`9090` OPEN、`9876` CLOSED ＝ **典型故障：9876 隧道掉了**，Blender 多半还开着 → 见第 3 步。
- `9090` 也 CLOSED ＝ 面板隧道也掉了 → 见第 4 步。

### 2.（可选）经面板确认 Windows 侧状态

```bash
cd vps_tunnel
export REMOTE_SERVER=http://49.233.189.223:9090 REMOTE_PASSWORD=<PANEL_PASS>
python cli.py shell 'tasklist | findstr /I "blender python"'   # 看 blender.exe 在不在
python cli.py shell 'netstat -ano | findstr 9876'              # 127.0.0.1:9876 LISTENING = MCP 本地正常
```

`blender.exe` 在跑且 `127.0.0.1:9876` LISTENING ⇒ Blender + 插件都正常，纯粹是反挂隧道断了。

### 3. 恢复 9876 隧道 ← 大多数情况只需这一步

**在 Windows 上**（cmd / PowerShell 直接跑）：

```bash
D:\openclaw\python\python.exe E:\code\othercode\remote_win\vps_tunnel\start_blender.py --vps 49.233.189.223 --vps-pass <VPS_PASS>
```

> `start_blender.py` 名字唬人，**它不开 Blender**——内部只 `Popen(CREATE_NO_WINDOW)` 起 `tunnel.py` 当后台孙进程挂隧道，父进程随即自退（打印两行 `[+]` 属正常）。
> 前提：Blender 已开且 blender-mcp 已 Start（本地 `127.0.0.1:9876` 在 LISTENING）；本脚本只转发端口，不开 Blender、不点插件。

若一时上不了 Windows 桌面，也可经活着的 9090 面板远程触发同一条命令：

```bash
cd vps_tunnel
export REMOTE_SERVER=http://49.233.189.223:9090 REMOTE_PASSWORD=<PANEL_PASS>
python cli.py shell 'D:\openclaw\python\python.exe E:\code\othercode\remote_win\vps_tunnel\start_blender.py --vps 49.233.189.223 --vps-pass <VPS_PASS>'
```

（注意：面板 shell 是 PowerShell，命令链用 `;`；`start "" /b ...` 会 exit 1，别用，直接调脚本靠其内部 Popen 后台化。）

~几秒后 `nc -z 49.233.189.223 9876` 应变 OPEN，Mac 的 Blender MCP 即恢复。

### 4. 面板（9090）也掉了

在 Windows 上重跑 `start_all.py`（同时拉起面板 + 9090 隧道）：

```bash
python E:\code\othercode\remote_win\vps_tunnel\start_all.py --vps 49.233.189.223 --vps-pass <VPS_PASS> --password <PANEL_PASS>
```

### 5. Blender 本身没开 / 插件没 Start

`netstat` 看不到 `127.0.0.1:9876` LISTENING ⇒ 隧道挂起来也连不上。这时必须**人工在 Windows 打开 Blender 并点 BlenderMCP 面板的 Start**（面板 shell 点不了 UI），然后再回第 3 步挂隧道。

---

## 脚本分工

| 脚本 | 作用 | VPS 端口 |
|---|---|---|
| `tunnel.py` | 通用 SSH 反向隧道底座（被下面两个调用，一般不直接跑） | — |
| `start_blender.py` | 只挂 9876 BlenderMCP 隧道 | 9876 |
| `start_all.py` | 起 Web 面板 `app.py` + 9090 面板隧道 | 9090 |
| `app.py` | Web 控制面板（Flask），Windows 本地监听 8080，经隧道映射到 VPS:9090 | — |
| `cli.py` | Mac 侧通过面板远程执行 shell / 截图 / 系统信息 | — |

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
