import ctypes
import base64
import json
import os
import random
import re
import secrets
import socket as _socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import appupdate
import netparse
import singbox as core_mod
import subs as subs_mod
import version
import warp as warp_mod
from ui import ADMIN_HTML

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
GEO_FILE = os.path.join(BASE_DIR, "geo.json")
LOCK_FILE = os.path.join(BASE_DIR, ".lock")
APP_SCRIPT = os.path.abspath(__file__)

# «Завершиться, чтобы применить скачанное обновление» + путь к apply-скрипту
_restart_event = threading.Event()
_restart_bat = ""

try:
    import faulthandler
    faulthandler.enable(open(os.path.join(BASE_DIR, "crash.log"), "a", encoding="utf-8"))
except Exception:
    pass

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8888
ADMIN_HOST = "127.0.0.1"
ADMIN_PORT = 8000
MAX_LOGS = 400
CREATE_NO_WINDOW = 0x08000000

LATENCY_CUTOFF_MS = 1500
SUB_IMPORT_CAP = 600
TEST_WORKERS = 12
TEST_TIMEOUT = 6

SERVER_FIELDS = [
    "id", "name", "type", "host", "port", "uuid", "username", "password",
    "method", "flow", "security", "sni", "fp", "pbk", "sid", "transport",
    "path", "host_header", "service_name", "enabled", "source", "latency", "latency_ok", "tested", "country", "added_ts",
    "obfs", "obfs_password", "up", "down", "alpn", "allow_insecure", "congestion_control",
    "privkey", "peer_pubkey", "local_addrs", "reserved", "mtu",
]

try:
    import winreg
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _country_from_name(name):
    try:
        name = str(name or "")
        for i in range(len(name) - 1):
            a, b = name[i], name[i + 1]
            if 0x1F1E6 <= ord(a) <= 0x1F1FF and 0x1F1E6 <= ord(b) <= 0x1F1FF and a != b:
                return chr(ord(a) - 0x1F1E6 + 65) + chr(ord(b) - 0x1F1E6 + 65)
    except Exception:
        pass
    return None


def _norm_server(s):
    d = {k: (s.get(k) if isinstance(s, dict) else None) for k in SERVER_FIELDS}
    if not d.get("id"):
        d["id"] = uuid.uuid4().hex[:10]
    if not d.get("name"):
        d["name"] = f"{d.get('type','http')}://{d.get('host','')}:{d.get('port','')}"
    for f in ("port", "latency"):
        try:
            d[f] = int(d[f]) if d[f] is not None and d[f] != "" else (None if f == "latency" else 0)
        except (ValueError, TypeError):
            d[f] = None if f == "latency" else 0
    d["enabled"] = True if d.get("enabled") is None else bool(d["enabled"])
    d["latency_ok"] = bool(d.get("latency_ok"))
    d["tested"] = bool(d.get("tested"))
    if not d.get("source"):
        d["source"] = "manual"
    if not d.get("country"):
        d["country"] = _country_from_name(d.get("name")) or None
    for k in SERVER_FIELDS:
        if k not in d:
            d[k] = None
    return d


@dataclass
class State:
    servers: list = field(default_factory=list)
    subs: list = field(default_factory=list)
    rules: list = field(default_factory=list)
    active_server_id: str = ""
    unmatched: str = "proxy"
    selection_mode: str = "manual"
    system_proxy: bool = False
    vpn: bool = False
    lan: dict = None
    connected_since: float = 0.0
    orig_proxy: dict = None
    warp_reg: dict = None
    logs: list = field(default_factory=list)
    core: object = None
    reloader: object = None
    conn_total: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_log(self, level, message):
        with self.lock:
            self.logs.append({"time": time.strftime("%H:%M:%S"), "level": level, "message": str(message)})
            if len(self.logs) > MAX_LOGS:
                self.logs = self.logs[-MAX_LOGS:]

    def server(self, sid):
        for s in self.servers:
            if s["id"] == sid:
                return s
        return None

    def active_server(self):
        return self.server(self.active_server_id)


def default_state():
    st = State()
    st.servers = [
        _norm_server({"type": "http", "host": "103.203.234.217", "port": 8080, "name": "103.203.234.217:8080", "source": "manual"}),
        _norm_server({"type": "http", "host": "13.127.222.175", "port": 443, "name": "13.127.222.175:443", "source": "manual"}),
    ]
    st.active_server_id = st.servers[1]["id"]
    return st


def load_state():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            st = State()
            st.servers = [_norm_server(s) for s in data.get("servers", [])]
            st.subs = data.get("subs", [])
            st.rules = data.get("rules", [])
            st.active_server_id = data.get("active_server_id", "")
            st.unmatched = data.get("unmatched", "proxy")
            st.selection_mode = data.get("selection_mode", "manual")
            if st.selection_mode not in ("manual", "auto"):
                st.selection_mode = "manual"
            st.system_proxy = data.get("system_proxy", False)
            st.vpn = data.get("vpn", False)
            st.connected_since = float(data.get("connected_since") or 0.0)
            st.orig_proxy = data.get("orig_proxy")
            st.warp_reg = data.get("warp_reg")
            st.lan = _norm_lan(data.get("lan"))
            if not st.servers:
                return default_state()
            if not st.server(st.active_server_id):
                st.active_server_id = st.servers[0]["id"]
            return st
        except Exception:
            pass
    return default_state()


def save_state(state):
    with state.lock:
        data = {
            "servers": state.servers,
            "subs": state.subs,
            "rules": state.rules,
            "active_server_id": state.active_server_id,
            "unmatched": state.unmatched,
            "selection_mode": state.selection_mode,
            "system_proxy": state.system_proxy,
            "vpn": state.vpn,
            "connected_since": state.connected_since,
            "orig_proxy": state.orig_proxy,
            "warp_reg": state.warp_reg,
            "lan": state.lan or {},
        }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except Exception as exc:
        print("save_state error:", exc)


LAN_USER_DEFAULT = "nikki"
LAN_FW_RULE = "NikkiNet LAN proxy"


def _b64_ps(script):
    """PowerShell -EncodedCommand принимает UTF-16LE base64."""
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def _norm_lan(d):
    d = d if isinstance(d, dict) else {}
    user = str(d.get("username") or "").strip()[:32]
    pw = str(d.get("password") or "")[:64]
    return {"enabled": bool(d.get("enabled")) and bool(user) and bool(pw),
            "username": user, "password": pw}


def gen_lan_password(n=12):
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))


_VIRTUAL_ADAPTER = re.compile(
    r"vEthernet|WSL|Docker|Hyper-V|VirtualBox|VMware|Loopback|Tailscale|ZeroTier|"
    r"Radmin|OpenVPN|WireGuard|Xray|happ|TAP-|Npcap|Bluetooth|\bVPN\b",
    re.I,
)


def _private_rank(ip):
    """0/1/2 — приоритет домашних сетей; -1 — не приватный IPv4."""
    try:
        p = [int(x) for x in str(ip).split(".")]
    except Exception:
        return -1
    if len(p) != 4 or any(b < 0 or b > 255 for b in p):
        return -1
    if p[0] == 192 and p[1] == 168:
        return 0
    if p[0] == 10:
        return 1
    if p[0] == 172 and 16 <= p[1] <= 31:
        return 2
    return -1


_LAN_IP_CACHE = {"ts": 0.0, "ip": ""}


def _detect_lan_ip():
    """Быстрое определение адреса в локальной сети (адаптер с маршрутом по умолчанию)."""
    if IS_WINDOWS:
        best = None
        try:
            ps = ("$idx = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue).ifIndex; "
                  "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
                  "Where-Object { $idx -contains $_.InterfaceIndex } | "
                  "ForEach-Object { $_.IPAddress + '|' + $_.InterfaceAlias }")
            r = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps],
                capture_output=True, text=True, timeout=8, creationflags=CREATE_NO_WINDOW,
            )
            for line in (r.stdout or "").splitlines():
                line = line.strip()
                if "|" not in line:
                    continue
                ip, alias = line.split("|", 1)
                if _VIRTUAL_ADAPTER.search(alias):
                    continue
                rank = _private_rank(ip)
                if rank >= 0 and (best is None or rank < best[0]):
                    best = (rank, ip)
        except Exception:
            best = None
        if best:
            return best[1]
    # запасной вариант: адрес источника маршрута по умолчанию
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return ""


def lan_ip(force=False):
    """Кэшированный адрес машины в локальной сети."""
    now = time.time()
    if not force and _LAN_IP_CACHE["ip"] and now - _LAN_IP_CACHE["ts"] < 60:
        return _LAN_IP_CACHE["ip"]
    ip = _detect_lan_ip()
    _LAN_IP_CACHE["ip"] = ip
    _LAN_IP_CACHE["ts"] = now
    return ip


def _firewall_lan(add):
    """Открыть/закрыть TCP-порт прокси, только для локальной подсети."""
    if not IS_WINDOWS:
        return False, "только Windows"
    name = LAN_FW_RULE
    if not add:
        ps = (f"Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue | "
              "Remove-NetFirewallRule -ErrorAction SilentlyContinue")
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps],
                capture_output=True, text=True, timeout=30, creationflags=CREATE_NO_WINDOW,
            )
        except Exception:
            pass
        return True, ""
    return _firewall_lan_add(name)


def _firewall_lan_add(name):
    """Правило без прав администратора не создать: пробуем elevated со скрытым окном."""
    ps_check = (f"$r = Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue; "
                "if ($r) { $r | Get-NetFirewallPortFilter | ForEach-Object { $_.LocalPort } }")
    port = str(core_mod.LAN_PORT)
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps_check],
            capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW,
        )
        if port in (r.stdout or "") and "LocalSubnet" in _rule_remote_address(name):
            return True, ""
    except Exception:
        pass
    ps_add = ("$ErrorActionPreference='Stop'; "
              f"Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue | "
              "Remove-NetFirewallRule -ErrorAction SilentlyContinue; "
              f"New-NetFirewallRule -DisplayName '{name}' -Direction Inbound -Action Allow "
              f"-Protocol TCP -LocalPort {core_mod.LAN_PORT} -RemoteAddress LocalSubnet -Profile Any | Out-Null")
    return _ps_elevated(ps_add, "NikkiNet")


def _rule_remote_address(name):
    ps = (f"Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue | "
          "Get-NetFirewallAddressFilter | ForEach-Object { $_.RemoteAddress }")
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps],
            capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW,
        )
        return r.stdout or ""
    except Exception:
        return ""


def _ps_elevated(ps, tag):
    """Выполнить PowerShell от администратора: сначала молча (UAC один раз), при отказе — видимое окно."""
    inner = ("$e = $null; try { " + ps + " } catch { $e = $_.Exception.Message }; "
             "if ($e) { Write-Host $e; exit 1 }")
    b64 = _b64_ps(inner)
    hidden = (f"try {{ $p = Start-Process -FilePath 'powershell.exe' -Verb RunAs -WindowStyle Hidden "
              f"-ArgumentList '-NoProfile','-NonInteractive','-EncodedCommand','{b64}' -Wait -PassThru; "
              "exit $p.ExitCode } catch { exit 2 }")
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", hidden],
            capture_output=True, text=True, timeout=120, creationflags=CREATE_NO_WINDOW,
        )
        if r.returncode == 0:
            return True, ""
        if r.returncode == 2:
            return False, "нужны права администратора: запустите NikkiNet от имени администратора"
    except Exception as exc:
        return False, str(exc)[:200]
    # не сработало молча — пробуем показать окно UAC/ошибки
    visible = (f"Start-Process -FilePath 'powershell.exe' -Verb RunAs "
               f"-ArgumentList '-NoProfile','-EncodedCommand','{b64}' -Wait")
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", visible],
            capture_output=True, text=True, timeout=300, creationflags=CREATE_NO_WINDOW,
        )
        if r.returncode == 0:
            return True, ""
        return False, (r.stderr or r.stdout or "правило не создано").strip()[:200]
    except Exception as exc:
        return False, str(exc)[:200]


def do_reload(state, force=False):
    cfg = core_mod.build_config(
        state.servers, state.active_server_id, state.rules, state.unmatched, state.vpn, LISTEN_PORT,
        state.selection_mode, lan=state.lan
    )
    return state.core.start(cfg, LISTEN_PORT, force=force)


class Reloader:
    def __init__(self, state):
        self.state = state
        self.trigger = threading.Event()
        self._lock = threading.Lock()
        self.force_flag = False
        self._last_start = 0.0
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def request(self, force=False):
        with self._lock:
            self.force_flag = self.force_flag or force
        self.trigger.set()

    def _loop(self):
        while True:
            self.trigger.wait(0.5)
            self.trigger.clear()
            time.sleep(0.2)
            self.trigger.clear()
            with self._lock:
                force = self.force_flag
                self.force_flag = False
            try:
                self._apply(force)
            except Exception as exc:
                self.state.add_log("error", f"reload: {exc}")

    RESTART_COOLDOWN = 30.0

    def _apply(self, force):
        st = self.state
        if st.core is None:
            return
        for _attempt in range(4):
            cfg = core_mod.build_config(
                st.servers, st.active_server_id, st.rules, st.unmatched, st.vpn, LISTEN_PORT,
                st.selection_mode, lan=st.lan
            )
            running = bool(st.core.running and st.core.proc and st.core.proc.poll() is None)
            if not force and running and st.core.cfg_hash == core_mod.config_hash(cfg):
                return
            # кулдаун: фоновые изменения применяем не чаще раза в 30с,
            # чтобы ядро не «мигало» при частых правках пула
            if not force and running:
                waited = time.time() - self._last_start
                if waited < self.RESTART_COOLDOWN:
                    time.sleep(self.RESTART_COOLDOWN - waited + 0.1)
                    continue
            ok, msg = st.core.start(cfg, LISTEN_PORT, force=force)
            if ok:
                self._last_start = time.time()
                if msg != "конфиг не изменился":
                    st.add_log("info", msg)
                return
            m = re.search(r"outbound\[(\d+)\]", msg or "")
            if m:
                idx = int(m.group(1))
                obs = cfg.get("outbounds") or []
                tag = obs[idx].get("tag") if 0 <= idx < len(obs) else None
                bad = next((s for s in st.servers if tag and core_mod.outbound_tag(s) == tag), None)
                if bad is not None:
                    st.add_log("error", f"Карантин битого узла: {bad.get('name')} ({(msg or '')[:120]})")
                    with st.lock:
                        st.servers = [s for s in st.servers if s is not bad]
                        if st.active_server_id == bad.get("id"):
                            alive = [s for s in st.servers if s.get("enabled")]
                            st.active_server_id = alive[0]["id"] if alive else ""
                    try:
                        save_state(st)
                    except Exception:
                        pass
                    continue
            st.add_log("error", f"reload: {(msg or '')[:200]}")
            return
        st.add_log("error", "reload: не удалось применить конфиг за отведённые попытки — повтор на следующем изменении")


# ---------- single instance / core lifecycle ----------

def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def acquire_single_instance():
    if os.path.exists(LOCK_FILE):
        try:
            old = int(open(LOCK_FILE).read().strip() or "0")
        except Exception:
            old = 0
        if old and old != os.getpid() and _pid_alive(old):
            # предыдущий экземпляр мог быть в процессе штатного выхода — даём ему время
            for _ in range(10):
                time.sleep(1)
                if not _pid_alive(old):
                    break
            else:
                print(f"Уже запущен (PID {old}). Остановите его или удалите {LOCK_FILE}.")
                sys.exit(0)
    with open(LOCK_FILE, "w") as fh:
        fh.write(str(os.getpid()))


def release_single_instance():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


def kill_port_owner(port):
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             creationflags=CREATE_NO_WINDOW).stdout
        pids = set()
        for ln in out.splitlines():
            if f":{port} " in ln and "LISTENING" in ln:
                parts = ln.split()
                if parts:
                    pids.add(parts[-1])
        for p in list(pids):
            try:
                q = subprocess.run(["tasklist", "/FI", "PID eq " + p], capture_output=True, text=True,
                                   creationflags=CREATE_NO_WINDOW).stdout
                if "sing-box.exe" in q:
                    subprocess.run(["taskkill", "/PID", p, "/F"], capture_output=True,
                                   creationflags=CREATE_NO_WINDOW)
            except Exception:
                pass
    except Exception:
        pass


# ---------- system proxy ----------

INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_REFRESH = 37
_we_enabled_system_proxy = False
_saved_proxy = None


def _refresh_internet_settings():
    try:
        wininet = ctypes.windll.wininet
        wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
        wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x1A, 0,
            ctypes.c_wchar_p("Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings"),
            0x0002, 5000, None,
        )
    except Exception:
        pass


def _read_proxy_settings():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        settings = {}
        for name, default in (("ProxyEnable", 0), ("ProxyServer", ""), ("ProxyOverride", "")):
            try:
                settings[name], _ = winreg.QueryValueEx(key, name)
            except FileNotFoundError:
                settings[name] = default
        winreg.CloseKey(key)
        settings["ProxyEnable"] = int(settings.get("ProxyEnable") or 0)
        settings["ProxyServer"] = settings.get("ProxyServer") or ""
        settings["ProxyOverride"] = settings.get("ProxyOverride") or ""
        return settings
    except Exception:
        return None


def _write_proxy_settings(settings):
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        0, winreg.KEY_SET_VALUE,
    )
    winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1 if settings.get("ProxyEnable") else 0)
    winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, settings.get("ProxyServer", ""))
    winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, settings.get("ProxyOverride", ""))
    winreg.CloseKey(key)
    _refresh_internet_settings()


def _merged_override(current):
    overs = []
    for tok in (current or "").split(";"):
        if tok and tok not in overs:
            overs.append(tok)
    for tok in ("<local>", "localhost", "127.*", "10.*", "<loopback>"):
        if tok.lower() not in {t.lower() for t in overs}:
            overs.append(tok)
    return ";".join(overs)


def set_system_proxy(enable, server=None, state=None):
    global _we_enabled_system_proxy, _saved_proxy
    if not IS_WINDOWS:
        return False, "Системный прокси доступен только в Windows"
    server = server or f"{LISTEN_HOST}:{LISTEN_PORT}"
    try:
        if enable:
            current = _read_proxy_settings()
            if current is None:
                current = {"ProxyEnable": 0, "ProxyServer": "", "ProxyOverride": ""}
            is_ours = server in str(current.get("ProxyServer", ""))
            if _saved_proxy is None and not (is_ours and current.get("ProxyEnable")):
                _saved_proxy = current
                if state:
                    state.orig_proxy = current
            _write_proxy_settings({
                "ProxyEnable": 1,
                "ProxyServer": server,
                "ProxyOverride": _merged_override(current.get("ProxyOverride", "")),
            })
        else:
            if _saved_proxy is not None:
                _write_proxy_settings(_saved_proxy)
                _saved_proxy = None
            else:
                _write_proxy_settings({"ProxyEnable": 0, "ProxyServer": "", "ProxyOverride": ""})
        _we_enabled_system_proxy = bool(enable)
        return True, "OK"
    except Exception as exc:
        return False, str(exc)


def restore_system_proxy():
    if _we_enabled_system_proxy or _saved_proxy is not None:
        set_system_proxy(False)


def startup_proxy_rollback(state):
    if not IS_WINDOWS:
        return
    if state.system_proxy:
        return
    cur = _read_proxy_settings()
    if not cur or not int(cur.get("ProxyEnable") or 0):
        return
    if f"{LISTEN_HOST}:{LISTEN_PORT}" not in str(cur.get("ProxyServer", "")):
        return
    orig = getattr(state, "orig_proxy", None) or {}
    if (orig.get("ProxyServer") or "") != f"{LISTEN_HOST}:{LISTEN_PORT}" and (orig.get("ProxyEnable") is None or orig.get("ProxyOverride") is not None):
        _write_proxy_settings(orig)
        state.add_log("info", "Откатил системный прокси после предыдущего запуска")
    else:
        _write_proxy_settings({"ProxyEnable": 0, "ProxyServer": "", "ProxyOverride": ""})
        state.add_log("info", "Выключил системный прокси (признак прерванного запуска)")


# ---------- subscriptions ----------

_sub_inflight = set()


def _cleanup_dead(state, orphan_min=30):
    """Авто-очистка: мёртвые (протестированные и не отвечающие) и брошенные
    непротестированные узлы подписок (тест потерян, напр. из-за перезапуска).
    Активные (обновляющиеся прямо сейчас) подписки не трогаем."""
    active = set()
    with state.lock:
        for x in state.subs:
            if x["id"] in _sub_inflight:
                active.add("sub:" + (x.get("name") or x["id"]))
        before = len(state.servers)
        prev_active = state.active_server_id
        now = time.time()
        keep = []
        for s in state.servers:
            if s.get("tested") and not s.get("latency_ok") and s.get("source") != "warp":
                continue
            if (not s.get("tested")
                    and str(s.get("source", "")).startswith("sub:")
                    and s.get("source") not in active
                    and s.get("added_ts")
                    and now - s["added_ts"] > orphan_min * 60):
                continue
            keep.append(s)
        state.servers = keep
        removed = before - len(keep)
        active_removed = bool(prev_active) and removed and not state.server(prev_active)
        if removed and active_removed:
            alive = [x for x in state.servers if x.get("enabled")]
            state.active_server_id = alive[0]["id"] if alive else ""
    if removed:
        # рестарт ядра нужен только если удалили АКТИВНЫЙ сервер:
        # мёртвые outbound'ы в конфиге безвредны — до следующего штатного reload
        if active_removed and state.reloader:
            state.reloader.request()
        try:
            save_state(state)
        except Exception:
            pass
        state.add_log("info", f"Авто-очистка: удалено нерабочих/брошенных серверов: {removed}")
    return removed


def _dedupe_key(s):
    return f"{s.get('type')}://{s.get('host')}:{s.get('port')}"


def add_servers(state, new_servers, source="manual"):
    added_list = []
    with state.lock:
        existing = {_dedupe_key(s) for s in state.servers}
        for ns in new_servers:
            ns = _norm_server(ns)
            ns["source"] = source
            ns["added_ts"] = time.time()
            if _dedupe_key(ns) in existing:
                continue
            if not ns.get("host") or not ns.get("port"):
                continue
            state.servers.append(ns)
            existing.add(_dedupe_key(ns))
            added_list.append(ns)
            if not state.server(state.active_server_id):
                state.active_server_id = ns["id"]
    return added_list


def _test_one(srv, timeout=TEST_TIMEOUT):
    res = core_mod.test_outbound(srv, timeout=timeout)
    ok = bool(res.get("ok")) and (res.get("latency_ms") or 10 ** 9) <= LATENCY_CUTOFF_MS
    srv["latency"] = res.get("latency_ms") if ok else None
    srv["latency_ok"] = ok
    srv["tested"] = True
    return ok


def _test_and_filter(state, servers, timeout=TEST_TIMEOUT):
    """Тестирует серверы; >1500мс и мёртвые сразу удаляет из пула. Возвращает выживших."""
    if not servers:
        return []
    with ThreadPoolExecutor(max_workers=TEST_WORKERS) as ex:
        list(ex.map(lambda s: _test_one(s, timeout), servers))
    failed_ids = {s["id"] for s in servers if not s["latency_ok"]}
    if failed_ids:
        with state.lock:
            state.servers = [s for s in state.servers if s["id"] not in failed_ids]
    return [s for s in servers if s["latency_ok"]]


# ---------- GeoIP (ip-api.com batch + кэш) ----------

_geo_lock = threading.Lock()
_geo_cache = None


def _load_geo():
    global _geo_cache
    with _geo_lock:
        if _geo_cache is None:
            try:
                with open(GEO_FILE, "r", encoding="utf-8") as fh:
                    _geo_cache = json.load(fh)
            except Exception:
                _geo_cache = {}
        return _geo_cache


def _save_geo():
    with _geo_lock:
        try:
            with open(GEO_FILE, "w", encoding="utf-8") as fh:
                json.dump(_geo_cache, fh, ensure_ascii=False)
        except Exception:
            pass


def enrich_countries(state, servers=None):
    """Определяет страну по IP (ip-api.com, батчи по 100, кэш в geo.json)."""
    cache = _load_geo()
    targets = [s for s in (servers or state.servers) if s.get("host") and not s.get("country")]
    if not targets:
        return 0

    def resolve(s):
        h = str(s.get("host") or "")
        if re.fullmatch(r"[\d.]+", h):
            return h
        try:
            return _socket.gethostbyname(h)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        ips = list(ex.map(resolve, targets))
    ip_by_id = {s["id"]: ip for s, ip in zip(targets, ips) if ip}
    need = sorted({ip for ip in ip_by_id.values() if ip not in cache})
    if need:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for i in range(0, len(need), 100):
            chunk = need[i:i + 100]
            try:
                req = urllib.request.Request(
                    "http://ip-api.com/batch?fields=status,countryCode,query",
                    data=json.dumps(chunk).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with opener.open(req, timeout=15) as r:
                    data = json.load(r)
                for item in data:
                    if item.get("status") == "success" and item.get("countryCode"):
                        cache[item.get("query")] = item["countryCode"]
            except Exception:
                break
        _save_geo()
    n = 0
    for s in targets:
        c = cache.get(ip_by_id.get(s["id"]))
        if c:
            s["country"] = c
            n += 1
    if n:
        save_state(state)
    return n


def _forced_sub_type(url):
    u = (url or "").lower()
    if "socks5" in u or "socks4" in u or "/socks" in u:
        return "socks"
    return None


def update_subscription(state, sub):
    sid = sub["id"]
    if sid in _sub_inflight:
        state.add_log("warn", f"Подписка {sub.get('name', sid)} уже обновляется")
        return 0, "уже обновляется"
    _sub_inflight.add(sid)
    try:
        ok, text = subs_mod.fetch_url(sub["url"])
        if not ok:
            sub["last_status"] = "ошибка: " + text[:120]
            state.add_log("error", f"Подписка {sub.get('name', sid)}: {text[:120]}")
            save_state(state)
            return 0, sub["last_status"]
        servers, errors = subs_mod.parse_subscription(text, sub.get("force_type") or _forced_sub_type(sub["url"]))
        if len(servers) > SUB_IMPORT_CAP:
            servers = random.sample(servers, SUB_IMPORT_CAP)
        sub["last_count"] = len(servers)
        sub["last_update"] = time.strftime("%Y-%m-%d %H:%M")
        sub["last_update_ts"] = time.time()
        sub["last_status"] = "проверяю..."
        added_list = add_servers(state, servers, source="sub:" + (sub.get("name") or sid))
        save_state(state)
        state.add_log("info", f"Подписка {sub.get('name', sid)}: новых {len(added_list)}, проверяю (<{LATENCY_CUTOFF_MS}мс)...")
        keep = _test_and_filter(state, added_list)
        if keep:
            try:
                enrich_countries(state, keep)
            except Exception:
                pass
        sub["last_status"] = f"ok: +{len(keep)} живых из {len(added_list)}" + (f"; пропущено парсером: {len(errors)}" if errors else "")
        if keep and state.reloader:
            state.reloader.request()
        save_state(state)
        state.add_log("info", f"Подписка {sub.get('name', sid)}: +{len(keep)} живых (из {len(added_list)})")
        return len(keep), sub["last_status"]
    finally:
        _sub_inflight.discard(sid)


def _active_fallback(state):
    """Сторож активного сервера: умер → мгновенно переключаемся на лучший живой
    (приоритет — та же страна), чтобы подключение не висело мёртвым."""
    act = state.active_server()
    if not act or not act.get("enabled"):
        return
    try:
        if _test_one(act):
            return
    except Exception:
        return
    state.add_log("warn", f"Активный сервер {act.get('name')} не отвечает — переключаюсь")
    with state.lock:
        cands = [s for s in state.servers
                 if s.get("enabled") and s.get("latency_ok") and s["id"] != act["id"]]
    cc = str(act.get("country") or "").upper()
    same = [s for s in cands if str(s.get("country") or "").upper() == cc]
    pool = same or cands
    if not pool:
        state.add_log("error", "Живых серверов для переключения нет")
        return
    pool.sort(key=lambda s: s.get("latency") or 10 ** 9)
    best = pool[0]
    state.active_server_id = best["id"]
    fast = False
    if state.core and state.core.running:
        if core_mod.clash_set_selector(core_mod.outbound_tag(best)):
            fast = True
    if not fast and state.reloader:
        state.reloader.request()
    save_state(state)
    state.add_log("info", f"Переключение на {best.get('name')} ({best.get('country')}, {best.get('latency')} мс){'' if fast else ' (перезапуск)'}")


def auto_updater_loop(state):
    while True:
        time.sleep(60)
        try:
            try:
                _cleanup_dead(state)
            except Exception:
                pass
            try:
                _active_fallback(state)
            except Exception:
                pass
            with state.lock:
                due = [s for s in state.subs
                       if s.get("auto") and s.get("interval_h", 0) > 0
                       and (not s.get("last_update_ts")
                            or time.time() - s["last_update_ts"] >= s["interval_h"] * 3600)]
            for sub in due:
                try:
                    update_subscription(state, sub)
                except Exception:
                    pass
        except Exception:
            pass


def _apply_update_async(state):
    """Скачивает релиз в фоне и инициирует перезапуск с обновлением."""
    def worker():
        global _restart_bat
        state.add_log("info", "Обновление: скачиваю новый релиз...")
        try:
            bat = appupdate.download_and_prepare(BASE_DIR)
        except Exception as exc:
            state.add_log("error", f"Обновление не удалось: {exc}")
            return
        _restart_bat = bat
        state.add_log("info", "Обновление скачано, перезапускаю приложение")
        _restart_event.set()
    threading.Thread(target=worker, daemon=True).start()


def _start_autoparse(state, opts):
    """Запускает фоновый автосбор и добавляет найденные серверы в NikkiNet."""
    def on_done(servers):
        added = add_servers(state, servers, source="autoparse")
        if added and state.reloader:
            state.reloader.request()
        save_state(state)
        state.add_log("info", f"Автосбор: добавлено {len(added)} серверов")
        return len(added)

    ok, err = netparse.start(opts, on_done)
    return {"ok": ok, "error": err, "status": netparse.status()}


# ---------- web ----------

class AdminServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, handler, state):
        super().__init__(addr, handler)
        self.state = state

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        # штатные обрывы соединения клиентом (браузер закрыл вкладку,
        # обновил страницу или оборвал preconnect-сокет) — не ошибка
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                            BrokenPipeError, TimeoutError)):
            return
        super().handle_error(request, client_address)


class AdminHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _body(self):
        cl = int(self.headers.get("Content-Length") or 0)
        if not cl:
            return {}
        try:
            return json.loads(self.rfile.read(cl).decode("utf-8"))
        except Exception:
            return {}

    def _json(self, obj, code=200):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        state = self.server.state
        if self.path == "/" or self.path.startswith("/index"):
            payload = ADMIN_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/api/state":
            self._json(self._state_dict())
        elif self.path == "/api/connect":
            total = _bump_conn_total(state)
            conns = []
            dl = ul = 0
            group_now = None
            if state.core and state.core.running:
                info = state.core.parse_connections()
                if info:
                    conns = info["connections"]
                    dl, ul = info["download_total"], info["upload_total"]
                else:
                    conns = state.core.parse_last_log()
                group_now = core_mod.clash_selector_now(core_mod.TAG_MAIN)
            self._json({
                "connections": conns, "total": total,
                "download": dl, "upload": ul,
                "group_now": group_now,
                "selection_mode": state.selection_mode,
            })
        elif self.path == "/api/log":
            txt = state.core.tail_log(120) if state.core else ""
            self._json({"lines": txt.splitlines()[-120:]})
        elif self.path == "/api/update/status":
            self._json(appupdate.status())
        elif self.path == "/api/parse/status":
            self._json(netparse.status())
        else:
            self.send_error(404)

    def _state_dict(self):
        state = self.server.state
        group_now = None
        if state.core and state.core.running:
            group_now = core_mod.clash_selector_now(core_mod.TAG_MAIN)
        return {
            "servers": state.servers,
            "subs": state.subs,
            "rules": state.rules,
            "active_server_id": state.active_server_id,
            "unmatched": state.unmatched,
            "selection_mode": state.selection_mode,
            "group_now": group_now,
            "group_mode": core_mod.proxy_group_tag(state.selection_mode),
            "system_proxy": state.system_proxy,
            "vpn": state.vpn,
            "lan": _norm_lan(state.lan),
            "lan_ip": lan_ip(),
            "lan_port": core_mod.LAN_PORT,
            "listen_port": LISTEN_PORT,
            "connected_since": state.connected_since,
            "admin": f"{ADMIN_HOST}:{ADMIN_PORT}",
            "listen": f"{'0.0.0.0' if _norm_lan(state.lan)['enabled'] else LISTEN_HOST}:{LISTEN_PORT}",
            "core": state.core.status() if state.core else {"running": False, "error": "ядро не инициализировано"},
            "tools_ready": core_mod.tools_ready(),
            "is_admin": is_admin(),
            "logs": state.logs[-30:],
        }

    def do_POST(self):
        state = self.server.state
        body = self._body()
        try:
            r = self._route(state, body)
        except Exception as exc:
            state.add_log("error", f"{self.path}: {exc}")
            return self._json({"error": str(exc)}, 500)
        if r is None:
            return self._json({"error": "неизвестный путь"}, 404)
        return self._json(r)

    def _route(self, state, b):
        p = self.path

        if p == "/api/update/check":
            latest = appupdate.check_latest()
            return {"ok": latest is not None, "status": appupdate.status()}

        if p == "/api/update/apply":
            if not appupdate.update_available():
                return {"ok": False, "error": "нет доступного обновления"}
            _apply_update_async(state)
            return {"ok": True, "message": "обновление скачивается, приложение перезапустится"}

        if p == "/api/parse/start":
            mode = b.get("mode") if b.get("mode") in ("internet", "lists") else "internet"

            def clamp(name, default, low, high):
                try:
                    value = int(b.get(name, default))
                except (TypeError, ValueError):
                    value = default
                return max(low, min(high, value))

            opts = {
                "mode": mode,
                "deep": bool(b.get("deep", True)),
                "max_pages": clamp("max_pages", 40, 5, 150),
                "per_source": clamp("per_source", 250, 20, 600),
                "max_total": clamp("max_total", 1200, 100, 4000),
                "deep_limit": clamp("deep_limit", 300, 10, 2000),
            }
            res = _start_autoparse(state, opts)
            if res.get("ok"):
                state.add_log("info", "Автосбор серверов запущен")
            return res

        if p == "/api/server/add":
            text = b.get("text")
            errors = []
            if text:
                new = []
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    s = subs_mod.uri_to_server(line)
                    if s:
                        new.append(s)
                    else:
                        errors.append(line[:60])
                added_list = add_servers(state, new, source="manual")
                if added_list and state.reloader:
                    state.reloader.request()
                save_state(state)
                state.add_log("info", f"Импорт: {len(added_list)} серверов")
                return {"ok": True, "added": len(added_list), "errors": errors}
            srv = b.get("server") or {}
            srv = _norm_server(srv)
            if not srv.get("host") or not srv.get("port"):
                return {"ok": False, "added": 0, "errors": ["укажите host и port"]}
            added_list = add_servers(state, [srv], source="manual")
            if added_list and state.reloader:
                state.reloader.request()
                save_state(state)
            return {"ok": True, "added": len(added_list)}

        if p == "/api/server/update":
            srv = state.server(b.get("id"))
            if not srv:
                return {"ok": False, "error": "не найден"}
            upd = {k: v for k, v in (b.get("server") or {}).items() if k in SERVER_FIELDS}
            with state.lock:
                for k, v in upd.items():
                    srv[k] = v
                if upd.get("type"):
                    for k in ("uuid", "username", "method", "flow", "security", "sni", "fp", "pbk", "sid", "transport", "path", "host_header", "service_name", "obfs", "obfs_password", "up", "down", "alpn", "allow_insecure", "congestion_control"):
                        if k not in upd:
                            srv[k] = ""
                srv["latency"] = None
            if state.reloader:
                state.reloader.request()
            save_state(state)
            return {"ok": True}

        if p == "/api/server/delete":
            sid = b.get("id")
            with state.lock:
                state.servers = [s for s in state.servers if s["id"] != sid]
                if state.active_server_id == sid:
                    state.active_server_id = state.servers[0]["id"] if state.servers else ""
            if state.reloader:
                state.reloader.request()
            save_state(state)
            return {"ok": True}

        if p == "/api/server/select":
            srv = state.server(b.get("id"))
            if not srv:
                return {"ok": False, "error": "не найден"}
            state.active_server_id = srv["id"]
            fast = False
            if state.core and state.core.running:
                if state.selection_mode == "auto":
                    fast = True
                elif srv.get("enabled"):
                    tag = core_mod.outbound_tag(srv)
                    if core_mod.clash_set_selector(tag):
                        fast = True
            if not fast and state.reloader:
                state.reloader.request()
            save_state(state)
            state.add_log("info" if fast else "info", f"Сервер: {srv['name']}{'' if fast else ' (перезапуск)'}")
            return {"ok": True, "fast": fast}

        if p == "/api/connect":
            country = str(b.get("country", "")).strip().upper()
            auto = country in ("", "AUTO", "*")
            with state.lock:
                if auto:
                    cands = [s for s in state.servers if s.get("enabled") and s.get("latency_ok")]
                else:
                    cands = [s for s in state.servers
                             if s.get("enabled") and s.get("latency_ok")
                             and str(s.get("country", "")).upper() == country]
            if not cands:
                return {"ok": False, "error": f"нет проверенных живых серверов в стране {country}" if not auto else "нет живых серверов"}
            cands.sort(key=lambda s: s.get("latency") or 10 ** 9)
            pool = cands[:5]
            with ThreadPoolExecutor(max_workers=min(5, len(pool))) as ex:
                list(ex.map(lambda s: _test_one(s), pool))
            live = [s for s in pool if s.get("latency_ok")]
            if not live:
                state.add_log("error", f"Подключение {country or 'авто'}: лучшие кандидаты не прошли повторный тест")
                return {"ok": False, "error": "серверы не ответили — нажмите «Проверить все» и повторите"}
            best = min(live, key=lambda s: s.get("latency") or 10 ** 9)
            state.active_server_id = best["id"]
            changed_mode = state.selection_mode != "manual"
            if changed_mode:
                state.selection_mode = "manual"
            fast = False
            if state.core and state.core.running and not changed_mode and best.get("enabled"):
                if core_mod.clash_set_selector(core_mod.outbound_tag(best)):
                    fast = True
            if not fast and state.reloader:
                state.reloader.request()
            sp_ok, sp_msg = set_system_proxy(True, state=state)
            state.system_proxy = bool(sp_ok)
            if sp_ok:
                state.connected_since = time.time()
            save_state(state)
            state.add_log("info", f"Подключено{'' if auto else ' (' + country + ')'}: {best['name']} ({best.get('latency')} мс){'' if fast else ' (перезапуск)'}")
            return {"ok": True, "fast": fast, "auto": auto, "server": best,
                    "sysproxy": bool(sp_ok), "sysproxy_error": None if sp_ok else sp_msg}

        if p == "/api/disconnect":
            sp_ok, sp_msg = set_system_proxy(False, state=state)
            state.system_proxy = False
            state.connected_since = 0.0
            save_state(state)
            state.add_log("info", "Отключено: системный прокси выключен")
            return {"ok": True, "sysproxy": False}

        if p == "/api/server/toggle":
            srv = state.server(b.get("id"))
            if not srv:
                return {"ok": False, "error": "не найден"}
            with state.lock:
                srv["enabled"] = bool(b.get("enabled"))
                if srv["id"] == state.active_server_id and not srv["enabled"]:
                    for s in state.servers:
                        if s["enabled"]:
                            state.active_server_id = s["id"]
                            break
                    else:
                        state.active_server_id = ""
            if state.reloader:
                state.reloader.request()
            save_state(state)
            return {"ok": True}

        if p == "/api/server/test":
            srv = state.server(b.get("id"))
            if not srv:
                return {"ok": False, "error": "не найден"}
            res = core_mod.test_outbound(srv)
            ok = bool(res.get("ok")) and (res.get("latency_ms") or 10 ** 9) <= LATENCY_CUTOFF_MS
            srv["latency"] = res.get("latency_ms") if ok else None
            srv["latency_ok"] = ok
            srv["tested"] = True
            state.add_log("info" if ok else "error",
                          f"Тест {srv['name']}: {'OK ' + str(res.get('latency_ms')) + ' мс' if ok else (f'>{LATENCY_CUTOFF_MS}мс — отброшен' if res.get('ok') else res.get('error'))}")
            save_state(state)
            return {"ok": True, "result": res, "accepted": ok}

        if p == "/api/server/testall":
            def job():
                try:
                    targets = [s for s in state.servers if s.get("enabled")] or list(state.servers)
                    state.add_log("info", f"Массовый тест: {len(targets)} серверов (отсечка {LATENCY_CUTOFF_MS}мс)...")
                    with ThreadPoolExecutor(max_workers=TEST_WORKERS) as ex:
                        list(ex.map(lambda s: _test_one(s), targets))
                    with state.lock:
                        failed_sub = [s for s in state.servers
                                      if s.get("tested") and not s.get("latency_ok")
                                      and str(s.get("source", "")).startswith("sub:")]
                        state.servers = [s for s in state.servers if s not in failed_sub]
                    ok_n = sum(1 for s in targets if s.get("latency_ok"))
                    try:
                        enrich_countries(state)
                    except Exception:
                        pass
                    state.reloader.request()
                    save_state(state)
                    state.add_log("info", f"Массовый тест: {ok_n}/{len(targets)} живых, удалено {len(failed_sub)} из подписок")
                except Exception as exc:
                    state.add_log("error", f"testall: {exc}")

            threading.Thread(target=job, daemon=True).start()
            return {"ok": True, "started": True, "total": len(state.servers)}

        if p == "/api/server/purge":
            removed = _cleanup_dead(state)
            return {"ok": True, "removed": removed}

        if p == "/api/geo/refresh":
            def geo_job():
                try:
                    n = enrich_countries(state)
                    state.add_log("info", f"Страны определены для {n} серверов")
                except Exception as exc:
                    state.add_log("error", f"geo: {exc}")

            threading.Thread(target=geo_job, daemon=True).start()
            return {"ok": True, "started": True}

        if p == "/api/warp/add":
            reg = state.warp_reg if warp_mod.reg_valid(state.warp_reg) else None
            reg_err = ""
            if not reg:
                try:
                    reg = warp_mod.register()
                except Exception as exc:
                    reg_err = str(exc)[:150]
                if not reg:
                    with state.lock:
                        cands = [s for s in state.servers
                                 if s.get("latency_ok") and s.get("enabled") and s.get("type") == "http" and s.get("tested")]
                    cands.sort(key=lambda s: s.get("latency") or 999999)
                    for cand in cands[:5]:
                        try:
                            reg = warp_mod.register(proxy=f"http://{cand['host']}:{cand['port']}")
                            break
                        except Exception:
                            continue
                if not reg:
                    msg = f"Не удалось зарегистрировать WARP: {reg_err}. Через прокси тоже не вышло."
                    state.add_log("error", "WARP: " + msg)
                    return {"ok": False, "error": msg}
                state.warp_reg = reg
            srv = _norm_server(warp_mod.make_server(reg))
            with state.lock:
                state.servers = [s for s in state.servers if s.get("source") != "warp"]
                state.servers.append(srv)
            res = core_mod.test_outbound(srv)
            srv["latency"] = res.get("latency_ms") if res.get("ok") else None
            srv["latency_ok"] = bool(res.get("ok"))
            srv["tested"] = True
            if state.reloader:
                state.reloader.request()
            save_state(state)
            state.add_log("info" if res.get("ok") else "warn",
                          f"WARP: {'работает, ' + str(res.get('latency_ms')) + ' мс' if res.get('ok') else 'зарегистрирован, но недоступен: ' + str(res.get('error'))[:120]}")
            return {"ok": True, "result": res, "server_id": srv["id"]}

        if p == "/api/subs/add":
            url = str(b.get("url", "")).strip()
            if not url:
                return {"ok": False, "error": "укажите URL"}
            sub = {
                "id": uuid.uuid4().hex[:10],
                "url": url,
                "name": str(b.get("name", "")).strip() or url[:40],
                "interval_h": int(b.get("interval_h") or 24),
                "auto": True,
                "force_type": str(b.get("type", "")).strip() or None,
                "last_update": "-",
                "last_count": 0,
                "last_status": "",
                "last_update_ts": 0,
            }
            state.subs.append(sub)
            save_state(state)
            threading.Thread(target=update_subscription, args=(state, sub), daemon=True).start()
            return {"ok": True, "started": True, "added": 0}

        if p == "/api/subs/update":
            sub = next((s for s in state.subs if s["id"] == b.get("id")), None)
            if not sub:
                return {"ok": False, "error": "не найдена"}
            threading.Thread(target=update_subscription, args=(state, sub), daemon=True).start()
            return {"ok": True, "started": True}

        if p == "/api/subs/set":
            sub = next((s for s in state.subs if s["id"] == b.get("id")), None)
            if not sub:
                return {"ok": False, "error": "не найдена"}
            with state.lock:
                sub.update({k: v for k, v in (b.get("fields") or {}).items() if k in sub})
            save_state(state)
            return {"ok": True}

        if p == "/api/subs/delete":
            with state.lock:
                state.subs = [s for s in state.subs if s["id"] != b.get("id")]
            save_state(state)
            return {"ok": True}

        if p == "/api/rules/save":
            rules = []
            for r in (b.get("rules") or []):
                rules.append({
                    "id": uuid.uuid4().hex[:8],
                    "action": r.get("action", "proxy"),
                    "server_id": r.get("server_id"),
                    "domain_suffix": list(r.get("domain_suffix") or []),
                    "keyword": list(r.get("keyword") or []),
                    "ip_cidr": list(r.get("ip_cidr") or []),
                    "ip_is_private": bool(r.get("ip_is_private")),
                    "enabled": True,
                })
            state.rules = rules
            if state.reloader:
                state.reloader.request()
            save_state(state)
            state.add_log("info", f"Правил сохранено: {len(rules)}")
            return {"ok": True}

        if p == "/api/mode":
            m = b.get("unmatched")
            sm = b.get("selection_mode")
            changed = False
            if m in ("proxy", "direct", "block") and m != state.unmatched:
                state.unmatched = m
                changed = True
            if sm in ("manual", "auto") and sm != state.selection_mode:
                state.selection_mode = sm
                changed = True
            if changed and state.reloader:
                state.reloader.request()
            save_state(state)
            return {"ok": True, "changed": changed}

        if p == "/api/system-proxy":
            ok, msg = set_system_proxy(bool(b.get("enabled")), state=state)
            if ok:
                state.system_proxy = bool(b.get("enabled"))
                if b.get("enabled"):
                    state.connected_since = state.connected_since or time.time()
                else:
                    state.connected_since = 0.0
                save_state(state)
                return {"ok": True}
            return {"ok": False, "error": msg}

        if p == "/api/vpn":
            enabled = bool(b.get("enabled"))
            if enabled and not is_admin():
                if not _relaunch_admin(state):
                    state.add_log("error", "Не удалось повысить права (UAC отклонён?)")
                    return {"ok": False, "error": "Не удалось повысить права. Запустите start.bat от администратора."}
                state.vpn = True
                save_state(state)
                _graceful_exit(self.server, delay=2.0)
                return {"ok": True, "relaunching": True,
                        "message": "Повышаю права, VPN включится после перезапуска..."}
            prev = state.vpn
            state.vpn = enabled
            ok, msg = do_reload(state, force=True)
            if not ok:
                state.vpn = prev
                do_reload(state, force=True)
                save_state(state)
                state.add_log("error", f"VPN: {msg[:150]}")
                return {"ok": False, "error": msg[:250]}
            state.add_log("info", "Полный VPN (TUN) " + ("включён" if enabled else "выключен"))
            save_state(state)
            return {"ok": True, "vpn": enabled}

        if p == "/api/lan":
            want = bool(b.get("enabled"))
            cur = _norm_lan(state.lan)
            user = str(b.get("username") if b.get("username") is not None else cur["username"]).strip()[:32]
            pw = str(b.get("password") if b.get("password") is not None else cur["password"])[:64]
            if not user:
                user = LAN_USER_DEFAULT
            if want:
                if len(user) < 2:
                    return {"ok": False, "error": "Логин должен быть не короче 2 символов"}
                if not pw:
                    pw = gen_lan_password()
                if len(pw) < 6:
                    return {"ok": False, "error": "Пароль должен быть не короче 6 символов"}
            prev = state.lan
            new = {"enabled": want, "username": user, "password": pw}
            state.lan = new
            ok, msg = do_reload(state, force=True)
            if not ok:
                state.lan = prev
                do_reload(state, force=True)
                return {"ok": False, "error": msg[:250]}
            fw_ok, fw_err = _firewall_lan(want)
            save_state(state)
            if want:
                state.add_log("info", f"Доступ из локальной сети включён: {user}@{lan_ip()}:{core_mod.LAN_PORT}")
            else:
                state.add_log("info", "Доступ из локальной сети выключен")
            res = {"ok": True, "lan": new, "address": f"{lan_ip()}:{core_mod.LAN_PORT}"}
            if want and not fw_ok:
                res["warning"] = ("Доступ включён, но порт не открыт в брандмауэре: " + fw_err[:160])
            return res

        if p == "/api/reload":
            if state.reloader:
                state.reloader.request(force=True)
            return {"ok": True, "message": "перезапуск запрошен"}

        if p == "/api/app/exit":
            state.add_log("info", "Выход по кнопке из панели")
            threading.Thread(target=_graceful_exit, args=(self.server, 1.5), daemon=True).start()
            return {"ok": True, "exiting": True}

        return None


# ---------- self-elevation ----------

def _relaunch_admin(state):
    py = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.isfile(py):
        py = sys.executable
    args = f'"{APP_SCRIPT}" --vpn'
    state.add_log("info", "Повышение прав (UAC)...")
    try:
        code = ctypes.windll.shell32.ShellExecuteW(None, "runas", py, args, BASE_DIR, 1)
        return int(code) > 32
    except Exception:
        return False


def _graceful_exit(admin_srv, delay=2.0):
    def worker():
        time.sleep(delay)
        try:
            if admin_srv.state.core:
                admin_srv.state.core.stop()
        except Exception:
            pass
        restore_system_proxy()
        try:
            # страховка: ни один sing-box не должен пережить выход.
            # ВАЖНО: до release_single_instance — иначе параллельно поднятое
            # новое приложение получит своё ядро убитым этим sweep'ом
            subprocess.run(
                ["taskkill", "/F", "/IM", "sing-box.exe"],
                capture_output=True, timeout=20, creationflags=0x08000000,
            )
        except Exception:
            pass
        release_single_instance()
        try:
            admin_srv.shutdown()
        except Exception:
            pass
        try:
            os._exit(0)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()


# ---------- counters ----------

_conn_seen = {"count": None}


def _bump_conn_total(state):
    if not state.core:
        return state.conn_total
    txt = state.core.tail_log(30000)
    n = len(re.findall(r"inbound connection from \S+", txt))
    prev = _conn_seen["count"]
    _conn_seen["count"] = n
    if prev is None:
        state.conn_total += n
    elif n >= prev:
        state.conn_total += (n - prev)
    else:
        state.conn_total += n
    return state.conn_total


def open_app_window(url):
    """Открывает панель как отдельное окно приложения (Edge/Chrome --app)."""
    env = os.environ
    pf = env.get("ProgramFiles", r"C:\Program Files")
    pf86 = env.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = env.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(pf86, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(local, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
    ]
    exe = ""
    for path in candidates:
        if path and os.path.isfile(path):
            exe = path
            break
    if exe:
        try:
            subprocess.Popen(
                [exe, "--app=" + url, "--window-size=1280,900"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
            return True
        except Exception:
            pass
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Не найден Microsoft Edge или Google Chrome.\n"
            "Установите Edge или Chrome — без них окно приложения не открыть.",
            "NikkiNet",
            0x10,
        )
    except Exception:
        pass
    return False


def run():
    state = load_state()
    want_vpn = "--vpn" in sys.argv
    if want_vpn:
        state.vpn = True

    state.core = core_mod.Core(log_cb=state.add_log)
    state.reloader = Reloader(state)
    admin_srv = AdminServer((ADMIN_HOST, ADMIN_PORT), AdminHandler, state)

    for x in state.subs:
        if "проверяю" in str(x.get("last_status", "")):
            x["last_status"] = "прервано (перезапуск приложения)"

    acquire_single_instance()
    kill_port_owner(LISTEN_PORT)
    kill_port_owner(core_mod.CLASH_PORT)
    try:
        # зачистка осиротевших sing-box (могли остаться после аварийного закрытия)
        subprocess.run(
            ["taskkill", "/F", "/IM", "sing-box.exe"],
            capture_output=True, timeout=30, creationflags=0x08000000,
        )
        time.sleep(0.5)
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq sing-box.exe"],
            capture_output=True, text=True, timeout=15, creationflags=0x08000000,
        ).stdout
        n = sum(1 for ln in out.splitlines() if "sing-box.exe" in ln.lower())
        if n:
            state.add_log(
                "warn",
                f"Обнаружен sing-box, который я не могу закрыть ({n} шт.) — вероятно, "
                f"запущен с правами администратора из другого сеанса. Он может держать порт 8888 и лог: "
                f"закройте его вручную (Диспетчер задач) или запустите приложение от администратора.",
            )
    except Exception:
        pass

    if not core_mod.tools_ready():
        state.add_log("warn", "sing-box не загружен, скачиваю...")
        try:
            core_mod.ensure_tools()
        except Exception as exc:
            state.add_log("error", f"Не удалось скачать sing-box: {exc}")

    if state.vpn and not is_admin():
        state.add_log("warn", "VPN (TUN) не может работать без прав администратора, режим выключен")
        state.vpn = False
        save_state(state)

    startup_proxy_rollback(state)

    try:
        _cleanup_dead(state)
    except Exception:
        pass

    do_reload(state, force=True)

    _lan = _norm_lan(state.lan)
    if _lan["enabled"]:
        fw_ok, fw_err = _firewall_lan(True)
        if fw_ok:
            state.add_log("info", f"Доступ из локальной сети: {_lan['username']}@{lan_ip()}:{core_mod.LAN_PORT}")
        else:
            state.add_log("error", f"Доступ из сети: правило брандмауэра не создано ({fw_err})")

    if state.system_proxy:
        ok, msg = set_system_proxy(True, f"{LISTEN_HOST}:{LISTEN_PORT}", state=state)
        state.add_log("info" if ok else "error", "Системный прокси восстановлен" if ok else f"Системный прокси: {msg}")

    threading.Thread(target=admin_srv.serve_forever, daemon=True).start()
    threading.Thread(target=auto_updater_loop, args=(state,), daemon=True).start()
    appupdate.start_background(
        lambda upd: state.add_log("info", f"Доступно обновление v{upd['version']} — обновитесь из панели (баннер сверху)")
    )

    def _startup_geo():
        time.sleep(5)
        try:
            n = enrich_countries(state)
            if n:
                state.add_log("info", f"Страны определены для {n} серверов")
                save_state(state)
        except Exception:
            pass

    threading.Thread(target=_startup_geo, daemon=True).start()

    print("=" * 60)
    print(" Proxy Manager (Nekoray/HApp-стиль)")
    print(f"  Версия: v{version.APP_VERSION} · обновления: github.com/{version.GITHUB_REPO}")
    print(f"  Локальный прокси: http://{LISTEN_HOST}:{LISTEN_PORT}  (http/socks mixed)")
    if _lan["enabled"]:
        print(f"  Для локальной сети: {lan_ip()}:{core_mod.LAN_PORT}  (логин {_lan['username']}, пароль задан)")
    print(f"  Панель управления: http://{ADMIN_HOST}:{ADMIN_PORT}")
    print("  Настройте браузер на прокси 127.0.0.1:8888")
    print("=" * 60)
    threading.Timer(1.0, lambda: open_app_window(f"http://{ADMIN_HOST}:{ADMIN_PORT}/")).start()

    try:
        while not _restart_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        try:
            if state.core:
                state.core.stop()
        except Exception:
            pass
        try:
            admin_srv.shutdown()
        except Exception:
            pass
        restore_system_proxy()
        release_single_instance()
        print("Готово.")

    if _restart_bat:
        print("Применяю обновление (apply_update.bat)...")
        try:
            appupdate.launch_apply_bat(_restart_bat)
        except Exception as exc:
            print("Не удалось запустить обновление:", exc)


if __name__ == "__main__":
    run()