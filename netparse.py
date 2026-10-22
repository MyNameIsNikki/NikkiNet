# -*- coding: utf-8 -*-
"""Встроенный автосбор бесплатных серверов из интернета.

Модуль не зависит от CLI-парсера: использует штатные subs.py/webscan.py/singbox.py.
Собирает публичные списки и share-ссылки, проверяет TCP и (опционально) sing-box,
затем отдаёт готовые серверы приложению через callback.
"""
import ipaddress
import random
import re
import socket
import threading
import time

import singbox
import subs
import webscan

# ---------------------------------------------------------------- настройки

SHARE_TYPES = {"vless", "vmess", "trojan", "ss", "hysteria2", "tuic"}
HTTP_TYPES = {"http", "https"}
SOCKS_TYPES = {"socks"}

DEFAULT_PER_SOURCE = 250
DEFAULT_MAX_TOTAL = 1200
DEFAULT_TCP_WORKERS = 80
DEFAULT_TCP_TIMEOUT = 3.0
DEFAULT_DEEP_WORKERS = 6
DEFAULT_DEEP_TIMEOUT = 10.0
DEFAULT_DEEP_LIMIT = 300
DEFAULT_CUTOFF_MS = 1500
DEFAULT_MAX_PAGES = 40
DEFAULT_DEPTH = 2
DEFAULT_DELAY = 0.3

# Проверенные публичные источники (обновлено 23.10.2026)
SOURCES = [
    ("TheSpeedX HTTP", "http", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"),
    ("TheSpeedX SOCKS5", "socks", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"),
    ("monosans HTTP", "http", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"),
    ("monosans SOCKS5", "socks", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt"),
    ("roosterkid HTTPS", "http", "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt"),
    ("ShiftyTR HTTP", "http", "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"),
    ("ShiftyTR SOCKS5", "socks", "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt"),
    ("hookzof SOCKS5", "socks", "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt"),
    ("proxifly HTTP", "http", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt"),
    ("proxifly SOCKS5", "socks", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt"),
    ("barry-far V2ray", "share", "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt"),
    ("Epodonios v2ray", "share", "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt"),
    ("mahdibland V2RayAggregator", "share", "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt"),
    ("Pawdroid Free-servers", "share", "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub"),
    ("ripaojiedian freenode", "share", "https://raw.githubusercontent.com/ripaojiedian/freenode/main/sub"),
    ("ALIILAPRO v2rayNG", "share", "https://raw.githubusercontent.com/ALIILAPRO/v2rayNG-Config/main/server.txt"),
    ("ermaozi get_subscribe", "share", "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt"),
    ("freefq free", "share", "https://raw.githubusercontent.com/freefq/free/master/v2"),
    ("free-proxy-list", "web-http", "https://free-proxy-list.net/"),
    ("sslproxies", "web-http", "https://www.sslproxies.org/"),
    ("us-proxy", "web-http", "https://www.us-proxy.org/"),
    ("socks-proxy.net", "web-socks", "https://www.socks-proxy.net/"),
    ("proxyspace HTTP", "web-http", "https://proxyspace.pro/http.txt"),
    ("proxyspace SOCKS5", "web-socks", "https://proxyspace.pro/socks5.txt"),
    ("spys.me HTTP", "web-http", "https://spys.me/proxy.txt"),
    ("spys.me SOCKS", "web-socks", "https://spys.me/socks.txt"),
    ("my-proxy", "web-http", "https://www.my-proxy.com/free-proxy-list.html"),
    ("scdn.io", "web-http", "https://proxy.scdn.io/api/get_proxy.php?protocol=http&count=50"),
    ("openproxylist HTTP", "web-http", "https://api.openproxylist.xyz/http.txt"),
    ("openproxylist SOCKS5", "web-socks", "https://api.openproxylist.xyz/socks5.txt"),
    ("proxydb", "web-http", "https://www.proxydb.net/"),
]

SEEDS = [
    "https://v2cross.com/free-v2ray-nodes/",
    "https://v2cross.com/1884.html",
    "https://v2rayse.com/free-node",
    "https://clashnode.com/free-node/",
    "https://freeclashnode.com/free-node/",
    "https://nodefree.org/",
    "https://v2rayng.com/",
    "https://v2ray.download/",
    "https://www.v2ray.cool/",
    "https://v2rayshare.net/",
    "https://free-proxy-list.net/",
    "https://www.sslproxies.org/",
    "https://www.us-proxy.org/",
    "https://www.socks-proxy.net/",
    "https://www.my-proxy.com/free-proxy-list.html",
    "https://proxyspace.pro/",
    "https://spys.me/",
    "https://www.proxydb.net/",
]

QUERIES = [
    "free vless subscription link",
    "free vmess configs",
    "free trojan proxy list",
    "free shadowsocks servers",
    "free hysteria2 nodes",
    "free socks5 proxy list",
    "free proxy list txt",
]

_HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9\.\-]{0,251}[a-z0-9])?$", re.I)

# ---------------------------------------------------------------- состояние

_LOCK = threading.Lock()
_STATE = {
    "running": False,
    "phase": "ожидание",
    "message": "",
    "found": 0,
    "alive": 0,
    "working": 0,
    "added": 0,
    "started": 0.0,
    "finished": 0.0,
    "log": [],
}


def status():
    with _LOCK:
        out = dict(_STATE)
        out["log"] = list(_STATE["log"])
        out["elapsed"] = int(time.time() - _STATE["started"]) if _STATE["started"] else 0
        return out


def _set(**kw):
    with _LOCK:
        _STATE.update(kw)


def _log(msg):
    msg = str(msg)
    with _LOCK:
        _STATE["log"].append("%s  %s" % (time.strftime("%H:%M:%S"), msg))
        if len(_STATE["log"]) > 80:
            _STATE["log"] = _STATE["log"][-80:]
    print("[autoparse]", msg, flush=True)


# ---------------------------------------------------------------- утилиты

def _port(value):
    try:
        p = int(value)
    except (TypeError, ValueError):
        return 0
    return p if 1 <= p <= 65535 else 0


def _host_ok(host):
    host = str(host or "").strip().lower().strip("[]").rstrip(".")
    if not host or " " in host or "/" in host or len(host) > 253:
        return ""
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            return ""
        return host
    except ValueError:
        pass
    if "." not in host or host.startswith(".") or host.endswith("."):
        return ""
    if host.endswith((".local", ".lan", ".internal", ".home", ".arpa")):
        return ""
    return host if _HOST_RE.match(host) else ""


def _country(name):
    try:
        name = str(name or "")
        for i in range(len(name) - 1):
            a, b = name[i], name[i + 1]
            if 0x1F1E6 <= ord(a) <= 0x1F1FF and 0x1F1E6 <= ord(b) <= 0x1F1FF and a != b:
                return chr(ord(a) - 0x1F1E6 + 65) + chr(ord(b) - 0x1F1E6 + 65)
    except Exception:
        pass
    return None


def _normalize(raw, source_name):
    if not isinstance(raw, dict):
        return None
    typ = str(raw.get("type") or "http").lower().strip()
    if typ in ("socks5", "socks5h", "socks4", "socks4a"):
        typ = "socks"
    if typ not in (SHARE_TYPES | HTTP_TYPES | SOCKS_TYPES):
        return None
    host = _host_ok(raw.get("host"))
    port = _port(raw.get("port"))
    if not host or not port:
        return None
    s = {k: raw.get(k) for k in (
        "uuid", "username", "password", "method", "flow", "security", "sni", "fp",
        "pbk", "sid", "transport", "path", "host_header", "service_name", "obfs",
        "obfs_password", "up", "down", "alpn", "allow_insecure",
        "congestion_control", "privkey", "peer_pubkey", "local_addrs", "reserved", "mtu",
    )}
    s["type"] = typ
    s["host"] = host
    s["port"] = port
    name = str(raw.get("name") or "").strip() or "%s://%s:%s" % (typ, host, port)
    s["name"] = name[:120]
    s["country"] = raw.get("country") or _country(name)
    s["enabled"] = True
    s["tested"] = False
    s["latency_ok"] = False
    s["latency"] = None
    s["source"] = "autoparse:%s" % source_name
    return s


def _key(s):
    return "%s://%s:%s" % (s.get("type"), s.get("host"), s.get("port"))


def _tcp_one(s, timeout):
    try:
        t0 = time.time()
        with socket.create_connection((s["host"], s["port"]), timeout=timeout):
            return int((time.time() - t0) * 1000)
    except Exception:
        return None


def _tcp_filter(cands, workers, timeout):
    alive = []
    if not cands:
        return alive
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda s: _tcp_one(s, timeout), cands))
    for s, ms in zip(cands, results):
        if ms is not None:
            s["_tcp"] = ms
            alive.append(s)
    return alive


def _deep_one(s):
    try:
        res = singbox.test_outbound(s, timeout=DEFAULT_DEEP_TIMEOUT)
    except Exception as exc:
        return False, str(exc)[:80]
    ok = bool(res.get("ok")) and (res.get("latency_ms") or 10 ** 9) <= DEFAULT_CUTOFF_MS
    s["latency"] = int(res["latency_ms"]) if ok else None
    s["latency_ok"] = ok
    s["tested"] = True
    return ok, res.get("error") or ""


# ---------------------------------------------------------------- сбор

def _fetch_source(item, per_source):
    name, kind, url = item
    ok, text = subs.fetch_url(url, timeout=40)
    if not ok:
        return name, [], str(text)[:120]
    raw = []
    try:
        if kind in ("http", "socks"):
            servers, _ = subs.parse_subscription(text, force_type=kind)
            raw = servers or []
        elif kind == "share":
            servers, _ = subs.parse_subscription(text)
            raw = servers or []
        else:
            default = "socks" if kind == "web-socks" else "http"
            raw = webscan.extract_servers(text, default_type=default, url=url) or []
    except Exception as exc:
        return name, [], str(exc)[:120]
    if len(raw) > per_source:
        raw = random.sample(raw, per_source)
    return name, raw, ""


def _collect_sources(opts):
    from concurrent.futures import ThreadPoolExecutor
    per = int(opts.get("per_source") or DEFAULT_PER_SOURCE)
    todo = list(SOURCES)
    total = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda it: _fetch_source(it, per), todo))
    for name, raw, err in results:
        if err:
            _log("источник %s: ошибка %s" % (name, err))
            continue
        norm = []
        for item in raw:
            s = _normalize(item, name)
            if s:
                norm.append(s)
        _log("источник %s: %d" % (name, len(norm)))
        total.extend(norm)
    return total


def _collect_web(opts):
    pages = int(opts.get("max_pages") or DEFAULT_MAX_PAGES)
    depth = int(opts.get("depth") or DEFAULT_DEPTH)
    raw, page_stats = webscan.crawl(
        SEEDS, max_pages=pages, max_depth=depth,
        delay=DEFAULT_DELAY, timeout=15.0, respect_robots=True, log=_log)
    out = []
    for item in raw:
        s = _normalize(item, str(item.get("_source") or "web"))
        if s:
            out.append(s)
    ok_pages = sum(1 for p in page_stats if p.get("servers"))
    _log("обход сайтов: страниц %d, с серверами %d, найдено %d"
         % (len(page_stats), ok_pages, len(out)))
    return out


def _dedupe(items):
    seen = set()
    out = []
    for s in items:
        k = _key(s)
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def _worker(opts, on_done):
    try:
        mode = str(opts.get("mode") or "internet")
        deep = bool(opts.get("deep", True))
        max_total = int(opts.get("max_total") or DEFAULT_MAX_TOTAL)

        _set(phase="сбор источников", message="читаю публичные списки")
        _log("старт: режим=%s, глубокая проверка=%s" % (mode, "да" if deep else "нет"))
        cands = _collect_sources(opts)

        if mode == "internet":
            _set(phase="обход сайтов", message="ищу серверы на публичных страницах")
            cands.extend(_collect_web(opts))

        cands = _dedupe(cands)
        _set(found=len(cands), message="кандидатов: %d" % len(cands))
        _log("уникальных кандидатов: %d" % len(cands))

        # share-узлы ценнее обычных прокси — даём им приоритет
        share = [s for s in cands if s["type"] in SHARE_TYPES]
        other = [s for s in cands if s["type"] not in SHARE_TYPES]
        random.shuffle(share)
        random.shuffle(other)
        cands = (share + other)[:max_total]

        _set(phase="проверка TCP", message="проверяю доступность %d" % len(cands))
        alive = _tcp_filter(cands, DEFAULT_TCP_WORKERS, DEFAULT_TCP_TIMEOUT)
        _set(alive=len(alive), message="TCP-живых: %d" % len(alive))
        _log("TCP-живых: %d из %d" % (len(alive), len(cands)))

        working = []
        if deep and alive:
            limit = int(opts.get("deep_limit") or DEFAULT_DEEP_LIMIT)
            sample = list(alive)
            random.shuffle(sample)
            if limit > 0:
                sample = sample[:limit]
            _set(phase="проверка sing-box", message="проверяю %d через sing-box" % len(sample))
            _log("глубокая проверка: %d" % len(sample))
            from concurrent.futures import ThreadPoolExecutor, as_completed
            done = 0
            with ThreadPoolExecutor(max_workers=DEFAULT_DEEP_WORKERS) as ex:
                futs = {ex.submit(_deep_one, s): s for s in sample}
                for fut in as_completed(futs):
                    s = futs[fut]
                    try:
                        ok, _err = fut.result()
                    except Exception:
                        ok = False
                    done += 1
                    if ok:
                        working.append(s)
                    if done % 20 == 0:
                        _set(working=len(working),
                             message="проверено %d/%d, рабочих %d" % (done, len(sample), len(working)))
                        _log("проверено %d/%d, рабочих %d" % (done, len(sample), len(working)))
        else:
            # без глубокой проверки оставляем только TCP-живые
            working = alive
            for s in working:
                s["tested"] = False
                s["latency_ok"] = False

        for s in working:
            s.pop("_tcp", None)
        _set(working=len(working), phase="добавление", message="добавляю %d" % len(working))
        added = 0
        if working:
            try:
                added = int(on_done(working) or 0)
            except Exception as exc:
                _log("ошибка добавления: %s" % exc)
        _set(added=added, phase="готово", finished=time.time(),
             message="рабочих %d, добавлено %d" % (len(working), added))
        _log("готово: рабочих %d, добавлено новых %d" % (len(working), added))
    except Exception as exc:
        _set(phase="ошибка", message=str(exc), finished=time.time())
        _log("ошибка: %s" % exc)
    finally:
        _set(running=False)
        with _LOCK:
            _STATE["finished"] = _STATE["finished"] or time.time()


def start(opts, on_done):
    """Запускает сбор в фоне. Возвращает (ok, error)."""
    with _LOCK:
        if _STATE["running"]:
            return False, "сбор уже выполняется"
        _STATE.update(running=True, phase="запуск", message="", found=0,
                      alive=0, working=0, added=0, started=time.time(),
                      finished=0.0, log=[])
    threading.Thread(target=_worker, args=(dict(opts), on_done), daemon=True).start()
    return True, ""
