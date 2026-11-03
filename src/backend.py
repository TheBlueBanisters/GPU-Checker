import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time

import paramiko
from PySide6.QtCore import QThread, Signal


BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
DATA = BASE / "data" if (BASE / "portable.flag").exists() else Path(os.getenv("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "GPUChecker"
HOST_KEY_LOCK = threading.Lock()


def config_path():
    imported = DATA / "ssh_config"
    return imported if imported.exists() else Path.home() / ".ssh/config"


def resolve_path(value):
    p = Path(os.path.expandvars(value)).expanduser()
    return str(p if p.is_absolute() else BASE / p)


def remote_command(interval):
    # Embed code, do not upload files or leave a remote agent/service behind.
    source = (Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "remote_probe.py").read_bytes()
    payload = base64.b64encode(source).decode("ascii")
    code = "import base64;exec(compile(base64.b64decode(%r),'<gpu-checker>','exec'))" % payload
    return "if command -v python3 >/dev/null 2>&1; then exec python3 -u -c %s %s; else printf 'GPUCHECK:{\"error\":\"Remote requires Python 3.6+ and NVIDIA drivers\"}\\n'; fi" % (shlex.quote(code), float(interval))


def ssh_executable():
    candidates = [shutil.which("ssh"), str(Path(os.getenv("WINDIR", "C:/Windows")) / "System32/OpenSSH/ssh.exe"),
                  str(BASE / "tools/ssh.exe")]
    return next((p for p in candidates if p and Path(p).is_file()), None)


def validate(profile):
    host = profile["host"].strip()
    if not host or host.startswith("-") or not re.fullmatch(r"[\w.:%@+\-\[\]]+", host, re.ASCII):
        raise ValueError("主机请填写域名、IP 或 SSH 别名（不要包含空格和命令）")
    if profile.get("user") and (profile["user"].startswith("-") or not re.fullmatch(r"[\w.@+\-]+", profile["user"], re.ASCII)):
        raise ValueError("用户名格式不正确")
    if profile.get("port") and not 1 <= int(profile["port"]) <= 65535:
        raise ValueError("端口应为 1–65535")


def native_args(profile):
    exe = ssh_executable()
    if not exe:
        raise RuntimeError("此电脑未找到 OpenSSH。可选择内置密钥/密码模式，或安装 Windows OpenSSH 客户端。")
    # Preserve native SSH config, agent, certificates, Include and ProxyJump.
    args = [exe, "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=12",
            "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=2", "-o", "LogLevel=ERROR"]
    if (DATA / "ssh_config").exists():
        args += ["-F", str(DATA / "ssh_config")]
    if (DATA / "known_hosts").exists():
        known = [str(Path.home() / ".ssh/known_hosts"), str(DATA / "known_hosts")]
        args += ["-o", "UserKnownHostsFile=" + " ".join('"' + p.replace("\\", "/") + '"' for p in known)]
    for field, flag in (("user", "-l"), ("port", "-p"), ("key", "-i")):
        if profile.get(field):
            args += [flag, resolve_path(profile[field]) if field == "key" else profile[field]]
    args += [profile["host"], remote_command(profile["interval"])]
    return args


class Monitor(QThread):
    data = Signal(dict)
    status = Signal(str)
    failed = Signal(str)
    trust = Signal(str, str)

    def __init__(self, profile, password="", passphrase=""):
        super().__init__()
        self.profile = dict(profile)
        self.password, self.passphrase = password, passphrase
        self.stop_event = threading.Event()
        self.stop_lock = threading.Lock()
        self.trust_event = threading.Event()
        self.accepted = False
        self.proc = self.client = self.channel = None
        self.last_sample = time.monotonic()

    def stop(self):
        self.stop_event.set()
        self.trust_event.set()
        if not self.stop_lock.acquire(blocking=False):
            return
        try:
            # UI cancellation and the worker's finally block can race. A peer
            # that has already disconnected may raise EOF while closing a channel.
            for resource in (self.channel,self.client):
                if resource:
                    try:
                        resource.close()
                    except (EOFError,OSError,paramiko.SSHException):
                        pass
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()  # local SSH only, never a remote GPU workload
                except OSError:
                    pass
        finally:
            self.stop_lock.release()

    def accept_key(self, accepted):
        self.accepted = accepted
        self.trust_event.set()

    def consume(self, line):
        if line.startswith("GPUCHECK:"):
            sample = json.loads(line[len("GPUCHECK:"):])
            self.last_sample = time.monotonic()
            self.data.emit(sample)

    def run(self):
        try:
            validate(self.profile)
            self.status.emit("正在建立加密连接…")
            if self.profile["mode"] == "OpenSSH 免密（推荐）":
                self.native()
            else:
                self.builtin()
        except Exception as exc:
            if not self.stop_event.is_set():
                message = str(exc)
                if isinstance(exc, paramiko.AuthenticationException):
                    message = "认证失败：请检查用户名、密码、密钥或密钥口令。"
                self.failed.emit(message)
        finally:
            self.password = self.passphrase = ""
            self.stop()
            if self.proc:
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=3)
                for stream in (self.proc.stdout, self.proc.stderr):
                    if stream:
                        stream.close()

    def native(self):
        self.proc = subprocess.Popen(native_args(self.profile), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        lines, errors = queue.Queue(), []
        def readout():
            for raw in self.proc.stdout:
                lines.put(raw.decode("utf-8", "replace").strip())
            lines.put(None)
        def readerr():
            for raw in self.proc.stderr:
                errors.append(raw.decode("utf-8", "replace").strip())
                del errors[:-12]
        reader = threading.Thread(target=readout, daemon=True)
        stderr = threading.Thread(target=readerr, daemon=True)
        reader.start()
        stderr.start()
        while not self.stop_event.is_set():
            try:
                line = lines.get(timeout=0.5)
            except queue.Empty:
                limit=max(35,self.profile['interval']*2+15)
                if time.monotonic() - self.last_sample > limit:
                    raise TimeoutError(f"{limit} 秒没有收到采样，连接可能已中断；请重新连接。")
                continue
            if line is None:
                stderr.join(timeout=1)
                raise RuntimeError("\n".join(errors) or "SSH 连接已关闭。请检查认证和远端 Python 3。")
            self.consume(line)

    def builtin(self):
        p = self.profile
        config = paramiko.SSHConfig()
        config_file = config_path()
        if config_file.exists():
            with config_file.open(encoding="utf-8") as f:
                config.parse(f)
        cfg = config.lookup(p["host"])
        if cfg.get("proxyjump") or cfg.get("proxycommand"):
            raise RuntimeError("该 SSH 别名配置了跳板机，请使用 OpenSSH 免密模式；内置模式仅支持直连。")
        host = cfg.get("hostname", p["host"])
        user = p.get("user") or cfg.get("user")
        if not user:
            raise ValueError("内置模式需要填写远端用户名（或在 SSH config 中配置 User）")
        port = int(p.get("port") or cfg.get("port", 22))
        self.client = paramiko.SSHClient()
        default_known = Path.home() / ".ssh/known_hosts"
        if default_known.exists():
            self.client.load_system_host_keys(str(default_known))
        DATA.mkdir(parents=True, exist_ok=True)
        known = DATA / "known_hosts"
        if known.exists():
            self.client.load_host_keys(str(known))
        monitor = self
        class AskPolicy(paramiko.MissingHostKeyPolicy):
            def missing_host_key(self, client, hostname, key):
                fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")
                monitor.trust.emit(hostname, key.get_name() + "  " + fingerprint)
                while not monitor.trust_event.wait(0.2):
                    if monitor.stop_event.is_set():
                        raise RuntimeError("已取消")
                if not monitor.accepted or monitor.stop_event.is_set():
                    raise RuntimeError("未信任主机密钥，连接已取消")
                with HOST_KEY_LOCK:
                    merged=paramiko.HostKeys()
                    if known.exists():
                        merged.load(str(known))
                    previous=merged.lookup(hostname)
                    if previous and previous.get(key.get_name()) and previous[key.get_name()] != key:
                        raise paramiko.SSHException('Host key changed during verification; connection rejected')
                    merged.add(hostname,key.get_name(),key)
                    temporary=known.with_suffix('.tmp')
                    merged.save(str(temporary))
                    temporary.replace(known)
                client.get_host_keys().add(hostname, key.get_name(), key)
        self.client.set_missing_host_key_policy(AskPolicy())
        is_password = p["mode"] == "密码登录（内置）"
        keys = resolve_path(p["key"]) if p.get("key") else cfg.get("identityfile")
        self.client.connect(hostname=host, port=port, username=user,
                            password=self.password if is_password else None,
                            passphrase=self.passphrase or None,
                            key_filename=None if is_password else keys,
                            allow_agent=not is_password, look_for_keys=not is_password,
                            timeout=12, banner_timeout=12, auth_timeout=20)
        self.password = self.passphrase = ""
        if self.stop_event.is_set():
            return
        self.client.get_transport().set_keepalive(10)
        self.channel = self.client.get_transport().open_session(timeout=12)
        self.channel.settimeout(1)
        self.channel.exec_command(remote_command(p["interval"]))
        buffer, errors = b"", b""
        while not self.stop_event.is_set():
            if self.channel.recv_ready():
                buffer += self.channel.recv(65536)
                if len(buffer) > 8 * 1024 * 1024:
                    raise RuntimeError("远端采样数据异常过大")
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    self.consume(line.decode("utf-8", "replace").strip())
            if self.channel.recv_stderr_ready():
                errors = (errors + self.channel.recv_stderr(8192))[-8192:]
            if self.channel.exit_status_ready() and not self.channel.recv_ready():
                raise RuntimeError(errors.decode("utf-8", "replace") or "远端连接已关闭")
            limit=max(35,p['interval']*2+15)
            if time.monotonic() - self.last_sample > limit:
                raise TimeoutError(f"{limit} 秒没有收到采样，连接可能已中断；请重新连接。")
            self.stop_event.wait(0.1)
