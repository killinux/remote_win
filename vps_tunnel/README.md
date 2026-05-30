# 方案二：Mac 通过 VPS 控制远程 Windows

适用场景：Mac 没有公网 IP，远程 Windows 也没有，通过一台 VPS 中转。

```
┌──────────┐                ┌──────────┐  SSH反向隧道  ┌──────────────┐
│   Mac    │ ──── HTTP ───> │   VPS    │ <─────────── │  远程 Windows │
│  浏览器   │               │  :9090   │  ──────────> │  Web控制面板   │
└──────────┘                └──────────┘              │  :8080       │
                                                      └──────────────┘
```

## 部署步骤

### 1. 配置 VPS（一次性）

在任意能 SSH 到 VPS 的机器上运行：

```bash
pip install paramiko
python setup_vps.py --host VPS的IP --password VPS的SSH密码
```

### 2. 远程 Windows

把 `app.py`、`tunnel.py`、`start_all.py` 拷到远程，然后：

```bash
pip install flask paramiko
python start_all.py --vps VPS的IP --vps-pass VPS的SSH密码 --password 网页登录密码
```

### 3. Mac 访问

浏览器打开 `http://VPS的IP:9090`，输入密码登录。

功能：
- **Terminal** — 远程执行 PowerShell/CMD 命令，带命令历史
- **Files** — 文件浏览器，上传/下载文件
- **Processes** — 进程列表，搜索和一键 Kill
- **System** — 系统信息 + 远程截屏

## 文件说明

| 文件 | 运行在 | 说明 |
|------|--------|------|
| `app.py` | 远程 Windows | Web 控制面板（Flask） |
| `tunnel.py` | 远程 Windows | SSH 反向隧道，连接 VPS |
| `start_all.py` | 远程 Windows | 一键启动 app + tunnel |
| `setup_vps.py` | 任意机器 | 一次性配置 VPS 的 sshd 和 nginx |

## 依赖

- 远程 Windows：`flask`、`paramiko`
- VPS：已安装 `sshd`（默认有），可选 `nginx`
