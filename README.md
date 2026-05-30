# Remote Windows Control

通过 HTTP 短轮询远程控制 Windows 机器。适用于远程机器没有公网 IP 的场景。

## 架构

```
┌──────────────┐    HTTP poll (每5秒)    ┌──────────────┐
│  本机 Server  │ <───────────────────── │  远程 Agent   │
│  (有公网IP)   │ ────────────────────> │  (无公网IP)   │
│  port 80     │    返回待执行命令       │              │
└──────┬───────┘                        └──────────────┘
       │ localhost
┌──────┴───────┐
│   CLI/Claude  │
│  发送命令查看结果│
└──────────────┘
```

Agent 定期用普通 HTTP 请求轮询 Server 获取命令、回传结果，流量特征与普通网页浏览一致。

## 快速开始

### 1. 本机（Server + CLI）

```bash
pip install flask requests
python server.py --secret 你的密码 --port 80
```

### 2. 远程机器（Agent）

把 `agent.py` 拷贝到远程 Windows，然后：

```bash
pip install requests
python agent.py --server http://你的公网IP:80 --secret 你的密码
```

### 3. 发命令

```bash
python cli.py status                          # 查看 agent 连接状态
python cli.py shell "dir C:\"                 # 执行 PowerShell 命令
python cli.py shell "ipconfig /all"           # 查看网络配置
python cli.py shell "Get-Service" --timeout 30
python cli.py shell "cmd /c dir" --cmd-exe    # 用 cmd.exe 执行
python cli.py screenshot                      # 截取远程桌面
python cli.py screenshot -o desktop.png       # 截屏保存到指定文件
python cli.py download "C:\Users\user\a.txt"  # 下载远程文件到本地
python cli.py download "C:\a.txt" ./local.txt # 指定本地保存路径
python cli.py upload ./local.txt "C:\a.txt"   # 上传本地文件到远程
python cli.py ps                              # 查看进程列表（按内存排序）
python cli.py kill 1234                       # 杀掉指定 PID 的进程
python cli.py sysinfo                         # 系统信息（CPU/内存/磁盘/IP/运行时间）
python cli.py history                         # 查看历史命令记录
```

## 功能列表

| 命令 | 说明 |
|------|------|
| `shell` | 执行 PowerShell/CMD 命令，返回 stdout/stderr/exit_code |
| `screenshot` | 截取主屏幕，保存为 PNG |
| `download` | 从远程下载文件到本地（≤50MB） |
| `upload` | 从本地上传文件到远程 |
| `ps` | 进程列表，显示 PID/CPU/内存/进程名 |
| `kill` | 按 PID 终止进程 |
| `sysinfo` | 主机名、操作系统、CPU、内存、磁盘、IP、运行时间 |
| `status` | 查看 Agent 是否在线 |
| `history` | 最近 50 条命令历史 |

## 安全机制

- **Token 认证**：Agent 与 Server 之间用共享密钥的 SHA256 哈希作为 Bearer Token
- **Controller 本地限制**：`/ctrl/*` 接口只接受 127.0.0.1 请求，外部无法直接下发命令
- **流量伪装**：标准 HTTP + 常规 User-Agent + 随机轮询间隔（±30% 抖动）

## Agent 开机自启（可选）

用 Windows 任务计划程序设置开机自启：

```powershell
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\agent.py --server http://IP:80 --secret 密码"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "RemoteAgent" -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest
```

## 依赖

- Server: `flask`
- Agent: `requests`（无其他依赖，截屏/进程管理全部通过 PowerShell 实现）
