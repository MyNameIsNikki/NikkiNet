#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NikkiNet server parser.

Собирает бесплатные публичные прокси и конфиги из открытых источников,
проверяет доступность и складывает результат в папку result/.

Режимы:
  python parser.py --fast        собрать + быстрая TCP-проверка
  python parser.py --deep        собрать + проверка через sing-box (точная)
  python parser.py --retest      перепроверить result/servers.json
  python parser.py --merge-only  импортировать result/servers.json в NikkiNet
  python parser.py --stats       показать статистику результата
  python parser.py               интерактивное меню

Зависимости: только стандартная библиотека Python 3.8+.
"""

import argparse
import ipaddress
import json
import os
import random
import re
import shutil
import socket
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, ProxyHandler, build_opener

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(BASE_DIR, "result")
SOURCES_FILE = os.path.join(BASE_DIR, "sources.json")
SERVERS_FILE = os.path.join(RESULT_DIR, "servers.json")
PROXIES_FILE = os.path.join(RESULT_DIR, "proxies.txt")
REPORT_FILE = os.path.join(RESULT_DIR, "report.txt")
WEB_PAGES_FILE = os.path.join(RESULT_DIR, "web-pages.txt")
QUERIES_FILE = os.path.join(BASE_DIR, "queries.txt")
SEEDS_FILE = os.path.join(BASE_DIR, "seeds.txt")

API_BASE = "http://127.0.0.1:8000"

sys.path.insert(0, BASE_DIR)
try:
    import vpn_parsers as vp
except Exception as exc:  # pragma: no cover
    print("Не удалось загрузить vpn_parsers.py:", exc)
    raise SystemExit(1)
try:
    import webscan
except Exception as exc:  # pragma: no cover
    print("Не удалось загрузить webscan.py:", exc)
    raise SystemExit(1)

SERVER_FIELDS = [
    "id", "name", "type", "host", "port", "uuid", "username", "password",
    "method", "flow", "security", "sni", "fp", "pbk", "sid", "transport",
    "path", "host_header", "service_name", "enabled", "source", "latency",
    "latency_ok", "tested", "country", "added_ts",
    "obfs", "obfs_password", "up", "down", "alpn", "allow_insecure",
    "congestion_control", "privkey", "peer_pubkey", "local_addrs",
    "reserved", "mtu",
]

SHARE_TYPES = {"vless", "vmess", "trojan", "ss", "hysteria2", "tuic"}
HTTP_TYPES = {"http", "https"}
SOCKS_TYPES = {"socks"}

DEFAULT_PER_SOURCE = 400
DEFAULT_MAX_TOTAL = 3500
DEFAULT_TCP_WORKERS = 100
DEFAULT_TCP_TIMEOUT = 3.0
DEFAULT_DEEP_WORKERS = 6
DEFAULT_DEEP_TIMEOUT = 12.0
DEFAULT_DEEP_LIMIT = 500
DEFAULT_CUTOFF_MS = 1500

DEFAULT_MAX_PAGES = 120
DEFAULT_DEPTH = 2
DEFAULT_WEB_DELAY = 0.7
DEFAULT_WEB_TIMEOUT = 15.0
DEFAULT_SEARCH_RESULTS = 8

QUOTA_SHARE = 2000
QUOTA_HTTP = 1000
QUOTA_SOCKS = 800


# ---------------------------------------------------------------- утилиты

def _opener():
    return build_opener(ProxyHandler({}))


def api_json(path, payload=None, timeout=15):
    url = API_BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = Request(url, data=data, headers=headers,
                  method="POST" if data is not None else "GET")
    with _opener().open(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
    return json.loads(body)


def dedupe_key(s):
    return "%s://%s:%s" % (s.get("type"), s.get("host"), s.get("port"))


def country_from_name(name):
    name = str(name or "")
    for i in range(len(name) - 1):
        a, b = name[i], name[i + 1]
        if (0x1F1E6 <= ord(a) <= 0x1F1FF
                and 0x1F1E6 <= ord(b) <= 0x1F1FF and a != b):
            return chr(ord(a) - 0x1F1E6 + 65) + chr(ord(b) - 0x1F1E6 + 65)
    return None


def clean_host(raw):
    host = str(raw or "").strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if not host or len(host) > 253:
        return ""
    if any(c.isspace() for c in host):
        return ""
    try:
        ip = ipaddress.ip_address(host)
        return host if ip.is_global else ""
    except ValueError:
        pass
    if "." not in host:
        return ""
    low = host.lower()
    if low.endswith((".local", ".lan", ".internal", ".localdomain",
                     ".home", ".corp", ".localhost")):
        return ""
    if not re.match(r"^[A-Za-z0-9._-]+$", host):
        return ""
    return low


def empty_server():
    d = {k: "" for k in SERVER_FIELDS}
    d.update({
        "port": 0,
        "enabled": True,
        "source": "parser",
        "latency": None,
        "latency_ok": False,
        "tested": False,
        "added_ts": 0.0,
        "allow_insecure": False,
        "mtu": 0,
    })
    return d


def normalize_server(raw, source_name):
    if not isinstance(raw, dict):
        return None
    d = empty_server()
    for key in SERVER_FIELDS:
        if raw.get(key) is not None:
            d[key] = raw[key]

    typ = str(d.get("type") or "").strip().lower()
    if typ in ("socks5", "socks5h", "socks5-hostname", "socks4", "socks4a"):
        typ = "socks"
    if typ not in vp.VALID_TYPES:
        return None
    d["type"] = typ

    host = clean_host(d.get("host"))
    if not host:
        return None
    try:
        port = int(d.get("port") or 0)
    except (TypeError, ValueError):
        return None
    if port < 1 or port > 65535:
        return None

    name = str(d.get("name") or "").strip()
    name = name.replace("\r", " ").replace("\n", " ")
    if not name:
        name = "%s://%s:%d" % (typ, host, port)

    d["id"] = uuid.uuid4().hex[:10]
    d["name"] = name[:120]
    d["host"] = host
    d["port"] = port
    d["enabled"] = True
    d["source"] = "parser:" + source_name
    d["latency"] = None
    d["latency_ok"] = False
    d["tested"] = False
    d["country"] = country_from_name(name) or None
    d["added_ts"] = time.time()
    d["allow_insecure"] = bool(d.get("allow_insecure"))
    try:
        d["mtu"] = int(d.get("mtu") or 0)
    except (TypeError, ValueError):
        d["mtu"] = 0
    for key in ("uuid", "username", "password", "method", "flow", "security",
                "sni", "fp", "pbk", "sid", "transport", "path", "host_header",
                "service_name", "obfs", "obfs_password", "up", "down", "alpn",
                "congestion_control", "privkey", "peer_pubkey", "local_addrs"):
        if d.get(key) is None:
            d[key] = ""
    return d


def load_sources():
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    sources = data.get("sources") if isinstance(data, dict) else data
    if not isinstance(sources, list):
        raise ValueError("sources.json: ожидался список sources")
    result = []
    for src in sources:
        if not isinstance(src, dict) or not src.get("url"):
            continue
        if src.get("enabled") is False:
            continue
        kind = str(src.get("kind") or "share").lower()
        if kind not in ("http", "socks", "share", "web", "web-http", "web-socks"):
            kind = "share"
        result.append({
            "name": str(src.get("name") or src["url"])[:60],
            "url": src["url"],
            "kind": kind,
        })
    return result


# ---------------------------------------------------------------- сбор

def fetch_source(src, per_source):
    kind = src["kind"]
    force_type = kind if kind in ("http", "socks") else None
    stat = {
        "name": src["name"], "kind": kind, "url": src["url"],
        "status": "ok", "parsed": 0, "skipped": 0, "error": "",
        "size": 0, "servers": [],
    }
    is_web = kind in ("web", "web-http", "web-socks")
    try:
        if is_web:
            ok, text, _ctype, _final, err = webscan.fetch(src["url"], timeout=40)
            if not ok:
                text = err or "fetch error"
        else:
            ok, text = vp.fetch_url(src["url"], timeout=40)
    except Exception as exc:
        ok, text = False, str(exc)
    if not ok:
        stat["status"] = "error"
        stat["error"] = str(text)[:220]
        return stat
    stat["size"] = len(str(text).encode("utf-8", "ignore"))
    try:
        if is_web:
            default_type = "socks" if kind == "web-socks" else "http"
            servers = webscan.extract_servers(text, default_type=default_type,
                                              url=src["url"])
            errors = []
        else:
            servers, errors = vp.parse_subscription(text, force_type=force_type)
    except Exception as exc:
        stat["status"] = "error"
        stat["error"] = "parse: " + str(exc)[:200]
        return stat
    stat["skipped"] = len(errors)
    if len(servers) > per_source:
        servers = random.sample(servers, per_source)
    stat["parsed"] = len(servers)
    stat["servers"] = servers
    return stat


def _write_web_pages(pages):
    os.makedirs(RESULT_DIR, exist_ok=True)
    try:
        with open(WEB_PAGES_FILE, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("url\tstatus\tservers\tbytes\tdepth\terror\r\n")
            for p in pages:
                f.write("%s\t%s\t%s\t%s\t%s\t%s\r\n" % (
                    p.get("url", ""), p.get("status", ""), p.get("servers", 0),
                    p.get("bytes", 0), p.get("depth", 0),
                    str(p.get("error", "")).replace("\t", " ")[:160]))
    except Exception as exc:
        print("Не удалось записать web-pages.txt:", exc)


def collect_web(args):
    """Поиск в интернете + обход сайтов. Возвращает (raw, stats, pages, meta)."""
    queries = list(getattr(args, "search", None) or [])
    if getattr(args, "no_search", False):
        queries = []
    elif getattr(args, "internet", False):
        file_queries = webscan.load_lines(getattr(args, "queries", QUERIES_FILE))
        if not file_queries:
            file_queries = list(webscan.DEFAULT_QUERIES)
        for q in file_queries:
            if q not in queries:
                queries.append(q)

    seeds = webscan.load_lines(getattr(args, "seeds", SEEDS_FILE))
    if not queries and not seeds:
        return [], [], [], ["Интернет-режим: нет поисковых запросов и стартовых сайтов"]

    print("Интернет-режим: запросов %d, стартовых сайтов %d"
          % (len(queries), len(seeds)), flush=True)

    found = []
    seen_urls = set()
    search_errors = []
    empty_streak = 0
    for i, query in enumerate(queries):
        urls, err = webscan.search(
            query, limit=getattr(args, "search_results", DEFAULT_SEARCH_RESULTS),
            timeout=getattr(args, "web_timeout", DEFAULT_WEB_TIMEOUT))
        if urls:
            empty_streak = 0
            print("  [поиск] %-48s ссылок %d" % (query[:48], len(urls)), flush=True)
        else:
            empty_streak += 1
            print("  [поиск] %-48s %s"
                  % (query[:48], (err or "пусто")[:70]), flush=True)
            if err:
                search_errors.append("%s: %s" % (query[:40], err[:100]))
            if empty_streak >= 3 and i + 1 < len(queries):
                print("  [поиск] поисковики не отдают результаты — "
                      "дальше только обход seeds.txt", flush=True)
                break
        for u in urls:
            if u not in seen_urls:
                seen_urls.add(u)
                found.append(u)
        if i + 1 < len(queries):
            time.sleep(max(1.0, getattr(args, "delay", DEFAULT_WEB_DELAY)))

    for seed in seeds:
        if seed not in seen_urls:
            seen_urls.add(seed)
            found.append(seed)

    if not found:
        return [], [], [], ["Интернет-режим: ссылок не найдено. " + "; ".join(search_errors[:3])]

    print("Обход сайтов: до %d страниц, глубина %d..."
          % (getattr(args, "max_pages", DEFAULT_MAX_PAGES),
             getattr(args, "depth", DEFAULT_DEPTH)), flush=True)
    raw, pages = webscan.crawl(
        found,
        max_pages=getattr(args, "max_pages", DEFAULT_MAX_PAGES),
        max_depth=getattr(args, "depth", DEFAULT_DEPTH),
        delay=getattr(args, "delay", DEFAULT_WEB_DELAY),
        timeout=getattr(args, "web_timeout", DEFAULT_WEB_TIMEOUT),
        respect_robots=not getattr(args, "no_robots", False),
        log=print)
    _write_web_pages(pages)

    groups = {}
    for item in raw:
        name = item.get("_source") or "web"
        groups.setdefault(name, []).append(item)
    stats = []
    for name, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        stats.append({
            "name": name, "kind": "web", "url": "", "status": "ok",
            "parsed": len(items), "skipped": 0, "error": "", "size": 0,
            "servers": items,
        })

    meta = ["Интернет: страниц %d, серверов %d, сайтов с находками %d"
            % (len(pages), len(raw), len(groups))]
    if search_errors:
        meta.append("Ошибки поиска: " + "; ".join(search_errors[:5]))
    return raw, stats, pages, meta


def collect_sources(per_source, max_total):
    sources = load_sources()
    print("Источников: %d. Загрузка..." % len(sources), flush=True)
    stats = [None] * len(sources)
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_source, src, per_source): i
                   for i, src in enumerate(sources)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                stats[i] = fut.result()
            except Exception as exc:  # pragma: no cover
                stats[i] = {
                    "name": sources[i]["name"], "kind": sources[i]["kind"],
                    "url": sources[i]["url"], "status": "error",
                    "parsed": 0, "skipped": 0, "error": str(exc)[:200],
                    "size": 0, "servers": [],
                }
            st = stats[i]
            if st["status"] == "ok":
                print("  [ok] %-32s %5d" % (st["name"][:32], st["parsed"]),
                      flush=True)
            else:
                print("  [!!] %-32s %s" % (st["name"][:32], st["error"][:80]),
                      flush=True)

    seen = set()
    by_kind = {"share": [], "http": [], "socks": []}
    total_parsed = 0
    for st in stats:
        total_parsed += st["parsed"]
        for raw in st["servers"]:
            srv = normalize_server(raw, st["name"])
            if not srv:
                continue
            key = dedupe_key(srv)
            if key in seen:
                continue
            seen.add(key)
            if srv["type"] in SHARE_TYPES:
                by_kind["share"].append(srv)
            elif srv["type"] in HTTP_TYPES:
                by_kind["http"].append(srv)
            else:
                by_kind["socks"].append(srv)

    selected = (by_kind["share"][:QUOTA_SHARE]
                + by_kind["http"][:QUOTA_HTTP]
                + by_kind["socks"][:QUOTA_SOCKS])
    if len(selected) > max_total:
        selected = selected[:max_total]
    print("Разобрано: %d, уникальных: %d, отобрано: %d"
          % (total_parsed, len(seen), len(selected)), flush=True)
    return selected, stats, len(seen)


# ---------------------------------------------------------------- проверки

def tcp_probe(host, port, timeout):
    started = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return max(1, int((time.time() - started) * 1000))
    except OSError:
        return None


def tcp_filter(servers, workers, timeout):
    if not servers:
        return [], 0
    alive = []
    print("TCP-проверка %d серверов (потоков %d)..." % (len(servers), workers),
          flush=True)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {ex.submit(tcp_probe, s["host"], s["port"], timeout): s
                   for s in servers}
        done = 0
        for fut in as_completed(futures):
            srv = futures[fut]
            done += 1
            try:
                ms = fut.result()
            except Exception:
                ms = None
            if ms is not None:
                srv["latency"] = ms
                alive.append(srv)
            if done % 200 == 0:
                print("  проверено %d/%d, доступно %d"
                      % (done, len(servers), len(alive)), flush=True)
    alive.sort(key=lambda s: s.get("latency") or 10 ** 9)
    return alive, len(servers) - len(alive)


def find_app_dir(explicit=""):
    candidates = []
    if explicit:
        candidates.append(explicit)
    env_dir = os.environ.get("NIKKINET_DIR")
    if env_dir:
        candidates.append(env_dir)
    candidates.append(os.path.join(os.path.dirname(BASE_DIR), "prox"))
    candidates.append(r"C:\Program Files\NikkiNet")
    for cand in candidates:
        if cand and os.path.isfile(os.path.join(cand, "proxy_app.py")):
            return os.path.abspath(cand)
    return ""


def load_singbox(app_dir):
    if not app_dir:
        return None, ("Не найдена папка NikkiNet (proxy_app.py). "
                      "Укажите её через --app.")
    exe = os.path.join(app_dir, "tools", "sing-box.exe")
    if not os.path.isfile(exe):
        return None, "Не найден sing-box.exe: " + exe
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    try:
        import singbox  # noqa: F401
    except Exception as exc:
        return None, "Не удалось импортировать singbox.py: " + str(exc)
    return singbox, ""


def _deep_one(singbox_mod, srv, timeout):
    try:
        res = singbox_mod.test_outbound(srv, timeout=timeout)
        return res if isinstance(res, dict) else {"ok": False}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:160]}


def deep_filter(servers, app_dir, limit, workers, timeout, cutoff):
    singbox_mod, err = load_singbox(app_dir)
    if not singbox_mod:
        return None, 0, err
    candidates = list(servers)
    random.shuffle(candidates)
    if limit and limit > 0:
        candidates = candidates[:limit]
    print("Глубокая проверка через sing-box: %d серверов (потоков %d, случайная выборка)..."
          % (len(candidates), workers), flush=True)
    working = []
    tested = 0
    failed = 0
    errors = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {ex.submit(_deep_one, singbox_mod, s, timeout): s
                   for s in candidates}
        for fut in as_completed(futures):
            srv = futures[fut]
            tested += 1
            try:
                res = fut.result()
            except Exception as exc:
                res = {"ok": False, "error": str(exc)}
            ok = bool(res.get("ok"))
            ms = res.get("latency_ms")
            srv["tested"] = True
            if ok and ms is not None and int(ms) <= cutoff:
                srv["latency"] = int(ms)
                srv["latency_ok"] = True
                working.append(srv)
            else:
                srv["latency"] = None
                srv["latency_ok"] = False
                failed += 1
                if res.get("error") and len(errors) < 8:
                    errors.append(str(res["error"])[:160])
            if tested % 20 == 0:
                print("  проверено %d/%d, рабочих %d"
                      % (tested, len(candidates), len(working)), flush=True)
    working.sort(key=lambda s: s.get("latency") or 10 ** 9)
    return working, tested, "; ".join(errors)


# ---------------------------------------------------------------- результаты

def count_types(servers):
    counts = {}
    for srv in servers:
        counts[srv["type"]] = counts.get(srv["type"], 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def write_output(servers, mode, stats, extra):
    os.makedirs(RESULT_DIR, exist_ok=True)
    tmp = SERVERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(servers, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SERVERS_FILE)

    with open(PROXIES_FILE, "w", encoding="utf-8", newline="\r\n") as f:
        for srv in servers:
            f.write("%s://%s:%d\n" % (srv["type"], srv["host"], srv["port"]))

    lines = []
    lines.append("NikkiNet parser - отчет")
    lines.append("Время: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("Режим: " + mode)
    lines.append("")
    ok = sum(1 for st in stats if st.get("status") == "ok")
    lines.append("Источников: %d, успешно: %d, ошибок: %d"
                 % (len(stats), ok, len(stats) - ok))
    lines.append("")
    lines.append("Источники:")
    for st in stats:
        note = st.get("error") or ("пропущено строк: %d" % st.get("skipped", 0))
        lines.append("  %-34s %-6s %6d  %s"
                     % (st.get("name", "?")[:34], st.get("status", "?"),
                        st.get("parsed", 0), note[:100]))
    lines.append("")
    for line in extra:
        lines.append(line)
    lines.append("")
    lines.append("Итог: %d серверов" % len(servers))
    types = count_types(servers)
    if types:
        lines.append("По типам: " + ", ".join("%s=%d" % kv for kv in types.items()))
    lines.append("")
    lines.append("Файлы:")
    lines.append("  " + SERVERS_FILE)
    lines.append("  " + PROXIES_FILE)
    lines.append("")
    lines.append("ВНИМАНИЕ: бесплатные публичные узлы небезопасны. Владелец узла")
    lines.append("видит ваш трафик. Не используйте их для банков, почты, работы")
    lines.append("и любых важных аккаунтов. Узлы быстро умирают - запускайте")
    lines.append("парсер заново. Не публикуйте результат: чужие люди получат")
    lines.append("доступ к тем же узлам, и они станут ещё медленнее.")
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))

    print("\nСохранено: %s (%d серверов)" % (SERVERS_FILE, len(servers)))
    print("Список прокси: %s" % PROXIES_FILE)
    print("Отчет: %s" % REPORT_FILE)
    if types:
        print("По типам: " + ", ".join("%s=%d" % kv for kv in types.items()))


def load_results():
    if not os.path.isfile(SERVERS_FILE):
        print("Нет файла результата:", SERVERS_FILE)
        return []
    try:
        with open(SERVERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as exc:
        print("Не удалось прочитать результат:", exc)
        return []


# ---------------------------------------------------------------- импорт

def _lock_present(app_dir):
    if not app_dir:
        return False
    return os.path.isfile(os.path.join(app_dir, ".lock"))


def merge_into_app(servers, app_dir, force=False):
    if not servers:
        print("Нечего импортировать.")
        return 1

    api_up = False
    try:
        status = api_json("/api/update/status", timeout=4)
        api_up = isinstance(status, dict)
    except Exception:
        api_up = False

    if api_up:
        print("NikkiNet запущен - импорт через панель.")
        existing = set()
        try:
            state = api_json("/api/state", timeout=90)
            for srv in state.get("servers") or []:
                existing.add(dedupe_key(srv))
        except Exception as exc:
            print("  не удалось прочитать текущий список:", str(exc)[:120])
        todo = [srv for srv in servers if dedupe_key(srv) not in existing]
        print("  уже в NikkiNet: %d, к добавлению: %d"
              % (len(existing), len(todo)))
        added = 0
        failed = 0
        for i, srv in enumerate(todo, 1):
            try:
                res = api_json("/api/server/add", {"server": srv}, timeout=25)
                if res.get("ok") and res.get("added"):
                    added += 1
            except Exception as exc:
                failed += 1
                if failed <= 3:
                    print("  ошибка: %s" % str(exc)[:120])
            if i % 50 == 0 or i == len(todo):
                print("  %d/%d, добавлено %d" % (i, len(todo), added), flush=True)
        print("Импорт завершен: добавлено %d, ошибок %d" % (added, failed))
        return 0

    print("Панель NikkiNet не отвечает - импорт напрямую в config.json.")
    if not app_dir:
        print("Не найдена папка NikkiNet. Укажите её через --app.")
        return 2
    if _lock_present(app_dir) and not force:
        print("Похоже, NikkiNet запущен, но панель недоступна.")
        print("Закройте приложение и повторите, либо запустите с --force.")
        return 2

    cfg_path = os.path.join(app_dir, "config.json")
    if not os.path.isfile(cfg_path):
        print("Не найден config.json:", cfg_path)
        return 2
    try:
        with open(cfg_path, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except Exception as exc:
        print("Не удалось прочитать config.json:", exc)
        return 2
    current = cfg.get("servers")
    if not isinstance(current, list):
        current = []
        cfg["servers"] = current
    existing = {dedupe_key(srv) for srv in current}
    todo = [srv for srv in servers if dedupe_key(srv) not in existing]
    if not todo:
        print("Все серверы уже есть в NikkiNet.")
        return 0

    backup = cfg_path + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
    try:
        shutil.copy2(cfg_path, backup)
        current.extend(todo)
        tmp = cfg_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, cfg_path)
    except Exception as exc:
        print("Ошибка записи config.json:", exc)
        print("Если NikkiNet установлен в Program Files, запустите от админа.")
        return 2
    print("Добавлено %d серверов. Резервная копия: %s" % (len(todo), backup))
    return 0


# ---------------------------------------------------------------- сценарии

def run_collect(deep, args):
    app_dir = find_app_dir(args.app)
    want_web = bool(getattr(args, "internet", False) or getattr(args, "search", None))
    web_raw, web_stats, web_pages, web_meta = [], [], [], []
    if want_web:
        try:
            web_raw, web_stats, web_pages, web_meta = collect_web(args)
        except Exception as exc:
            print("Интернет-режим не удался:", exc)
            web_meta = ["Интернет-режим не удался: " + str(exc)[:160]]

    base, stats, unique = [], [], 0
    if not getattr(args, "no_sources", False):
        base, stats, unique = collect_sources(args.per_source, args.max_total)
    stats = list(stats) + list(web_stats)

    web_servers = []
    if web_raw:
        seen = set(dedupe_key(s) for s in base)
        for raw in web_raw:
            srv = normalize_server(raw, raw.get("_source") or "web")
            if not srv:
                continue
            key = dedupe_key(srv)
            if key in seen:
                continue
            seen.add(key)
            web_servers.append(srv)

    servers = base
    if web_servers:
        web_take = min(len(web_servers), max(1, args.max_total // 2))
        base_cap = max(0, args.max_total - web_take)
        base_part = base[:base_cap]
        room = max(0, args.max_total - len(base_part))
        servers = base_part + web_servers[:room]
        added_web = max(0, len(servers) - len(base_part))
        print("Из интернета добавлено: %d" % added_web, flush=True)
        web_meta.append("Из интернета добавлено: %d" % added_web)

    if not servers:
        print("Ничего не собрано. Проверьте интернет, sources.json и queries.txt.")
        return 1
    print("К проверке: %d серверов" % len(servers), flush=True)

    alive, dead = tcp_filter(servers, args.tcp_workers, args.timeout)
    extra = [
        "Разобрано уникальных: %d" % unique,
        "TCP-проверка: доступно %d, мертвых %d" % (len(alive), dead),
    ] + web_meta
    result = alive
    mode = "сбор + TCP"
    if want_web:
        mode = "сбор + интернет + TCP"

    if deep:
        if not alive:
            print("Нет TCP-доступных серверов для глубокой проверки.")
        else:
            working, tested, errors = deep_filter(
                alive, app_dir, args.deep_limit, args.deep_workers,
                args.deep_timeout, args.cutoff)
            if working is None:
                print("Глубокая проверка недоступна:", tested)
                return 2
            result = working
            mode = "сбор + интернет + sing-box" if want_web else "сбор + sing-box"
            extra.append("Глубокая проверка: проверено %d, рабочих %d"
                         % (tested, len(working)))
            if errors:
                extra.append("Ошибки: " + errors)

    write_output(result, mode, stats, extra)
    if not result:
        print("Рабочих серверов не найдено. Попробуйте запустить позже.")
        return 1

    if args.merge:
        return merge_into_app(result, app_dir, force=args.force)
    if not args.no_merge:
        try:
            answer = input("\nИмпортировать в NikkiNet? [y/N]: ").strip().lower()
        except EOFError:
            answer = ""
        if answer in ("y", "yes", "д", "да"):
            return merge_into_app(result, app_dir, force=args.force)
    return 0


def run_retest(args):
    servers = load_results()
    if not servers:
        return 1
    app_dir = find_app_dir(args.app)
    alive, dead = tcp_filter(servers, args.tcp_workers, args.timeout)
    extra = ["Перепроверка: TCP доступно %d, мертвых %d" % (len(alive), dead)]
    result = alive
    mode = "перепроверка TCP"
    if not args.fast:
        working, tested, errors = deep_filter(
            alive, app_dir, args.deep_limit, args.deep_workers,
            args.deep_timeout, args.cutoff)
        if working is None:
            print("Глубокая проверка недоступна:", tested)
            return 2
        result = working
        mode = "перепроверка sing-box"
        extra.append("Глубокая проверка: проверено %d, рабочих %d"
                     % (tested, len(working)))
        if errors:
            extra.append("Ошибки: " + errors)
    stats = [{"name": "result/servers.json", "kind": "file", "url": "",
              "status": "ok", "parsed": len(servers), "skipped": 0,
              "error": "", "size": 0}]
    write_output(result, mode, stats, extra)
    if args.merge:
        return merge_into_app(result, app_dir, force=args.force)
    return 0


def run_merge_only(args):
    servers = load_results()
    if not servers:
        return 1
    return merge_into_app(servers, find_app_dir(args.app), force=args.force)


def show_stats():
    servers = load_results()
    if not servers:
        return 1
    types = count_types(servers)
    tested = sum(1 for srv in servers if srv.get("tested"))
    ok = sum(1 for srv in servers if srv.get("latency_ok"))
    print("Файл:", SERVERS_FILE)
    print("Серверов:", len(servers))
    print("По типам: " + ", ".join("%s=%d" % kv for kv in types.items()))
    print("Проверено sing-box: %d, рабочих: %d" % (tested, ok))
    fastest = sorted(servers, key=lambda s: s.get("latency") or 10 ** 9)[:10]
    print("\nСамые быстрые:")
    for srv in fastest:
        print("  %5s мс  %-8s %s:%s  %s"
              % (srv.get("latency") or "-", srv["type"], srv["host"],
                 srv["port"], srv.get("name", "")[:40]))
    return 0


def interactive_menu(args):
    while True:
        print("""
============================================================
  NikkiNet - парсер бесплатных серверов
============================================================
  1) Собрать + быстрая TCP-проверка
  2) Собрать + точная проверка через sing-box (медленно)
  3) Перепроверить result\\servers.json через sing-box
  4) Импортировать result\\servers.json в NikkiNet
  5) Показать статистику результата
  6) Глубокий сбор по интернету (поиск + сайты + sing-box)
  0) Выход
""")
        try:
            choice = input("Выбор: ").strip().lower()
        except EOFError:
            return 0
        if choice in ("0", "q", "exit", "выход", ""):
            return 0
        print()
        if choice == "1":
            run_collect(False, args)
        elif choice == "2":
            run_collect(True, args)
        elif choice == "3":
            run_retest(args)
        elif choice == "4":
            run_merge_only(args)
        elif choice == "5":
            show_stats()
        elif choice == "6":
            args.internet = True
            run_collect(True, args)
        else:
            print("Неизвестный пункт.")
        try:
            input("\nНажмите Enter, чтобы продолжить...")
        except EOFError:
            return 0


def build_parser():
    p = argparse.ArgumentParser(
        description="Сбор и проверка бесплатных публичных серверов для NikkiNet")
    p.add_argument("--fast", action="store_true",
                   help="собрать и проверить TCP (по умолчанию)")
    p.add_argument("--deep", action="store_true",
                   help="собрать и проверить через sing-box")
    p.add_argument("--retest", action="store_true",
                   help="перепроверить result/servers.json")
    p.add_argument("--merge-only", action="store_true",
                   help="импортировать result/servers.json в NikkiNet")
    p.add_argument("--merge", action="store_true",
                   help="импортировать после сбора без вопроса")
    p.add_argument("--no-merge", action="store_true",
                   help="не спрашивать об импорте")
    p.add_argument("--stats", action="store_true",
                   help="показать статистику result/servers.json")
    p.add_argument("--app", default="",
                   help="папка NikkiNet (где лежит proxy_app.py)")
    p.add_argument("--per-source", type=int, default=DEFAULT_PER_SOURCE,
                   help="максимум серверов с одного источника")
    p.add_argument("--max-total", type=int, default=DEFAULT_MAX_TOTAL,
                   help="общий лимит собранных серверов")
    p.add_argument("--tcp-workers", type=int, default=DEFAULT_TCP_WORKERS)
    p.add_argument("--timeout", type=float, default=DEFAULT_TCP_TIMEOUT,
                   help="таймаут TCP-проверки, сек")
    p.add_argument("--deep-workers", type=int, default=DEFAULT_DEEP_WORKERS)
    p.add_argument("--deep-timeout", type=float, default=DEFAULT_DEEP_TIMEOUT)
    p.add_argument("--deep-limit", type=int, default=DEFAULT_DEEP_LIMIT,
                   help="сколько серверов проверять через sing-box (случайная выборка; 0 = все)")
    p.add_argument("--cutoff", type=int, default=DEFAULT_CUTOFF_MS,
                   help="максимальная задержка рабочего сервера, мс")
    p.add_argument("--internet", action="store_true",
                   help="искать серверы по всему интернету (поиск + обход сайтов)")
    p.add_argument("--search", action="append", default=[],
                   help="поисковый запрос (можно несколько раз)")
    p.add_argument("--queries", default=QUERIES_FILE,
                   help="файл с поисковыми запросами для --internet")
    p.add_argument("--seeds", default=SEEDS_FILE,
                   help="файл со стартовыми сайтами для обхода")
    p.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                   help="максимум страниц для обхода")
    p.add_argument("--depth", type=int, default=DEFAULT_DEPTH,
                   help="глубина обхода ссылок")
    p.add_argument("--delay", type=float, default=DEFAULT_WEB_DELAY,
                   help="пауза между запросами к одному сайту, сек")
    p.add_argument("--web-timeout", type=float, default=DEFAULT_WEB_TIMEOUT,
                   help="таймаут загрузки страницы, сек")
    p.add_argument("--search-results", type=int, default=DEFAULT_SEARCH_RESULTS,
                   help="сколько ссылок брать из результатов поиска")
    p.add_argument("--no-robots", action="store_true",
                   help="не соблюдать robots.txt (не рекомендуется)")
    p.add_argument("--no-sources", action="store_true",
                   help="не использовать sources.json, только интернет")
    p.add_argument("--no-search", action="store_true",
                   help="не обращаться к поисковикам, обходить только seeds.txt")
    p.add_argument("--force", action="store_true",
                   help="писать config.json даже при запущенном NikkiNet")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.merge:
        args.no_merge = False

    if args.stats:
        return show_stats()
    if args.merge_only:
        return run_merge_only(args)
    if args.retest:
        args.fast = not args.deep
        return run_retest(args)
    if (args.internet or args.search) and not args.fast:
        args.deep = True
    if args.fast or args.deep:
        return run_collect(args.deep, args)

    return interactive_menu(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")
        raise SystemExit(130)
