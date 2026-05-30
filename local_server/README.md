# 方案一：本机 Server + 远程 Agent

适用场景：本机有公网 IP，Claude 在本机运行，通过 CLI 控制远程 Windows。

```
┌──────────────┐    HTTP poll (每5秒)    ┌──────────────┐
│  本机 Server  │ <───────────────────── │  远程 Agent   │
│  (有公网IP)   │ ────────────────────> │  (无公网IP)   │
│  port 80     │    返回待执行命令       │              │
└──────┬───────┘                        └──────────────┘
       │ localhost
┌──────┴───────┐
│   CLI/Claude  │
└──────────────┘
```

## 快速开始

### 本机

```bash
pip install flask requests
python server.py --secret 你的密码 --port 80
```

### 远程 Windows

把 `agent.py` 拷到远程，然后：

```bash
pip install requests
python agent.py --server http://本机公网IP:80 --secret 你的密码
```

### 发命令

```bash
python cli.py shell "dir C:\"
python cli.py screenshot
python cli.py download "C:\file.txt"
python cli.py upload local.txt "C:\remote.txt"
python cli.py ps
python cli.py kill 1234
python cli.py sysinfo
python cli.py status
python cli.py history
```

## 文件说明

| 文件 | 运行在 | 说明 |
|------|--------|------|
| `server.py` | 本机 | Flask HTTP server，接收 agent 轮询和 CLI 命令 |
| `agent.py` | 远程 | 定期轮询 server，执行命令并回传结果 |
| `cli.py` | 本机 | CLI 工具，Claude 通过它控制远程 |

## 依赖

- 本机：`flask`
- 远程：`requests`（无其他依赖，截屏/进程管理通过 PowerShell）
