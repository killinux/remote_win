# 方案二：Mac 通过 VPS 控制远程 Windows

适用场景：Mac 没有公网 IP，远程 Windows 也没有，通过一台 VPS 中转。

```
┌──────────┐                ┌──────────┐  SSH反向隧道  ┌──────────────┐
│   Mac    │ ──── HTTP ───> │   VPS    │ <─────────── │  远程 Windows │
│ 浏览器/CLI│               │:9090/9876│  ──────────> │ Web面板/Blender│
└──────────┘                └──────────┘              │ :8080 / :9876│
                                                      └──────────────┘
```

## 快速使用

### 远程 Windows 每次开机执行：

```bash
cd E:\code\othercode\remote_win\vps_tunnel

# Web 控制面板 + 隧道
python start_all.py --vps 49.233.189.223 --vps-pass haoning --password haoning

# Blender MCP 隧道（需先打开 Blender 和 blender-mcp）
python start_blender.py --vps 49.233.189.223 --vps-pass haoning
```

### Mac 浏览器控制：

打开 http://49.233.189.223:9090 ，密码 `haoning`

### Mac Claude CLI 控制：

```bash
export REMOTE_SERVER=http://49.233.189.223:9090
export REMOTE_PASSWORD=haoning
python cli.py shell "dir C:\\"
python cli.py screenshot
python cli.py download "C:\file.txt"
python cli.py upload local.txt "C:\remote.txt"
python cli.py ps
python cli.py kill 1234
python cli.py sysinfo
python cli.py files "C:\\"
```

### Mac Claude 连接 Blender MCP：

在 `~/.claude/settings.json` 中添加：
```json
{
  "mcpServers": {
    "blender": {
      "url": "http://49.233.189.223:9876/sse"
    }
  }
}
```

## 首次部署

### 1. 配置 VPS（一次性）

```bash
pip install paramiko
python setup_vps.py --host VPS的IP --password VPS的SSH密码
```

### 2. 远程 Windows 安装依赖（一次性）

```bash
pip install flask paramiko
```

### 3. 开机自启（可选）

```powershell
$action = New-ScheduledTaskAction -Execute "python" -Argument "E:\code\othercode\remote_win\vps_tunnel\start_all.py --vps 49.233.189.223 --vps-pass haoning --password haoning"
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "RemoteControl" -Action $action -Trigger $trigger -RunLevel Highest
```

## 文件说明

| 文件 | 运行在 | 说明 |
|------|--------|------|
| `app.py` | 远程 Windows | Web 控制面板（Flask） |
| `tunnel.py` | 远程 Windows | SSH 反向隧道 |
| `start_all.py` | 远程 Windows | 一键启动 app + tunnel |
| `start_blender.py` | 远程 Windows | 启动 Blender MCP 隧道 |
| `cli.py` | Mac | Claude CLI 控制远程 |
| `setup_vps.py` | 任意机器 | 一次性配置 VPS |

## 依赖

- 远程 Windows：`flask`、`paramiko`
- Mac：`requests`
- VPS：`sshd`（默认有），可选 `nginx`
