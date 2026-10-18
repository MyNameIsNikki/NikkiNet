import hashlib
import json as _json
import os
import random
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
SINGBOX_EXE = os.path.join(TOOLS_DIR, "sing-box.exe")
WINTUN_DLL = os.path.join(TOOLS_DIR, "wintun.dll")
MAIN_CONFIG = os.path.join(TOOLS_DIR, "sing-box-config.json")
MAIN_LOG = os.path.join(TOOLS_DIR, "sing-box.log")

SINGBOX_VERSION = "v1.14.3"
SINGBOX_URL = (
    f"https://github.com/SagerNet/sing-box/releases/download/{SINGBOX_VERSION}/"
    f"sing-box-1.14.3-windows-amd64.zip"
)
WINTUN_URL = "https://www.wintun.net/builds/wintun-0.14.1.zip"

CREATE_NO_WINDOW = 0x08000000
OUTBOUND_TEST_TARGET = "example.com:80"

CLASH_HOST = "127.0.0.1"
CLASH_PORT = 9090

TAG_DIRECT = "direct"
TAG_BLOCK = "block"
TAG_MAIN = "MAIN"
TAG_AUTO = "AUTO"
TAG_DNS = "dns"

MAX_LOG_SIZE = 64 * 1024 * 1024

_CONN_RE = re.compile(r"connection from ([\d.]+):\d+ to (\S+)")
_DONE_RE = re.compile(r"connection to (\S+) closed")

# ---------- Windows Job Object: смерть родителя убивает все sing-box ----------
# Не даёт sing-box.exe оставаться сиротами (держать лог/порты) после
# аварийного закрытия приложения — KILL_ON_JOB_CLOSE срабатывает при
# закрытии последнего хэндла джоба самим Windows на выходе процесса.

_job_handle = None


def _ensure_job():
    global _job_handle
    if _job_handle is not None or os.name != "nt":
        return _job_handle
    try:
        import ctypes
        from ctypes import wintypes

        class _IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class _BASIC_LIMITS(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD)]

        class _EXT_LIMITS(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BASIC_LIMITS),
                ("IoInfo", _IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = ctypes.windll.kernel32
        h = k32.CreateJobObjectW(None, None)
        info = _EXT_LIMITS()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        k32.SetInformationJobObject(h, 9, ctypes.byref(info), ctypes.sizeof(info))  # JobObjectExtendedLimitInformation
        _job_handle = h
    except Exception:
        _job_handle = None
    return _job_handle


def _assign_job(proc):
    """Привязать дочерний процесс к джобу (умрёт вместе с нами при любом исходе)."""
    if proc is None:
        return
    h = _ensure_job()
    if h is None:
        return
    try:
        import ctypes
        from ctypes import wintypes
        ctypes.windll.kernel32.AssignProcessToJobObject(h, wintypes.HANDLE(proc._handle))
    except Exception:
        pass


def tools_ready():
    return os.path.isfile(SINGBOX_EXE)


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "proxy-app"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=180) as resp, open(dest, "wb") as fh:
        shutil.copyfileobj(resp, fh)


def extract_member(zip_path, predicate, dest_dir, final_name=None):
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if predicate(name):
                out = os.path.join(dest_dir, final_name or os.path.basename(name))
                with zf.open(name) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                return out
    return None


def ensure_tools():
    os.makedirs(TOOLS_DIR, exist_ok=True)
    if not os.path.isfile(SINGBOX_EXE):
        tmp = os.path.join(TOOLS_DIR, "sing-box.zip")
        try:
            download(SINGBOX_URL, tmp)
            out = extract_member(
                tmp,
                lambda n: n.lower().endswith("sing-box.exe"),
                TOOLS_DIR,
                final_name="sing-box.exe",
            )
            if not out:
                raise RuntimeError("sing-box.exe не найден в архиве")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    if not os.path.isfile(WINTUN_DLL):
        tmp = os.path.join(TOOLS_DIR, "wintun.zip")
        arch = "amd64"
        mach = os.environ.get("PROCESSOR_ARCHITECTURE", "").lower()
        if "arm64" in mach:
            arch = "arm64"
        elif mach in ("x86", "ia64"):
            arch = "x86"
        try:
            download(WINTUN_URL, tmp)
            out = extract_member(
                tmp,
                lambda n: n.lower().endswith("bin/%s/wintun.dll" % arch),
                TOOLS_DIR,
                final_name="wintun.dll",
            )
            if not out:
                out = extract_member(
                    tmp, lambda n: n.lower().endswith("wintun.dll"), TOOLS_DIR, final_name="wintun.dll"
                )
            if not out:
                raise RuntimeError("wintun.dll не найден в архиве")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    return True


def _clean(d):
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


UTLS_FP = {"chrome", "firefox", "edge", "safari", "360", "qq", "ios", "android", "random", "randomized"}


def _fp(value):
    v = str(value or "").strip().lower()
    return v if v in UTLS_FP else "chrome"


def build_outbound(server, tag):
    st = server.get("type", "http")
    host = server.get("host", "")
    port = int(server.get("port") or 0)
    if not host or not port:
        return None
    base = _clean({"type": st, "tag": tag, "server": host, "server_port": port})
    if st in ("http", "https"):
        base["type"] = "http"
        if server.get("username"):
            base["username"] = server["username"]
        if server.get("password"):
            base["password"] = server["password"]
        if st == "https":
            base["tls"] = {"enabled": True, "server_name": host}
        return base
    if st == "socks":
        base["type"] = "socks"
        base["version"] = "5"
        if server.get("username"):
            base["username"] = server["username"]
        if server.get("password"):
            base["password"] = server["password"]
        return base
    if st == "hysteria2":
        base["type"] = "hysteria2"
        base["password"] = server.get("password", "")
        tls = {"enabled": True, "server_name": server.get("sni") or host}
        if server.get("allow_insecure"):
            tls["insecure"] = True
        if server.get("alpn"):
            tls["alpn"] = [server["alpn"]]
        base["tls"] = tls
        if server.get("obfs") or server.get("obfs_password"):
            obfs = _clean({"type": server.get("obfs") or "salamander",
                           "password": server.get("obfs_password")})
            if obfs:
                base["obfs"] = obfs
        for k, v in (("up_mbps", server.get("up")), ("down_mbps", server.get("down"))):
            if v:
                try:
                    base[k] = int(v)
                except (ValueError, TypeError):
                    pass
        return base
    if st == "tuic":
        base["type"] = "tuic"
        base["uuid"] = server.get("uuid", "")
        if server.get("password"):
            base["password"] = server["password"]
        if server.get("congestion_control"):
            base["congestion_control"] = server["congestion_control"]
        tls = {"enabled": True, "server_name": server.get("sni") or host}
        if server.get("allow_insecure"):
            tls["insecure"] = True
        if server.get("alpn"):
            tls["alpn"] = [server["alpn"]]
        base["tls"] = tls
        return base
    if st == "wireguard":
        peer = _clean({
            "address": host,
            "port": port,
            "public_key": server.get("peer_pubkey"),
        })
        if server.get("reserved"):
            peer["reserved"] = server["reserved"]
        peer["allowed_ips"] = ["0.0.0.0/0", "::/0"]
        ep = _clean({
            "type": "wireguard",
            "tag": tag,
            "address": server.get("local_addrs"),
            "private_key": server.get("privkey"),
            "mtu": server.get("mtu") or 1280,
            "peers": [peer],
        })
        return ("endpoint", ep)
    if st in ("vless", "vmess", "trojan", "ss"):
        base["type"] = {"ss": "shadowsocks"}.get(st, st)
        if st == "vless":
            base["uuid"] = server.get("uuid", "")
            if str(server.get("flow") or "").strip().lower() == "xtls-rprx-vision":
                base["flow"] = "xtls-rprx-vision"
        elif st == "vmess":
            base["uuid"] = server.get("uuid", "")
            base["security"] = server.get("method") or "auto"
            base["alter_id"] = 0
        elif st == "trojan":
            base["password"] = server.get("password", "")
        elif st == "ss":
            base["method"] = server.get("method")
            base["password"] = server.get("password", "")
            if server.get("plugin"):
                base["plugin"] = server["plugin"]

        if st != "ss" and server.get("security") in ("tls", "reality"):
            tls = {"enabled": True, "server_name": server.get("sni") or host}
            if server.get("security") == "reality" and server.get("pbk"):
                tls["reality"] = _clean({
                    "enabled": True,
                    "public_key": server.get("pbk"),
                    "short_id": server.get("sid"),
                })
                tls["utls"] = _clean({"enabled": True, "fingerprint": _fp(server.get("fp"))})
            elif server.get("fp"):
                tls["utls"] = _clean({"enabled": True, "fingerprint": _fp(server.get("fp"))})
            base["tls"] = tls

        tr = server.get("transport") or "tcp"
        if tr == "ws":
            ws = _clean({"type": "ws", "path": server.get("path")})
            if server.get("host_header"):
                ws["headers"] = {"Host": server["host_header"]}
            base["transport"] = ws
        elif tr == "grpc":
            base["transport"] = _clean({"type": "grpc", "service_name": server.get("service_name")})
        elif tr in ("http", "h2"):
            hh = _clean({"type": "http", "path": server.get("path")})
            if server.get("host_header"):
                hh["host"] = [server["host_header"]]
            base["transport"] = hh
        return base
    return None


def outbound_tag(server):
    return "srv-" + str(server.get("id", "x"))[:8]


def proxy_group_tag(selection_mode):
    return TAG_AUTO if selection_mode == "auto" else TAG_MAIN


def build_config(servers, active_id, rules, unmatched, vpn, proxy_port, selection_mode="manual"):
    outbounds = [
        {"type": "direct", "tag": TAG_DIRECT},
        {"type": "block", "tag": TAG_BLOCK},
    ]
    endpoints = []
    tag_by_id = {}
    active_tag = None
    server_tags = []
    for s in servers:
        if not s.get("enabled"):
            continue
        tag = outbound_tag(s)
        ob = build_outbound(s, tag)
        if not ob:
            continue
        if isinstance(ob, tuple) and ob[0] == "endpoint":
            endpoints.append(ob[1])
        else:
            outbounds.append(ob)
        sid = s["id"]
        tag_by_id[sid] = tag
        server_tags.append(tag)
        if sid == active_id:
            active_tag = tag
    if active_tag is None and server_tags:
        active_tag = server_tags[0]

    groups = []
    if server_tags:
        if active_tag and active_tag in server_tags:
            default_main = active_tag
        else:
            default_main = server_tags[0]
        groups.append({
            "type": "selector",
            "tag": TAG_MAIN,
            "outbounds": list(server_tags),
            "default": default_main,
        })
        groups.append({"type": "urltest", "tag": TAG_AUTO, "outbounds": list(server_tags)})
    have_groups = bool(server_tags)
    outbounds.extend(groups)

    inbounds = [
        {
            "type": "mixed",
            "tag": "mixed-in",
            "listen": "127.0.0.1",
            "listen_port": proxy_port,
        }
    ]
    if vpn:
        inbounds.append({
            "type": "tun",
            "tag": "tun-in",
            "interface_name": "tun0",
            "address": ["198.18.0.1/30", "fdfe:dcba:9876::1/126"],
            "auto_route": True,
            "strict_route": False,
            "stack": "mixed",
            "mtu": 1500,
        })

    proxy_out = proxy_group_tag(selection_mode) if have_groups else TAG_DIRECT
    route_rules = [
        {"action": "route", "outbound": TAG_DIRECT, "ip_is_private": True},
        {"action": "route", "outbound": TAG_DIRECT, "domain_suffix": ["localhost"]},
    ]
    for r in rules or []:
        if not r.get("enabled", True):
            continue
        if r.get("action") == "direct":
            target = TAG_DIRECT
        elif r.get("action") == "block":
            route_rules.append({"action": "reject", **matcher(r)})
            continue
        elif r.get("action") == "proxy":
            target = proxy_out
        elif r.get("action") == "server":
            target = tag_by_id.get(r.get("server_id"))
            if target is None:
                continue
        else:
            continue
        route_rules.append({"action": "route", "outbound": target, **matcher(r)})

    final = {"proxy": proxy_out, "direct": TAG_DIRECT, "block": TAG_BLOCK}.get(unmatched, TAG_DIRECT)

    if vpn:
        dns_detour = proxy_out if unmatched == "proxy" else None
        doh = _clean({
            "type": "https",
            "tag": TAG_DNS,
            "server": "1.1.1.1",
            "detour": dns_detour,
        })
        dns_servers = [
            doh,
            _clean({"type": "https", "tag": "dns2", "server": "8.8.8.8", "detour": dns_detour}),
        ]
    else:
        dns_servers = [{"type": "local", "tag": TAG_DNS}]

    config = {
        "log": {"level": "info", "timestamp": True},
        "dns": {"servers": dns_servers, "final": TAG_DNS, "strategy": "ipv4_only"},
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {"rules": route_rules, "final": final, "default_domain_resolver": TAG_DNS},
        "experimental": {"clash_api": {"external_controller": f"{CLASH_HOST}:{CLASH_PORT}", "secret": ""}},
    }
    if endpoints:
        config["endpoints"] = endpoints
    if vpn:
        config["experimental"]["cache_file"] = {"enabled": True, "path": os.path.join(TOOLS_DIR, "cache.db")}
    return config


def matcher(r):
    m = {}
    if r.get("domain_suffix"):
        m["domain_suffix"] = r["domain_suffix"]
    if r.get("keyword"):
        m["domain_keyword"] = r["keyword"]
    if r.get("ip_cidr"):
        m["ip_cidr"] = r["ip_cidr"]
    if r.get("ip_is_private"):
        m["ip_is_private"] = True
    return m


def config_hash(config):
    return hashlib.sha256(_json.dumps(config, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _clash_url(path):
    return f"http://{CLASH_HOST}:{CLASH_PORT}{path}"


def _clash_json(method, path, body=None, timeout=4):
    data = body if body is None else _json.dumps(body).encode("utf-8")
    req = urllib.request.Request(_clash_url(path), data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return _json.loads(raw) if raw.strip() else {}


def clash_set_selector(target_tag, selector_tag=TAG_MAIN):
    """Быстрая смена сервера через Clash API без рестарта sing-box."""
    try:
        _clash_json("PUT", "/proxies/" + urllib.parse.quote(selector_tag, safe=""), {"name": target_tag})
        return True
    except Exception:
        return False


def clash_selector_now(selector_tag=TAG_MAIN):
    try:
        data = _clash_json("GET", "/proxies/" + urllib.parse.quote(selector_tag, safe=""))
        return data.get("now")
    except Exception:
        return None


def clash_urltest_delay(selector_tag=TAG_AUTO):
    try:
        data = _clash_json("GET", "/proxies/" + urllib.parse.quote(selector_tag, safe=""))
        return data.get("now"), data.get("delay")
    except Exception:
        return None, None


class Core:
    def __init__(self, log_cb=None):
        self.log_cb = log_cb or (lambda lvl, msg: None)
        self.proc = None
        self.lock = threading.Lock()
        self.running = False
        self.error = ""
        self.last_cfg = None
        self.cfg_hash = None
        self.stopping = False
        self._watchdog = None
        self._version_cache = None

    def _log(self, level, msg):
        try:
            self.log_cb(level, msg)
        except Exception:
            pass

    def version(self):
        if self._version_cache:
            return self._version_cache
        if not os.path.isfile(SINGBOX_EXE):
            return ""
        try:
            out = subprocess.run(
                [SINGBOX_EXE, "version"],
                capture_output=True, text=True, timeout=15, creationflags=CREATE_NO_WINDOW,
            )
            self._version_cache = (out.stdout or out.stderr or "").strip().splitlines()[0][:120]
            return self._version_cache
        except Exception:
            return ""

    def check_config(self, config=None):
        if config is not None:
            path = os.path.join(TOOLS_DIR, "check-config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json_dump(fh, config)
        else:
            path = MAIN_CONFIG
        try:
            out = subprocess.run(
                [SINGBOX_EXE, "check", "-c", path],
                capture_output=True, text=True, timeout=30, creationflags=CREATE_NO_WINDOW,
            )
            msg = (out.stdout or "") + "\n" + (out.stderr or "")
            if config is not None and os.path.exists(os.path.join(TOOLS_DIR, "check-config.json")):
                try:
                    os.remove(os.path.join(TOOLS_DIR, "check-config.json"))
                except Exception:
                    pass
            return (out.returncode == 0), msg.strip()
        except Exception as exc:
            return False, str(exc)

    def start(self, config, proxy_port=8888, force=False):
        with self.lock:
            h = config_hash(config)
            if not force and self.running and self.proc and self.proc.poll() is None:
                if self.cfg_hash == h:
                    self.last_cfg = config
                    return True, "конфиг не изменился"
            self.last_cfg = config
            if not os.path.isfile(SINGBOX_EXE):
                self.error = "sing-box не загружен"
                return False, self.error
            try:
                with open(MAIN_CONFIG, "w", encoding="utf-8") as fh:
                    json_dump(fh, config)
            except Exception as exc:
                self.error = f"Ошибка записи конфига: {exc}"
                return False, self.error
            ok, msg = self.check_config()
            if not ok:
                self.error = f"Конфиг не прошёл проверку: {msg[:300]}"
                self._log("error", self.error)
                return False, self.error
            self.stopping = False
            self.stop_locked()
            logf = open(MAIN_LOG, "w", encoding="utf-8", errors="ignore")
            try:
                self.proc = subprocess.Popen(
                    [SINGBOX_EXE, "run", "-c", MAIN_CONFIG, "-D", TOOLS_DIR],
                    stdout=logf,
                    stderr=subprocess.STDOUT,
                    creationflags=CREATE_NO_WINDOW,
                )
                _assign_job(self.proc)
            except Exception as exc:
                try:
                    logf.close()
                except Exception:
                    pass
                self.error = f"Не удалось запустить sing-box: {exc}"
                return False, self.error
            try:
                logf.close()
            except Exception:
                pass
            deadline = time.time() + 12
            while time.time() < deadline:
                if self.proc.poll() is not None:
                    self.error = f"sing-box завершился: {self.tail_log()[-250:]}"
                    self._log("error", self.error)
                    self.stop_locked()
                    return False, self.error
                if is_port_open("127.0.0.1", proxy_port):
                    self.running = True
                    self.error = ""
                    self.cfg_hash = h
                    self.stopping = False
                    self._log("info", "sing-box работает (порт %s)" % proxy_port)
                    if self._watchdog is None or not self._watchdog.is_alive():
                        self._watchdog = threading.Thread(target=self._watchdog_loop, args=(proxy_port,), daemon=True)
                        self._watchdog.start()
                    return True, "sing-box работает"
                time.sleep(0.25)
            self.error = "Порт не открылся: " + self.tail_log()[-250:]
            self._log("error", self.error)
            self.stop_locked()
            return False, self.error

    def _watchdog_loop(self, proxy_port):
        tries = 0
        window_start = time.time()
        while True:
            time.sleep(2)
            with self.lock:
                if self.stopping or self.proc is None:
                    self.running = False
                    return
                proc = self.proc
            if proc.poll() is None:
                self._maybe_truncate_log()
                continue
            with self.lock:
                if self.stopping or self.proc is None:
                    self.running = False
                    return
                self.running = False
            if time.time() - window_start > 120:
                tries = 0
                window_start = time.time()
            tries += 1
            if tries > 3:
                self._log("error", "sing-box повторно падает, останавливаю watchdog")
                self.running = False
                return
            self._log("warn", f"sing-box завершился неожиданно, перезапуск ({tries}/3)...")
            time.sleep(0.5)
            self.start(self.last_cfg, proxy_port, force=True)

    def _maybe_truncate_log(self):
        try:
            if os.path.getsize(MAIN_LOG) > MAX_LOG_SIZE:
                backup = MAIN_LOG + ".old"
                try:
                    if os.path.exists(backup):
                        os.remove(backup)
                except Exception:
                    pass
                try:
                    with open(MAIN_LOG, "r", encoding="utf-8", errors="ignore") as fh:
                        data = fh.read()
                    with open(backup, "w", encoding="utf-8", errors="ignore") as fh:
                        fh.write(data[-2_000_000:])
                except Exception:
                    pass
                try:
                    open(MAIN_LOG, "w", encoding="utf-8", errors="ignore").close()
                except Exception:
                    pass
        except Exception:
            pass

    def stop_locked(self):
        self.stopping = True
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=8)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
        self.running = False

    def stop(self):
        with self.lock:
            self.stop_locked()
            self._log("info", "sing-box остановлен")
        return True, "OK"

    def restart(self, config, proxy_port=8888):
        self.stop()
        return self.start(config, proxy_port)

    def status(self):
        return {
            "running": self.running,
            "pid": self.proc.pid if self.proc else None,
            "error": self.error,
            "version": self.version(),
        }

    def tail_log(self, lines=40):
        try:
            size = os.path.getsize(MAIN_LOG)
            block = 64 * 1024
            with open(MAIN_LOG, "r", encoding="utf-8", errors="ignore") as fh:
                if size > block:
                    fh.seek(size - block)
                    data = fh.read()
                else:
                    data = fh.read()
            return "".join(data.splitlines(keepends=True)[-lines:])
        except Exception:
            return ""

    def parse_connections(self):
        try:
            data = _clash_json("GET", "/connections")
            conns = []
            for c in data.get("connections", []):
                meta = c.get("metadata", {}) or {}
                src = meta.get("sourceIP", "")
                host = meta.get("host") or meta.get("destinationIP", "")
                port = str(meta.get("destinationPort", ""))
                target = host or src
                if port and port != "None":
                    target += ":" + port
                conns.append({"target": target, "age": 0, "type": c.get("type", ""), "id": c.get("id")})
            return {
                "connections": conns,
                "download_total": data.get("downloadTotal", 0),
                "upload_total": data.get("uploadTotal", 0),
            }
        except Exception:
            return None


def parse_last_log(self, window=60):
    text = self.tail_log(300)
    targets = {}
    for m in re.finditer(r"inbound/mixed\[[^\]]+\]: inbound connection to (\S+)", text):
        targets[m.group(1)] = 0
    return [{"target": t, "age": "—"} for t in targets]


def is_port_open(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def json_dump(fh, data):
    _json.dump(data, fh, ensure_ascii=False, indent=2)


_test_ports_in_use = set()
_test_ports_lock = threading.Lock()


def _acquire_test_port():
    """Уникальный тестовый порт внутри процесса (12+ параллельных воркеров)."""
    with _test_ports_lock:
        for _ in range(50):
            p = random.randint(21000, 30000)
            if p not in _test_ports_in_use:
                _test_ports_in_use.add(p)
                return p
        return random.randint(21000, 30000)


def _release_test_port(p):
    with _test_ports_lock:
        _test_ports_in_use.discard(p)


def test_outbound(server, timeout=15):
    tag = "test-" + str(random.randint(1000, 9999))
    port = _acquire_test_port()
    ob = build_outbound(server, tag)
    if not ob:
        return {"ok": False, "error": "неподдерживаемый тип: %s" % server.get("type")}
    is_endpoint = isinstance(ob, tuple) and ob[0] == "endpoint"
    ep_entry = ob[1] if is_endpoint else None
    ob_entry = None if is_endpoint else ob
    cfg = {
        "log": {"level": "error", "timestamp": False},
        "dns": {"servers": [{"type": "local", "tag": "dns"}], "final": "dns", "strategy": "ipv4_only"},
        "inbounds": [{"type": "mixed", "tag": "in", "listen": "127.0.0.1", "listen_port": port}],
        "outbounds": [
            {"type": "direct", "tag": "direct"},
            {"type": "block", "tag": "block"},
        ],
        "route": {"rules": [], "final": tag, "default_domain_resolver": "dns"},
    }
    if is_endpoint:
        cfg["endpoints"] = [ep_entry]
    else:
        cfg["outbounds"].append(ob_entry)
    cfg_path = os.path.join(TOOLS_DIR, "test-%d.json" % port)
    log_path = os.path.join(TOOLS_DIR, "test-%d.log" % port)
    proc = None
    logf = None
    try:
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json_dump(fh, cfg)
        logf = open(log_path, "w", encoding="utf-8", errors="ignore")
        proc = subprocess.Popen(
            [SINGBOX_EXE, "run", "-c", cfg_path, "-D", TOOLS_DIR],
            stdout=logf, stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW,
        )
        _assign_job(proc)
        deadline = time.time() + 10
        while time.time() < deadline and not is_port_open("127.0.0.1", port, 0.3):
            if proc.poll() is not None:
                break
            time.sleep(0.2)
        if not is_port_open("127.0.0.1", port):
            return {"ok": False, "error": "не удалось поднять тестовый инстанс"}
        start = time.time()
        sock = None
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
            sock.settimeout(timeout)
            sock.sendall(
                f"CONNECT {OUTBOUND_TEST_TARGET} HTTP/1.1\r\nHost: {OUTBOUND_TEST_TARGET}\r\n\r\n".encode()
            )
            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                resp += chunk
            if b" 200 " not in resp.split(b"\r\n", 1)[0]:
                line = resp.split(b"\r\n", 1)[0].decode("latin-1", "ignore")
                return {"ok": False, "error": line or "CONNECT не удался"}
            sock.sendall(
                b"GET / HTTP/1.1\r\n"
                b"Host: example.com\r\nConnection: close\r\n\r\n"
            )
            answer = b""
            while b"\r\n\r\n" not in answer:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                answer += chunk
            latency = round((time.time() - start) * 1000, 1)
            first = answer.split(b"\r\n", 1)[0].decode("latin-1", "ignore")
            if first.startswith("HTTP/"):
                status = first.split(" ", 2)[1] if len(first.split(" ", 2)) >= 2 else "0"
                if status.startswith("2") or status.startswith("3"):
                    return {"ok": True, "latency_ms": latency, "status": status}
                return {"ok": False, "error": f"HTTP {status}"}
            return {"ok": False, "error": first or "нет ответа"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
    finally:
        _release_test_port(port)
        try:
            if logf:
                logf.close()
        except Exception:
            pass
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        for p in (cfg_path, log_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass