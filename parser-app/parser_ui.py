# -*- coding: utf-8 -*-
"""NikkiNet Parser - локальное приложение для поиска бесплатных серверов.

Запускает небольшой HTTP-сервер на 127.0.0.1:8010 и открывает панель
в отдельном окне Edge/Chrome (режим --app). Только стандартная библиотека.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(BASE_DIR, "result")
SERVERS_FILE = os.path.join(RESULT_DIR, "servers.json")
LOCK_FILE = os.path.join(BASE_DIR, "parser_ui.lock")
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
APP_URL = "http://127.0.0.1:8000"
HOST = "127.0.0.1"
PORT = 8010
URL = "http://%s:%d/" % (HOST, PORT)
VERSION = "1.0.0"

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import netparse  # noqa: E402
import singbox  # noqa: E402

_STATE_LOCK = threading.Lock()
_UI = {
    "last_ts": 0.0,
    "merge_error": "",
    "merge_added": 0,
    "tools_busy": False,
    "tools_log": [],
    "app_cache": (0.0, False),
}

try:
    os.makedirs(RESULT_DIR, exist_ok=True)
except Exception:
    pass


# ---------------------------------------------------------------- окружение

def _singbox_candidates():
    return [
        os.path.join(TOOLS_DIR, "sing-box.exe"),
        singbox.SINGBOX_EXE,
        os.path.join(os.path.dirname(BASE_DIR), "prox", "tools", "sing-box.exe"),
        r"C:\Program Files\NikkiNet\tools\sing-box.exe",
    ]


def prepare_singbox():
    """Находит sing-box: свой tools, рядом с prox или в установленном NikkiNet."""
    for path in _singbox_candidates():
        if path and os.path.isfile(path):
            singbox.TOOLS_DIR = os.path.dirname(path)
            singbox.SINGBOX_EXE = path
            return path
    return ""


def singbox_path():
    path = prepare_singbox()
    return path if path and os.path.isfile(path) else ""


def _ensure_local_tools_dir():
    os.makedirs(TOOLS_DIR, exist_ok=True)
    singbox.TOOLS_DIR = TOOLS_DIR
    singbox.SINGBOX_EXE = os.path.join(TOOLS_DIR, "sing-box.exe")


def _tool_log(msg):
    line = "%s  %s" % (time.strftime("%H:%M:%S"), msg)
    with _STATE_LOCK:
        _UI["tools_log"].append(line)
        _UI["tools_log"] = _UI["tools_log"][-40:]
    print("[parser-ui]", msg, flush=True)


def download_singbox():
    with _STATE_LOCK:
        if _UI["tools_busy"]:
            return False, "загрузка уже идёт"
        _UI["tools_busy"] = True
        _UI["tools_log"] = []
    threading.Thread(target=_download_singbox_worker, daemon=True).start()
    return True, ""


def _download_singbox_worker():
    try:
        _ensure_local_tools_dir()
        _tool_log("скачиваю sing-box %s (около 82 МБ)..." % singbox.SINGBOX_VERSION)
        tmp = os.path.join(TOOLS_DIR, "sing-box.zip")
        singbox.download(singbox.SINGBOX_URL, tmp)
        _tool_log("распаковываю...")
        out = singbox.extract_member(
            tmp, lambda n: n.lower().endswith("sing-box.exe"),
            TOOLS_DIR, final_name="sing-box.exe")
        if os.path.exists(tmp):
            os.remove(tmp)
        if not out:
            raise RuntimeError("sing-box.exe не найден в архиве")
        _tool_log("готово: %s" % out)
    except Exception as exc:
        _tool_log("ошибка загрузки: %s" % exc)
    finally:
        with _STATE_LOCK:
            _UI["tools_busy"] = False


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _http_json(url, payload=None, timeout=15):
    data = None
    headers = {"User-Agent": "NikkiNet-Parser/%s" % VERSION}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        opener = _opener()
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
        return True, json.loads(raw.decode("utf-8", "replace") or "{}")
    except Exception as exc:
        return False, str(exc)


def _app_running(force=False):
    now = time.time()
    with _STATE_LOCK:
        ts, cached = _UI["app_cache"]
    if not force and now - ts < 5:
        return cached
    ok, data = _http_json(APP_URL + "/api/update/status", timeout=1.5)
    running = bool(ok and isinstance(data, dict))
    with _STATE_LOCK:
        _UI["app_cache"] = (now, running)
    return running


def _key(server):
    return "%s://%s:%s" % (server.get("type"), server.get("host"), server.get("port"))


def merge_into_app(servers):
    """Добавляет серверы в запущенный NikkiNet через его API."""
    ok, state = _http_json(APP_URL + "/api/state", timeout=4)
    if not ok or not isinstance(state, dict):
        return 0, "NikkiNet не запущен - результаты сохранены в result\\servers.json"
    existing = set()
    for item in state.get("servers") or []:
        if isinstance(item, dict):
            existing.add(_key(item))
    added = 0
    errors = 0
    for server in servers:
        if _key(server) in existing:
            continue
        ok, _ = _http_json(APP_URL + "/api/server/add",
                           {"server": server}, timeout=20)
        if ok:
            added += 1
            existing.add(_key(server))
        else:
            errors += 1
    if errors:
        return added, "добавлено %d, ошибок %d" % (added, errors)
    return added, ""


# ---------------------------------------------------------------- сбор

def _write_results(servers):
    os.makedirs(RESULT_DIR, exist_ok=True)
    if os.path.isfile(SERVERS_FILE) and os.path.getsize(SERVERS_FILE) > 2:
        backup = os.path.join(
            RESULT_DIR, "servers-backup-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
        try:
            shutil.copy2(SERVERS_FILE, backup)
        except Exception:
            pass
    clean = []
    for server in servers:
        clean.append({k: v for k, v in server.items() if not str(k).startswith("_")})
    tmp = SERVERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(clean, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, SERVERS_FILE)


def _finish(working, opts):
    combined = working
    try:
        existing = []
        if os.path.isfile(SERVERS_FILE):
            with open(SERVERS_FILE, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, list):
                existing = loaded
        fresh = {_key(server): server for server in working}
        seen = set()
        combined = []
        for server in existing:
            key = _key(server)
            if key in seen:
                continue
            seen.add(key)
            combined.append(fresh.pop(key, server))
        for key, server in fresh.items():
            seen.add(key)
            combined.append(server)
        _write_results(combined)
        netparse._log("в result\\servers.json всего: %d" % len(combined))
    except Exception as exc:
        netparse._log("ошибка записи результата: %s" % exc)
        return 0
    with _STATE_LOCK:
        _UI["last_ts"] = time.time()
        _UI["merge_error"] = ""
        _UI["merge_added"] = 0
    added = 0
    if opts.get("merge"):
        added, err = merge_into_app(working)
        with _STATE_LOCK:
            _UI["merge_added"] = added
            _UI["merge_error"] = err
        if err:
            netparse._log("NikkiNet: %s" % err)
        else:
            netparse._log("в NikkiNet добавлено: %d" % added)
    return added


def _read_results(limit=2000):
    if not os.path.isfile(SERVERS_FILE):
        return [], {}
    try:
        with open(SERVERS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return [], {}
    if not isinstance(data, list):
        return [], {}
    counts = {}
    for item in data:
        typ = str(item.get("type") or "?")
        counts[typ] = counts.get(typ, 0) + 1
    rows = []
    for item in data[:limit]:
        rows.append({
            "id": item.get("id", ""),
            "type": item.get("type", ""),
            "host": item.get("host", ""),
            "port": item.get("port", ""),
            "name": item.get("name", ""),
            "latency": item.get("latency"),
            "country": item.get("country", ""),
            "source": item.get("source", ""),
            "tested": bool(item.get("tested")),
            "latency_ok": bool(item.get("latency_ok")),
        })
    rows.sort(key=lambda r: (r["latency"] is None,
                             r["latency"] if r["latency"] is not None else 999999))
    return rows, counts


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "NikkiNetParser/" + VERSION

    def log_message(self, fmt, *args):
        return

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def _json(self, data, code=200):
        self._send(code, json.dumps(data, ensure_ascii=False))

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, PAGE.replace("__VERSION__", VERSION),
                       "text/html; charset=utf-8")
            return
        if path == "/favicon.ico":
            self._send(200, ICON_SVG, "image/svg+xml")
            return
        if path == "/api/status":
            status = netparse.status()
            with _STATE_LOCK:
                tools_busy = _UI["tools_busy"]
                tools_log = list(_UI["tools_log"])
                merge_error = _UI["merge_error"]
                merge_added = _UI["merge_added"]
                last_ts = _UI["last_ts"]
            rows, counts = _read_results(limit=1)
            self._json({
                "ok": True,
                "version": VERSION,
                "parse": status,
                "singbox": bool(singbox_path()),
                "singbox_path": singbox_path(),
                "app": _app_running(),
                "results": sum(counts.values()),
                "types": counts,
                "last_ts": last_ts,
                "merge_error": merge_error,
                "merge_added": merge_added,
                "tools": {"busy": tools_busy, "log": tools_log},
            })
            return
        if path == "/api/results":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                limit = max(1, min(5000, int(query.get("limit", ["2000"])[0])))
            except (TypeError, ValueError):
                limit = 2000
            rows, counts = _read_results(limit=limit)
            self._json({"ok": True, "rows": rows, "types": counts,
                        "total": sum(counts.values())})
            return
        self._json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}") \
                if length else {}
        except Exception:
            body = {}
        if path == "/api/start":
            self._json(self.start_parse(body))
            return
        if path == "/api/merge":
            rows, _ = _read_results(limit=5000)
            servers = []
            for row in rows:
                servers.append({
                    "type": row["type"], "host": row["host"], "port": row["port"],
                    "name": row["name"], "latency": row["latency"],
                    "country": row["country"], "source": row["source"],
                })
            added, err = merge_into_app(servers)
            with _STATE_LOCK:
                _UI["merge_added"] = added
                _UI["merge_error"] = err
            self._json({"ok": not err, "added": added, "error": err})
            return
        if path == "/api/tools/download":
            ok, err = download_singbox()
            self._json({"ok": ok, "error": err})
            return
        if path == "/api/open":
            try:
                os.startfile(RESULT_DIR)
                self._json({"ok": True})
            except Exception as exc:
                self._json({"ok": False, "error": str(exc)})
            return
        if path == "/api/exit":
            self._json({"ok": True, "exiting": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self._json({"ok": False, "error": "not found"}, 404)

    def start_parse(self, body):
        def clamp(name, default, low, high):
            try:
                value = int(body.get(name, default))
            except (TypeError, ValueError):
                value = default
            return max(low, min(high, value))

        mode = "internet" if body.get("mode") == "internet" else "lists"
        deep = bool(body.get("deep", True))
        if deep and not singbox_path():
            return {"ok": False,
                    "error": "sing-box не найден. Нажмите «Скачать sing-box» "
                             "или запустите без глубокой проверки."}
        opts = {
            "mode": mode,
            "deep": deep,
            "merge": bool(body.get("merge", True)),
            "per_source": clamp("per_source", 250, 20, 600),
            "max_total": clamp("max_total", 1200, 100, 4000),
            "deep_limit": clamp("deep_limit", 300, 10, 2000),
            "max_pages": clamp("max_pages", 40, 5, 150),
            "depth": clamp("depth", 2, 1, 4),
        }
        ok, err = netparse.start(opts, lambda servers: _finish(servers, opts))
        if ok:
            with _STATE_LOCK:
                _UI["merge_error"] = ""
            netparse._log("запуск из панели: режим=%s" % mode)
        return {"ok": ok, "error": err, "status": netparse.status()}


def open_window():
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in edge_paths + chrome_paths:
        if os.path.isfile(path):
            try:
                subprocess.Popen([path, "--app=" + URL, "--window-size=1280,920"],
                                 close_fds=True)
                return
            except Exception:
                pass
    webbrowser.open(URL)


ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<rect width="64" height="64" rx="14" fill="#101a33"/>'
    '<path d="M18 48V16h7l14 20V16h7v32h-7L25 28v20z" fill="#00c2b2"/></svg>'
)

PAGE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NikkiNet Parser</title>
<style>
:root{--bg:#0b1120;--card:#111a2e;--card2:#16213a;--line:#243252;--txt:#e8eefc;--mut:#8fa2c7;--acc:#00c2b2;--acc2:#31e0cf;--warn:#ffb454;--bad:#ff6b6b;--ok:#3ddc97}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 75% -10%,#123 0,var(--bg) 55%);color:var(--txt);font:14px/1.45 "Segoe UI",system-ui,sans-serif}
header{display:flex;align-items:center;gap:14px;padding:18px 26px;border-bottom:1px solid var(--line);background:rgba(11,17,32,.82);position:sticky;top:0;z-index:5;backdrop-filter:blur(10px)}
.logo{width:40px;height:40px;border-radius:11px;background:linear-gradient(135deg,#0e2a46,#00c2b2);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:22px;color:#04121a;box-shadow:0 0 24px rgba(0,194,178,.35)}
h1{font-size:18px;margin:0;letter-spacing:.3px}
.sub{color:var(--mut);font-size:12px;margin-top:2px}
.chips{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}
.chip{font-size:12px;padding:5px 10px;border-radius:999px;border:1px solid var(--line);color:var(--mut);background:#0e1729;white-space:nowrap}
.chip.ok{color:var(--ok);border-color:rgba(61,220,151,.4)}
.chip.bad{color:var(--bad);border-color:rgba(255,107,107,.4)}
main{max-width:1320px;margin:0 auto;padding:22px 22px 60px;display:grid;grid-template-columns:420px 1fr;gap:18px}
.panel{background:linear-gradient(180deg,var(--card),#0e1729);border:1px solid var(--line);border-radius:16px;padding:18px}
.panel h2{font-size:14px;margin:0 0 14px;letter-spacing:.4px;text-transform:uppercase;color:#b9c8e6}
.results{grid-column:1/-1}
.seg{display:flex;background:#0a1223;border:1px solid var(--line);border-radius:12px;padding:4px;gap:4px;margin-bottom:16px}
.seg button{flex:1;background:none;border:0;color:var(--mut);padding:10px;border-radius:9px;cursor:pointer;font-weight:600;font-size:13px}
.seg button.on{background:linear-gradient(135deg,#123a4a,#0d5d63);color:var(--acc2);box-shadow:inset 0 0 0 1px rgba(0,194,178,.35)}
.row{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:10px 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}
label.f{display:flex;flex-direction:column;gap:5px;color:var(--mut);font-size:12px}
label.f input{background:#0a1223;border:1px solid var(--line);border-radius:9px;color:var(--txt);padding:9px 10px;font-size:13px;outline:none}
label.f input:focus{border-color:var(--acc)}
.switch{display:flex;align-items:center;gap:10px;cursor:pointer;color:#c9d6ef;font-size:13px}
.switch input{appearance:none;width:42px;height:24px;border-radius:999px;background:#26324d;position:relative;cursor:pointer;transition:.2s;flex:0 0 auto}
.switch input:checked{background:var(--acc)}
.switch input:after{content:"";position:absolute;width:18px;height:18px;border-radius:50%;background:#fff;top:3px;left:3px;transition:.2s}
.switch input:checked:after{left:21px}
button.primary{width:100%;margin-top:16px;padding:13px;border:0;border-radius:11px;background:linear-gradient(135deg,#00c2b2,#2ee6c9);color:#04121a;font-weight:800;font-size:14px;cursor:pointer;letter-spacing:.3px}
button.primary:disabled{opacity:.5;cursor:default}
button.ghost{background:#0d1729;border:1px solid var(--line);color:#c9d6ef;padding:9px 13px;border-radius:9px;cursor:pointer;font-size:13px}
button.ghost:hover{border-color:var(--acc);color:var(--acc2)}
.hint{color:var(--mut);font-size:12px;margin-top:10px;min-height:16px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.stat{background:#0a1223;border:1px solid var(--line);border-radius:12px;padding:12px}
.stat b{display:block;font-size:22px;color:#fff;font-variant-numeric:tabular-nums}
.stat span{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
.phase{display:flex;align-items:center;gap:10px;margin:14px 0 6px}
.phase .dot{width:9px;height:9px;border-radius:50%;background:var(--mut)}
.phase.run .dot{background:var(--acc2);box-shadow:0 0 0 4px rgba(0,194,178,.15);animation:pulse 1.2s infinite}
@keyframes pulse{50%{opacity:.4}}
.msg{color:var(--mut);font-size:12px;min-height:18px}
.log{margin-top:12px;background:#070d1a;border:1px solid var(--line);border-radius:11px;padding:10px;height:190px;overflow:auto;font:11px/1.5 Consolas,monospace;color:#9fb2d6;white-space:pre-wrap}
.toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.toolbar h2{margin:0;font-size:14px;text-transform:uppercase;letter-spacing:.4px;color:#b9c8e6}
.toolbar .count{color:var(--mut);font-size:12px}
.toolbar input{flex:1;min-width:180px;background:#0a1223;border:1px solid var(--line);border-radius:9px;color:var(--txt);padding:9px 11px;outline:none}
.toolbar input:focus{border-color:var(--acc)}
.types{display:flex;gap:7px;flex-wrap:wrap;margin:0 0 12px}
.type{font-size:11px;padding:4px 9px;border-radius:999px;background:#0d1729;border:1px solid var(--line);color:var(--mut)}
.type b{color:#cfe6ff;font-weight:600}
.tblwrap{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:12px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{position:sticky;top:0;background:#0c1526;color:var(--mut);text-align:left;padding:10px 12px;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.4px;z-index:1}
td{padding:9px 12px;border-top:1px solid #1b2740;white-space:nowrap}
tbody tr:hover{background:#13203a;cursor:pointer}
td.mono{font-family:Consolas,monospace;color:#d7e5ff}
.pill{font-size:11px;padding:3px 8px;border-radius:999px;background:#0e2233;color:#7fe9dc;border:1px solid rgba(0,194,178,.25)}
.lat{color:var(--ok)}
.lat.slow{color:var(--warn)}
.empty{padding:38px;text-align:center;color:var(--mut);font-size:13px}
footer{max-width:1320px;margin:0 auto;padding:0 22px 30px;color:#6f82a8;font-size:12px}
a{color:var(--acc2)}
@media(max-width:980px){main{grid-template-columns:1fr}.results{grid-column:1}}
</style>
</head>
<body>
<header>
  <div class="logo">N</div>
  <div><h1>NikkiNet Parser</h1><div class="sub">Поиск и проверка бесплатных серверов</div></div>
  <div class="chips">
    <span class="chip" id="chip-app">NikkiNet: проверяю...</span>
    <span class="chip" id="chip-singbox">sing-box: проверяю...</span>
    <span class="chip">v__VERSION__</span>
  </div>
</header>
<main>
  <section class="panel">
    <h2>Сбор</h2>
    <div class="seg">
      <button data-mode="lists" class="on" onclick="setMode('lists')">Списки GitHub</button>
      <button data-mode="internet" onclick="setMode('internet')">Весь интернет</button>
    </div>
    <label class="switch"><input type="checkbox" id="deep" checked> Проверять через sing-box</label>
    <div class="grid">
      <label class="f">С сервера<input id="per_source" type="number" value="250" min="20" max="600"></label>
      <label class="f">Всего кандидатов<input id="max_total" type="number" value="1200" min="100" max="4000"></label>
      <label class="f">Проверить глубоко<input id="deep_limit" type="number" value="300" min="10" max="2000"></label>
      <label class="f">Страниц сайтов<input id="max_pages" type="number" value="40" min="5" max="150"></label>
    </div>
    <label class="switch" style="margin-top:6px"><input type="checkbox" id="merge" checked> Добавлять в NikkiNet</label>
    <button class="primary" id="start" onclick="startParse()">Собрать серверы</button>
    <div class="hint" id="hint">Глубокая проверка занимает больше времени, но оставляет только рабочие узлы.</div>
  </section>

  <section class="panel">
    <h2>Прогресс</h2>
    <div class="stats">
      <div class="stat"><b id="s-found">0</b><span>найдено</span></div>
      <div class="stat"><b id="s-alive">0</b><span>живы TCP</span></div>
      <div class="stat"><b id="s-working">0</b><span>рабочих</span></div>
      <div class="stat"><b id="s-added">0</b><span>добавлено</span></div>
    </div>
    <div class="phase" id="phase"><span class="dot"></span><b id="phase-text">ожидание</b></div>
    <div class="msg" id="msg">Готов к запуску.</div>
    <div class="log" id="log">Лог появится здесь.</div>
  </section>

  <section class="panel results">
    <div class="toolbar">
      <h2>Результаты</h2><span class="count" id="count">0 серверов</span>
      <input id="filter" placeholder="Фильтр: тип, хост, страна..." oninput="renderRows()">
      <button class="ghost" onclick="loadResults()">Обновить</button>
      <button class="ghost" onclick="mergeNow()">Добавить в NikkiNet</button>
      <button class="ghost" onclick="openFolder()">Папка результатов</button>
    </div>
    <div class="types" id="types"></div>
    <div class="tblwrap">
      <table>
        <thead><tr><th>Тип</th><th>Адрес</th><th>Задержка</th><th>Страна</th><th>Источник</th></tr></thead>
        <tbody id="rows"><tr><td colspan="5" class="empty">Пока пусто. Запустите сбор.</td></tr></tbody>
      </table>
    </div>
  </section>
</main>
<footer>Бесплатные узлы недоверенные: владелец сервера видит трафик. Не используйте их для банков, почты и рабочих аккаунтов.</footer>

<script>
let mode = 'lists';
let rows = [];
let wasRunning = false;
let timer = null;

function esc(value){
  return String(value == null ? '' : value)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}
function setMode(value){
  mode = value;
  document.querySelectorAll('.seg button').forEach(function(b){
    b.classList.toggle('on', b.dataset.mode === value);
  });
  document.getElementById('hint').textContent = value === 'internet'
    ? 'Обход публичных сайтов: медленнее, но больше источников. Поисковики часто блокируют запросы, поэтому используются проверенные сайты.'
    : 'Быстрый сбор из GitHub-списков и публичных списков прокси.';
}
function num(id){ return parseInt(document.getElementById(id).value, 10) || 0; }
async function api(path, body){
  const opt = body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)};
  const r = await fetch(path, opt);
  return await r.json();
}
async function startParse(){
  const btn = document.getElementById('start');
  btn.disabled = true;
  document.getElementById('hint').textContent = 'Запускаю сбор...';
  try{
    const res = await api('/api/start', {
      mode: mode,
      deep: document.getElementById('deep').checked,
      merge: document.getElementById('merge').checked,
      per_source: num('per_source'),
      max_total: num('max_total'),
      deep_limit: num('deep_limit'),
      max_pages: num('max_pages')
    });
    if(!res.ok){
      document.getElementById('hint').textContent = res.error || 'Не удалось запустить';
    }
  }catch(e){
    document.getElementById('hint').textContent = 'Ошибка: ' + e;
  }
  btn.disabled = false;
  poll();
}
async function poll(){
  clearTimeout(timer);
  try{
    const st = await api('/api/status');
    renderStatus(st);
  }catch(e){}
  timer = setTimeout(poll, 1200);
}
function renderStatus(st){
  if(!st || !st.ok) return;
  const p = st.parse || {};
  document.getElementById('s-found').textContent = p.found || 0;
  document.getElementById('s-alive').textContent = p.alive || 0;
  document.getElementById('s-working').textContent = p.working || 0;
  document.getElementById('s-added').textContent = p.added || 0;
  document.getElementById('phase-text').textContent = p.phase || 'ожидание';
  document.getElementById('phase').classList.toggle('run', !!p.running);
  let msg = p.message || '';
  if(p.elapsed) msg += ' · ' + p.elapsed + ' с';
  if(st.merge_error) msg += ' · ' + st.merge_error;
  document.getElementById('msg').textContent = msg;
  const log = (p.log || []).slice(-8).join('\n');
  const logBox = document.getElementById('log');
  logBox.textContent = log || 'Лог появится здесь.';
  logBox.scrollTop = logBox.scrollHeight;
  const sb = document.getElementById('chip-singbox');
  sb.textContent = st.singbox ? 'sing-box: готов' : 'sing-box: не найден';
  sb.className = 'chip ' + (st.singbox ? 'ok' : 'bad');
  if(!st.singbox){
    document.getElementById('hint').innerHTML = 'sing-box не найден. <a href="#" onclick="downloadTools();return false">Скачать (82 МБ)</a> или снимите галочку глубокой проверки.';
  }
  const app = document.getElementById('chip-app');
  app.textContent = st.app ? 'NikkiNet: запущен' : 'NikkiNet: не запущен';
  app.className = 'chip ' + (st.app ? 'ok' : 'bad');
  const running = !!p.running;
  document.getElementById('start').disabled = running;
  if(wasRunning && !running){
    document.getElementById('hint').textContent = 'Сбор завершён. Результаты сохранены.';
    loadResults();
  }
  wasRunning = running;
  if(!running && st.results !== undefined){
    document.getElementById('count').textContent = st.results + ' серверов';
  }
}
async function loadResults(){
  try{
    const res = await api('/api/results?limit=5000');
    rows = res.rows || [];
    const types = res.types || {};
    const box = document.getElementById('types');
    box.innerHTML = Object.keys(types).sort().map(function(k){
      return '<span class="type">' + esc(k) + ' <b>' + types[k] + '</b></span>';
    }).join('');
    document.getElementById('count').textContent = (res.total || rows.length) + ' серверов';
    renderRows();
  }catch(e){}
}
function renderRows(){
  const q = document.getElementById('filter').value.trim().toLowerCase();
  const body = document.getElementById('rows');
  const list = rows.filter(function(r){
    if(!q) return true;
    return [r.type, r.host, r.port, r.country, r.source, r.name].join(' ').toLowerCase().indexOf(q) >= 0;
  });
  if(!list.length){
    body.innerHTML = '<tr><td colspan="5" class="empty">Ничего не найдено.</td></tr>';
    return;
  }
  body.innerHTML = list.slice(0, 1500).map(function(r){
    const lat = r.latency == null ? '—' : Math.round(r.latency) + ' мс';
    const cls = r.latency != null && r.latency > 1000 ? 'lat slow' : 'lat';
    return '<tr onclick="copyRow(this)" data-addr="' + esc(r.host + ':' + r.port) + '">'
      + '<td><span class="pill">' + esc(r.type) + '</span></td>'
      + '<td class="mono">' + esc(r.host) + ':' + esc(r.port) + '</td>'
      + '<td class="' + cls + '">' + lat + '</td>'
      + '<td>' + esc(r.country || '—') + '</td>'
      + '<td>' + esc((r.source || '').replace('autoparse:', '')) + '</td></tr>';
  }).join('');
}
function copyRow(tr){
  const addr = tr.getAttribute('data-addr');
  if(!addr) return;
  if(navigator.clipboard){ navigator.clipboard.writeText(addr); }
  const hint = document.getElementById('hint');
  hint.textContent = 'Скопировано: ' + addr;
}
async function mergeNow(){
  const hint = document.getElementById('hint');
  hint.textContent = 'Добавляю в NikkiNet...';
  try{
    const res = await api('/api/merge', {});
    hint.textContent = res.ok ? ('Добавлено в NikkiNet: ' + res.added) : (res.error || 'Ошибка');
  }catch(e){ hint.textContent = 'Ошибка: ' + e; }
}
async function downloadTools(){
  const hint = document.getElementById('hint');
  hint.textContent = 'Загрузка sing-box...';
  try{
    const res = await api('/api/tools/download', {});
    if(!res.ok) hint.textContent = res.error || 'Не удалось начать загрузку';
  }catch(e){ hint.textContent = 'Ошибка: ' + e; }
}
async function openFolder(){
  try{ await api('/api/open', {}); }catch(e){}
}
loadResults();
poll();
</script>
</body>
</html>
"""


def main():
    global PORT, URL
    try:
        httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        # сервер уже запущен - просто открываем окно
        open_window()
        return 0
    threading.Timer(0.8, open_window).start()
    try:
        with open(LOCK_FILE, "w", encoding="ascii") as fh:
            fh.write(str(os.getpid()))
    except Exception:
        pass
    print("NikkiNet Parser %s: %s" % (VERSION, URL))
    print("sing-box: %s" % (singbox_path() or "не найден"))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        try:
            with open(LOCK_FILE, "r", encoding="ascii") as fh:
                pid = fh.read().strip()
            if pid == str(os.getpid()):
                os.remove(LOCK_FILE)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
