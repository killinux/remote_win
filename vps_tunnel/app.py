#!/usr/bin/env python3
"""Web Control Panel for Remote Windows.
Run on the remote machine, access via browser.
Usage: python app.py --password YOUR_PASSWORD [--port 8080]
"""

import os
import sys
import json
import time
import base64
import hashlib
import subprocess
import tempfile
import argparse
import socket
import platform
from functools import wraps
from flask import Flask, request, jsonify, session, redirect, render_template_string, send_file

app = Flask(__name__)
app.secret_key = os.urandom(32)

PASSWORD = "admin"
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("auth"):
            if request.is_json:
                return jsonify({"error": "unauthorized"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper


# ───── Auth ─────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password") or (request.json or {}).get("password", "")
        if pw == PASSWORD:
            session["auth"] = True
            session.permanent = True
            return redirect("/")
        return render_template_string(LOGIN_HTML, error="Wrong password"), 401
    return render_template_string(LOGIN_HTML, error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ───── Pages ─────

@app.route("/")
@login_required
def index():
    return render_template_string(INDEX_HTML)


# ───── API ─────

@app.route("/api/exec", methods=["POST"])
@login_required
def api_exec():
    data = request.json
    cmd = data.get("cmd", "")
    timeout = data.get("timeout", 120)
    use_ps = data.get("powershell", True)
    if use_ps:
        args = ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd]
    else:
        args = ["cmd", "/c", cmd]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                              creationflags=CREATE_NO_WINDOW)
        return jsonify({
            "stdout": proc.stdout[-100000:],
            "stderr": proc.stderr[-20000:],
            "exit_code": proc.returncode,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"stdout": "", "stderr": f"Timeout after {timeout}s", "exit_code": -1})


@app.route("/api/screenshot")
@login_required
def api_screenshot():
    tmp = os.path.join(tempfile.gettempdir(), f"scr_{int(time.time())}.png")
    script = f"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object Drawing.Bitmap $b.Width,$b.Height
$g = [Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Location,[Drawing.Point]::Empty,$b.Size)
$bmp.Save('{tmp}')
$g.Dispose()
$bmp.Dispose()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", script],
                   capture_output=True, timeout=15, creationflags=CREATE_NO_WINDOW)
    if os.path.exists(tmp):
        with open(tmp, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        os.remove(tmp)
        return jsonify({"image": data})
    return jsonify({"error": "Screenshot failed"}), 500


@app.route("/api/files")
@login_required
def api_files():
    path = request.args.get("path", "C:\\")
    try:
        entries = []
        for name in os.listdir(path):
            full = os.path.join(path, name)
            try:
                st = os.stat(full)
                entries.append({
                    "name": name,
                    "path": full,
                    "is_dir": os.path.isdir(full),
                    "size": st.st_size if not os.path.isdir(full) else 0,
                    "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                })
            except (PermissionError, OSError):
                entries.append({"name": name, "path": full, "is_dir": False, "size": 0, "mtime": "N/A"})
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        return jsonify({"path": path, "entries": entries})
    except PermissionError:
        return jsonify({"error": f"Permission denied: {path}"}), 403
    except FileNotFoundError:
        return jsonify({"error": f"Not found: {path}"}), 404


@app.route("/api/download")
@login_required
def api_download():
    path = request.args.get("path", "")
    if not path or not os.path.isfile(path):
        return jsonify({"error": "File not found"}), 404
    return send_file(path, as_attachment=True)


@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    dest_dir = request.form.get("path", "C:\\Users")
    if not os.path.isdir(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"error": "No file"}), 400
    dest = os.path.join(dest_dir, uploaded.filename)
    uploaded.save(dest)
    return jsonify({"path": dest, "size": os.path.getsize(dest)})


@app.route("/api/processes")
@login_required
def api_processes():
    cmd = "Get-Process | Select-Object Id,ProcessName,CPU,@{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | Sort-Object MemMB -Descending | ConvertTo-Json -Compress"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True, timeout=15, creationflags=CREATE_NO_WINDOW)
    try:
        ps = json.loads(proc.stdout)
        if isinstance(ps, dict):
            ps = [ps]
    except:
        ps = []
    return jsonify(ps)


@app.route("/api/kill", methods=["POST"])
@login_required
def api_kill():
    pid = request.json.get("pid")
    proc = subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                          capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW)
    return jsonify({"ok": proc.returncode == 0, "msg": proc.stdout.strip() or proc.stderr.strip()})


@app.route("/api/sysinfo")
@login_required
def api_sysinfo():
    info = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "cpu": platform.processor(),
        "python": sys.version.split()[0],
    }
    cmds = {
        "os": "(Get-CimInstance Win32_OperatingSystem).Caption",
        "cpu_name": "(Get-CimInstance Win32_Processor).Name",
        "ram_gb": "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)",
        "disk": "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object { \"$($_.DeviceID) $([math]::Round($_.FreeSpace/1GB,1))/$([math]::Round($_.Size/1GB,1))GB\" }",
        "uptime": "(New-TimeSpan -Start (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).ToString('d\\.hh\\:mm\\:ss')",
        "ip": "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne '127.0.0.1'}).IPAddress -join ', '",
        "gpu": "(Get-CimInstance Win32_VideoController).Name",
    }
    for k, cmd in cmds.items():
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                               capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW)
            info[k] = r.stdout.strip()
        except:
            info[k] = "N/A"
    return jsonify(info)


# ───── HTML Templates ─────

LOGIN_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Login</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a2e;color:#eee;font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh}
.box{background:#16213e;padding:2rem;border-radius:8px;width:320px}
h2{margin-bottom:1rem;color:#0f3460}
input{width:100%;padding:.6rem;margin:.5rem 0;border:1px solid #333;border-radius:4px;background:#0f3460;color:#eee;font-size:1rem}
button{width:100%;padding:.6rem;background:#e94560;color:#fff;border:none;border-radius:4px;font-size:1rem;cursor:pointer;margin-top:.5rem}
button:hover{background:#c73e54}
.err{color:#e94560;font-size:.9rem;margin-top:.5rem}
</style></head><body>
<div class="box"><h2>Remote Control</h2>
<form method="post"><input type="password" name="password" placeholder="Password" autofocus>
<button type="submit">Login</button></form>
{% if error %}<p class="err">{{ error }}</p>{% endif %}
</div></body></html>"""

INDEX_HTML = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Remote Control</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a1a;color:#d4d4d4;font-family:'Consolas','SF Mono',monospace;font-size:14px}
.tabs{display:flex;background:#12122a;border-bottom:1px solid #333;position:sticky;top:0;z-index:10}
.tab{padding:.7rem 1.2rem;cursor:pointer;border-bottom:2px solid transparent;color:#888}
.tab:hover{color:#ddd}.tab.active{color:#5cf;border-color:#5cf}
.panel{display:none;padding:1rem;height:calc(100vh - 42px);overflow-y:auto}
.panel.active{display:flex;flex-direction:column}
#term-out{flex:1;overflow-y:auto;background:#0d0d1a;padding:.5rem;border-radius:4px;white-space:pre-wrap;word-break:break-all;margin-bottom:.5rem;font-size:13px;line-height:1.5}
#term-in{display:flex;gap:.5rem}
#term-in input{flex:1;background:#111;border:1px solid #333;color:#eee;padding:.5rem;border-radius:4px;font-family:inherit;font-size:14px}
#term-in button{padding:.5rem 1rem;background:#5cf;color:#000;border:none;border-radius:4px;cursor:pointer;font-weight:bold}
.stdout{color:#b5e853}.stderr{color:#e55}.exitcode{color:#f80}
.prompt{color:#5cf}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:.4rem .6rem;text-align:left;border-bottom:1px solid #222}
th{background:#12122a;position:sticky;top:0;color:#888}
tr:hover{background:#1a1a3a}
.btn{padding:.3rem .7rem;background:#333;color:#ddd;border:none;border-radius:3px;cursor:pointer;font-size:12px}
.btn:hover{background:#555}
.btn-danger{background:#a33;color:#fff}.btn-danger:hover{background:#c44}
.btn-primary{background:#2a6;color:#fff}.btn-primary:hover{background:#3b7}
.info-grid{display:grid;grid-template-columns:140px 1fr;gap:.3rem .8rem;background:#0d0d1a;padding:1rem;border-radius:4px}
.info-grid .k{color:#888;text-align:right}.info-grid .v{color:#b5e853}
.screenshot img{max-width:100%;border-radius:4px;margin-top:.5rem}
.breadcrumb{display:flex;gap:.3rem;margin-bottom:.5rem;flex-wrap:wrap}
.breadcrumb span{color:#5cf;cursor:pointer;padding:.2rem .4rem;border-radius:3px}
.breadcrumb span:hover{background:#1a1a3a}
.file-row{cursor:pointer}.file-row:hover{background:#1a1a3a}
.dir-icon{color:#f9a825}.file-icon{color:#666}
.upload-zone{border:2px dashed #333;border-radius:4px;padding:2rem;text-align:center;color:#666;margin-top:.5rem;cursor:pointer}
.upload-zone.dragover{border-color:#5cf;color:#5cf}
.topbar{display:flex;gap:.5rem;margin-bottom:.5rem;align-items:center}
.topbar input{flex:1;background:#111;border:1px solid #333;color:#eee;padding:.4rem .6rem;border-radius:4px;font-family:inherit}
.loading{color:#888;font-style:italic}
</style></head><body>

<div class="tabs">
  <div class="tab active" onclick="showTab('terminal')">Terminal</div>
  <div class="tab" onclick="showTab('files')">Files</div>
  <div class="tab" onclick="showTab('processes')">Processes</div>
  <div class="tab" onclick="showTab('system')">System</div>
  <div style="margin-left:auto;padding:.7rem"><a href="/logout" style="color:#888;text-decoration:none;font-size:12px">Logout</a></div>
</div>

<!-- Terminal -->
<div id="terminal" class="panel active">
  <div id="term-out"></div>
  <div id="term-in">
    <input id="cmd-input" placeholder="Type a command..." onkeydown="handleKey(event)" autofocus>
    <button onclick="runCmd()">Run</button>
  </div>
</div>

<!-- Files -->
<div id="files" class="panel">
  <div class="topbar">
    <div class="breadcrumb" id="breadcrumb"></div>
  </div>
  <div style="flex:1;overflow-y:auto">
    <table><thead><tr><th>Name</th><th>Size</th><th>Modified</th><th></th></tr></thead>
    <tbody id="file-list"></tbody></table>
  </div>
  <div class="upload-zone" id="upload-zone" onclick="document.getElementById('file-input').click()"
       ondragover="event.preventDefault();this.classList.add('dragover')"
       ondragleave="this.classList.remove('dragover')"
       ondrop="event.preventDefault();this.classList.remove('dragover');uploadFiles(event.dataTransfer.files)">
    Drop files here or click to upload
    <input type="file" id="file-input" multiple hidden onchange="uploadFiles(this.files)">
  </div>
</div>

<!-- Processes -->
<div id="processes" class="panel">
  <div class="topbar">
    <button class="btn btn-primary" onclick="loadProcesses()">Refresh</button>
    <input id="ps-filter" placeholder="Filter..." oninput="filterProcesses()">
  </div>
  <div style="flex:1;overflow-y:auto">
    <table><thead><tr><th>PID</th><th>Name</th><th>CPU</th><th>Mem(MB)</th><th></th></tr></thead>
    <tbody id="ps-list"></tbody></table>
  </div>
</div>

<!-- System -->
<div id="system" class="panel">
  <div class="topbar">
    <button class="btn btn-primary" onclick="loadSysinfo()">Refresh</button>
    <button class="btn" onclick="takeScreenshot()">Screenshot</button>
  </div>
  <div class="info-grid" id="sysinfo"></div>
  <div class="screenshot" id="screenshot-box"></div>
</div>

<script>
let cmdHistory = [], histIdx = -1;
let currentPath = 'C:\\';
let allProcesses = [];

function showTab(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(name).classList.add('active');
  document.querySelector(`.tab[onclick*="${name}"]`).classList.add('active');
  if (name === 'files' && !document.getElementById('file-list').innerHTML) loadFiles(currentPath);
  if (name === 'processes' && !document.getElementById('ps-list').innerHTML) loadProcesses();
  if (name === 'system' && !document.getElementById('sysinfo').innerHTML) loadSysinfo();
  if (name === 'terminal') document.getElementById('cmd-input').focus();
}

// ── Terminal ──
function appendOutput(html) {
  const out = document.getElementById('term-out');
  out.innerHTML += html;
  out.scrollTop = out.scrollHeight;
}

async function runCmd() {
  const input = document.getElementById('cmd-input');
  const cmd = input.value.trim();
  if (!cmd) return;
  cmdHistory.unshift(cmd); histIdx = -1;
  input.value = '';
  appendOutput(`<span class="prompt">PS&gt;</span> ${escHtml(cmd)}\n`);
  try {
    const r = await fetch('/api/exec', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({cmd})});
    const d = await r.json();
    if (d.stdout) appendOutput(`<span class="stdout">${escHtml(d.stdout)}</span>`);
    if (d.stderr) appendOutput(`<span class="stderr">${escHtml(d.stderr)}</span>`);
    if (d.exit_code !== 0) appendOutput(`<span class="exitcode">[exit ${d.exit_code}]</span>\n`);
    if (!d.stdout && !d.stderr && d.exit_code === 0) appendOutput('\n');
  } catch(e) { appendOutput(`<span class="stderr">Error: ${e}</span>\n`); }
}

function handleKey(e) {
  if (e.key === 'Enter') { runCmd(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); if (histIdx < cmdHistory.length-1) e.target.value = cmdHistory[++histIdx]; }
  else if (e.key === 'ArrowDown') { e.preventDefault(); histIdx = Math.max(-1, histIdx-1); e.target.value = histIdx>=0 ? cmdHistory[histIdx] : ''; }
}

// ── Files ──
async function loadFiles(path) {
  currentPath = path;
  const bc = document.getElementById('breadcrumb');
  const parts = path.replace(/\\/g,'/').split('/').filter(Boolean);
  let built = '';
  bc.innerHTML = '<span onclick="loadFiles(\'C:\\\\\')">C:</span>';
  parts.forEach(p => { built += p + '\\'; bc.innerHTML += `<span onclick="loadFiles('C:\\\\${escAttr(built)}')">${escHtml(p)}</span>`; });

  const list = document.getElementById('file-list');
  list.innerHTML = '<tr><td colspan="4" class="loading">Loading...</td></tr>';
  try {
    const r = await fetch(`/api/files?path=${encodeURIComponent(path)}`);
    const d = await r.json();
    if (d.error) { list.innerHTML = `<tr><td colspan="4" class="stderr">${d.error}</td></tr>`; return; }
    let html = '';
    if (path !== 'C:\\') html += `<tr class="file-row" onclick="loadFiles('${escAttr(parentDir(path))}')"><td><span class="dir-icon">📁</span> ..</td><td></td><td></td><td></td></tr>`;
    d.entries.forEach(e => {
      if (e.is_dir) {
        html += `<tr class="file-row" onclick="loadFiles('${escAttr(e.path)}')"><td><span class="dir-icon">📁</span> ${escHtml(e.name)}</td><td></td><td>${e.mtime}</td><td></td></tr>`;
      } else {
        html += `<tr class="file-row"><td><span class="file-icon">📄</span> ${escHtml(e.name)}</td><td>${fmtSize(e.size)}</td><td>${e.mtime}</td><td><a href="/api/download?path=${encodeURIComponent(e.path)}" class="btn">Download</a></td></tr>`;
      }
    });
    list.innerHTML = html || '<tr><td colspan="4">Empty directory</td></tr>';
  } catch(e) { list.innerHTML = `<tr><td colspan="4" class="stderr">${e}</td></tr>`; }
}

async function uploadFiles(files) {
  for (const f of files) {
    const fd = new FormData();
    fd.append('file', f);
    fd.append('path', currentPath);
    await fetch('/api/upload', {method:'POST', body:fd});
  }
  loadFiles(currentPath);
}

// ── Processes ──
async function loadProcesses() {
  const list = document.getElementById('ps-list');
  list.innerHTML = '<tr><td colspan="5" class="loading">Loading...</td></tr>';
  const r = await fetch('/api/processes');
  allProcesses = await r.json();
  renderProcesses(allProcesses);
}

function renderProcesses(ps) {
  const list = document.getElementById('ps-list');
  list.innerHTML = ps.slice(0,100).map(p => `<tr>
    <td>${p.Id}</td><td>${escHtml(p.ProcessName||'')}</td><td>${p.CPU?p.CPU.toFixed(1):'0'}</td><td>${p.MemMB||0}</td>
    <td><button class="btn btn-danger" onclick="killProc(${p.Id})">Kill</button></td>
  </tr>`).join('');
}

function filterProcesses() {
  const q = document.getElementById('ps-filter').value.toLowerCase();
  renderProcesses(allProcesses.filter(p => (p.ProcessName||'').toLowerCase().includes(q) || String(p.Id).includes(q)));
}

async function killProc(pid) {
  if (!confirm(`Kill process ${pid}?`)) return;
  await fetch('/api/kill', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pid})});
  loadProcesses();
}

// ── System ──
async function loadSysinfo() {
  const el = document.getElementById('sysinfo');
  el.innerHTML = '<span class="loading">Loading...</span>';
  const r = await fetch('/api/sysinfo');
  const d = await r.json();
  el.innerHTML = Object.entries(d).map(([k,v]) => `<span class="k">${k}</span><span class="v">${escHtml(String(v))}</span>`).join('');
}

async function takeScreenshot() {
  const box = document.getElementById('screenshot-box');
  box.innerHTML = '<p class="loading">Capturing...</p>';
  const r = await fetch('/api/screenshot');
  const d = await r.json();
  if (d.image) box.innerHTML = `<img src="data:image/png;base64,${d.image}">`;
  else box.innerHTML = `<p class="stderr">${d.error||'Failed'}</p>`;
}

// ── Utils ──
function escHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function escAttr(s){return s.replace(/\\/g,'\\\\').replace(/'/g,"\\'")}
function parentDir(p){const parts=p.replace(/\\$/,'').split('\\');parts.pop();return parts.join('\\\\')||'C:\\\\'}
function fmtSize(b){if(b<1024)return b+'B';if(b<1048576)return(b/1024).toFixed(1)+'K';if(b<1073741824)return(b/1048576).toFixed(1)+'M';return(b/1073741824).toFixed(1)+'G'}
</script>
</body></html>"""


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Web Control Panel")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--password", default="admin", help="Login password")
    args = p.parse_args()
    PASSWORD = args.password
    print(f"[*] Control Panel: http://0.0.0.0:{args.port}")
    print(f"[*] Password: {args.password}")
    app.run(host="0.0.0.0", port=args.port, threaded=True)
