#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
webscan.py - поиск и обход открытых страниц интернета для NikkiNet parser.

Что умеет:
  * поиск через DuckDuckGo HTML (резервный вариант - Bing);
  * обход сайтов по ссылкам с ограничением глубины и числа страниц;
  * соблюдение robots.txt и задержек между запросами;
  * извлечение share-ссылок, ip:port, JSON-списков и base64-блоков;
  * разбор HTML/JS-экранирования.

Только стандартная библиотека Python 3.8+.
"""

import base64
import html
import ipaddress
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import deque
from html.parser import HTMLParser

try:
    sys_stdout = __import__("sys").stdout
    sys_stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import subs as vp

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 NikkiNetParser/2.0")

TEXT_TYPES = (
    "text/html", "text/plain", "text/xml", "text/x-json",
    "application/json", "application/ld+json", "application/xml",
    "application/x-ndjson", "application/octet-stream",
)

SKIP_EXT = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".map",
    ".zip", ".rar", ".7z", ".gz", ".bz2", ".xz", ".tar",
    ".exe", ".msi", ".apk", ".dmg", ".iso", ".bin", ".img",
    ".mp3", ".mp4", ".avi", ".mkv", ".mov", ".webm", ".ogg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
)

SKIP_HOSTS = (
    "google.", "googleusercontent.", "youtube.", "facebook.", "instagram.",
    "twitter.", "x.com", "vk.com", "ok.ru", "t.co", "doubleclick.",
    "googlesyndication.", "googleadservices.", "yandex.", "bing.com",
    "microsoft.com", "apple.com", "amazon.", "cloudflare.com",
    "gstatic.", "fonts.gstatic.", "cdn.jsdelivr.net", "unpkg.com",
)

SHARE_RE = re.compile(
    r"(?i)\b(?:vless|vmess|trojan|ss|hysteria2|tuic)://[^\s<>\"'`]+")
IPPORT_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}(?!\d)")
IPPORT2_RE = re.compile(
    r"(?<![\d.])((?:\d{1,3}\.){3}\d{1,3})[\s,;|]+(\d{1,5})(?!\d)")
B64_RE = re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)

DEFAULT_QUERIES = [
    "free vless subscription link",
    "free vmess subscription link",
    "free trojan proxy config",
    "free shadowsocks server list",
    "free hysteria2 config",
    "free socks5 proxy list",
    "free http proxy list",
    "site:pastebin.com vless://",
    "site:t.me vless://",
    "site:t.me vmess://",
    "free v2ray configs daily",
    "free proxy list txt",
]

SEARCH_SKIP_HOSTS = SKIP_HOSTS + (
    "duckduckgo.com", "html.duckduckgo.com",
    "github.com", "raw.githubusercontent.com",
)

_robots_cache = {}


# ------------------------------------------------------------------ сеть

def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch(url, timeout=15.0, max_bytes=2000000):
    """Возвращает (ok, text, content_type, final_url, error)."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/json,text/plain,*/*;q=0.8",
        "Accept-Encoding": "identity",
        "Accept-Language": "en-US,en;q=0.8,ru;q=0.6",
    })
    try:
        with _opener().open(req, timeout=timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ctype and not ctype.startswith(TEXT_TYPES):
                return False, "", ctype, url, "content-type " + ctype
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raw = raw[:max_bytes]
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                text = raw.decode(charset, "replace")
            except (LookupError, UnicodeDecodeError):
                text = raw.decode("utf-8", "replace")
            return True, text, ctype, resp.geturl(), ""
    except urllib.error.HTTPError as exc:
        return False, "", "", url, "HTTP %s" % exc.code
    except Exception as exc:
        return False, "", "", url, str(exc)[:160]


def _robots_for(url, timeout=8.0):
    parts = urllib.parse.urlsplit(url)
    root = "%s://%s" % (parts.scheme, parts.netloc)
    if root in _robots_cache:
        return _robots_cache[root]
    ok, text, _, _, _ = fetch(root + "/robots.txt", timeout=timeout,
                              max_bytes=200000)
    parser = None
    if ok and text:
        try:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(text.splitlines())
        except Exception:
            parser = None
    _robots_cache[root] = parser
    return parser


def robots_allowed(url, timeout=8.0):
    """Возвращает (allowed, crawl_delay)."""
    parser = _robots_for(url, timeout=timeout)
    if parser is None:
        return True, 0.0
    try:
        allowed = parser.can_fetch(UA, url)
        delay = parser.crawl_delay(UA) or parser.crawl_delay("*") or 0
        return allowed, float(delay)
    except Exception:
        return True, 0.0


# ------------------------------------------------------------------ разбор

class _AnchorParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.hrefs = []
        self.base = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.hrefs.append(attrs["href"])
        elif tag == "base" and attrs.get("href"):
            self.base = attrs["href"]


class _ResultParser(HTMLParser):
    """Собирает ссылки и текст только из блоков результатов DDG и Bing."""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.items = []
        self._algo = 0
        self._h2 = 0
        self._anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        cls = (attrs.get("class") or "").lower()
        if tag == "li":
            if self._algo:
                self._algo += 1
            elif "b_algo" in cls:
                self._algo = 1
        elif tag == "h2":
            self._h2 += 1
        elif tag == "a" and attrs.get("href"):
            if ("result__a" in cls or "result-link" in cls or self._h2):
                self._anchor = [attrs["href"], []]

    def handle_data(self, data):
        if self._anchor:
            self._anchor[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor:
            self.items.append((self._anchor[0], " ".join(self._anchor[1])))
            self._anchor = None
        elif tag == "li" and self._algo:
            self._algo -= 1
            if not self._algo:
                self._h2 = 0
        elif tag == "h2" and self._h2:
            self._h2 -= 1


def extract_links(text, base_url):
    parser = _AnchorParser()
    try:
        parser.feed(text)
    except Exception:
        pass
    if parser.base:
        base_url = urllib.parse.urljoin(base_url, parser.base)
    out = []
    seen = set()
    for href in parser.hrefs:
        href = html.unescape(href).strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        link = urllib.parse.urljoin(base_url, href)
        link = urllib.parse.urldefrag(link)[0]
        parts = urllib.parse.urlsplit(link)
        if parts.scheme not in ("http", "https"):
            continue
        if _skip_link(link):
            continue
        if link not in seen:
            seen.add(link)
            out.append(link)
    return out


def _host_blocked(host, patterns):
    """Сравнение хоста с шаблонами: www. игнорируется, точка на конце = префикс."""
    h = (host or "").lower().strip(".")
    if h.startswith("www."):
        h = h[4:]
    for bad in patterns:
        b = bad.lower().strip()
        if not b:
            continue
        if b.endswith("."):
            if h.startswith(b):
                return True
        elif h == b or h.endswith("." + b):
            return True
    return False


def _skip_link(link):
    low = link.lower()
    path = urllib.parse.urlsplit(low).path
    if path.endswith(SKIP_EXT):
        return True
    host = (urllib.parse.urlsplit(low).hostname or "").lower()
    return _host_blocked(host, SKIP_HOSTS)


def site_key(host):
    host = str(host or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    two = ".".join(parts[-2:])
    if two in ("co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au",
               "co.jp", "co.kr", "com.br", "com.cn", "com.tr", "com.ru",
               "net.ru", "org.ru", "com.ua", "co.nz", "co.za", "com.mx",
               "com.ar", "com.sg", "com.hk", "com.tw", "com.pl"):
        return ".".join(parts[-3:])
    return two


def _clean_token(token):
    token = html.unescape(token).strip()
    token = token.rstrip(").,;:'\"`]}>")
    return token


def _normalize_text(text):
    text = html.unescape(html.unescape(text))
    text = text.replace("\\/", "/")
    text = text.replace("\\u002F", "/").replace("\\u002f", "/")
    text = text.replace("\\u003A", ":").replace("\\u003a", ":")
    text = text.replace("\\u0026", "&")
    return text


def extract_share_links(text):
    text = _normalize_text(text)
    out = []
    seen = set()
    for match in SHARE_RE.finditer(text):
        token = _clean_token(match.group(0))
        if token and token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _valid_public_ip(host):
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return False


def _valid_port(port):
    try:
        return 1 <= int(port) <= 65535
    except (TypeError, ValueError):
        return False


def extract_hostports(text):
    out = []
    seen = set()
    for match in IPPORT_RE.finditer(text):
        host, port = match.group(0).rsplit(":", 1)
        if not _valid_public_ip(host) or not _valid_port(port):
            continue
        key = "%s:%s" % (host, int(port))
        if key not in seen:
            seen.add(key)
            out.append((host, int(port)))
    for match in IPPORT2_RE.finditer(text):
        host, port = match.group(1), match.group(2)
        if not _valid_public_ip(host) or not _valid_port(port):
            continue
        key = "%s:%s" % (host, int(port))
        if key not in seen:
            seen.add(key)
            out.append((host, int(port)))
    return out


def _get_ci(obj, names):
    for key, value in obj.items():
        if str(key).lower() in names and isinstance(value, (str, int, float)):
            return str(value)
    return ""


def _iter_json_dicts(obj):
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            for value in cur.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(cur, list):
            for value in cur:
                if isinstance(value, (dict, list)):
                    stack.append(value)


def extract_json_servers(text):
    try:
        data = json.loads(text)
    except Exception:
        return []
    out = []
    for obj in _iter_json_dicts(data):
        host = _get_ci(obj, ("ip", "host", "hostname", "server", "address", "addr"))
        port = _get_ci(obj, ("port", "port_int", "server_port"))
        if not host or not port or not _valid_public_ip(host) or not _valid_port(port):
            continue
        typ = _get_ci(obj, ("protocol", "type", "proto", "scheme")).lower()
        if typ in ("socks5", "socks5h", "socks4", "socks4a"):
            typ = "socks"
        if typ not in vp.VALID_TYPES:
            typ = "http"
        out.append({"type": typ, "host": host, "port": int(port),
                    "name": "%s:%s" % (host, int(port))})
    return out


def _decode_blobs(text):
    """Декодирует длинные base64-блоки, в которых могут быть конфиги."""
    decoded = []
    seen = set()
    for match in B64_RE.finditer(text):
        blob = match.group(0)
        if blob in seen:
            continue
        seen.add(blob)
        if len(seen) > 15:
            break
        padded = blob + "=" * (-len(blob) % 4)
        try:
            raw = base64.b64decode(padded, validate=False)
        except Exception:
            continue
        if not raw or len(raw) > 500000:
            continue
        try:
            chunk = raw.decode("utf-8", "ignore")
        except Exception:
            continue
        if "://" in chunk or IPPORT_RE.search(chunk) or IPPORT2_RE.search(chunk):
            decoded.append(chunk)
    return decoded


def _strip_tags(text):
    """Грубое превращение HTML в текст: нужно для таблиц <td>ip</td><td>port</td>."""
    text = re.sub(r"<(script|style)\b[^>]*>", " ", text, flags=re.I)
    text = re.sub(r"</(script|style)>", " ", text, flags=re.I)
    text = TAG_RE.sub(" ", text)
    return _normalize_text(text)


def extract_servers(text, default_type="http", url=""):
    """Достаёт серверы из произвольной страницы (HTML/текст/JSON)."""
    if not text:
        return []
    text = _normalize_text(text)
    text = urllib.parse.unquote(text) if "%3A%2F%2F" in text.upper() else text
    plain = _strip_tags(text)

    raw = []
    seen = set()

    def add(item):
        if not item:
            return
        key = "%s://%s:%s" % (item.get("type"), item.get("host"), item.get("port"))
        if key not in seen:
            seen.add(key)
            raw.append(item)

    for token in extract_share_links(text):
        try:
            server = vp.uri_to_server(token)
        except Exception:
            continue
        if server:
            add(server)

    for host, port in extract_hostports(text):
        add({"type": default_type, "host": host, "port": port,
             "name": "%s:%s" % (host, port)})

    # таблицы вида <td>1.2.3.4</td><td>8080</td> ломают regex на сыром HTML
    for host, port in extract_hostports(plain):
        add({"type": default_type, "host": host, "port": port,
             "name": "%s:%s" % (host, port)})

    for item in extract_json_servers(text):
        add(item)

    for chunk in _decode_blobs(text):
        for token in extract_share_links(chunk):
            try:
                server = vp.uri_to_server(token)
            except Exception:
                continue
            if server:
                add(server)
        for host, port in extract_hostports(chunk):
            add({"type": default_type, "host": host, "port": port,
                 "name": "%s:%s" % (host, port)})

    for item in raw:
        item.setdefault("name", "%s://%s:%s" % (
            item.get("type"), item.get("host"), item.get("port")))
    return raw


def guess_default_type(url, text):
    low = (url + " " + text[:4000]).lower()
    if "socks5" in low or "socks4" in low or "/socks" in low:
        return "socks"
    return "http"


# ------------------------------------------------------------------ поиск

def _unwrap_redirect(link):
    parts = urllib.parse.urlsplit(link)
    host = (parts.hostname or "").lower()
    query = urllib.parse.parse_qs(parts.query)
    if "uddg" in query and query["uddg"]:
        return query["uddg"][0]
    if "duckduckgo.com" in host and parts.path.startswith("/l/"):
        if query.get("uddg"):
            return query["uddg"][0]
    if "bing.com" in host and "u" in query:
        value = query["u"][0]
        if value.startswith("a1"):
            try:
                pad = value[2:]
                pad += "=" * (-len(pad) % 4)
                return base64.urlsafe_b64decode(pad).decode("utf-8", "ignore")
            except Exception:
                return link
    if "google." in host and "url" in query:
        return query["url"][0]
    return link


def _query_tokens(query):
    tokens = re.findall(r"[a-z0-9]{4,}", (query or "").lower())
    stop = {"free", "list", "link", "best", "daily", "public", "site",
            "https", "http", "www", "config", "configs"}
    useful = [t for t in tokens if t not in stop]
    return useful or tokens


def _search_links(text, base_url, tokens=None):
    """Извлекает только релевантные ссылки из блоков результатов поиска."""
    parser = _ResultParser()
    try:
        parser.feed(text)
    except Exception:
        pass
    out = []
    seen = set()
    for href, title in parser.items:
        href = html.unescape(href).strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        link = _unwrap_redirect(urllib.parse.urljoin(base_url, href))
        parts = urllib.parse.urlsplit(link)
        if parts.scheme not in ("http", "https"):
            continue
        if _host_blocked((parts.hostname or "").lower(), SEARCH_SKIP_HOSTS):
            continue
        if tokens:
            haystack = (link + " " + title).lower()
            if not any(t in haystack for t in tokens):
                continue
        if link in seen:
            continue
        seen.add(link)
        out.append(link)
    return out


def search(query, limit=12, timeout=15.0):
    """Возвращает (urls, error). Пробует DuckDuckGo, затем Bing."""
    encoded = urllib.parse.quote_plus(query)
    tokens = _query_tokens(query)
    engines = (
        ("ddg", "https://html.duckduckgo.com/html/?q=%s&kl=wt-wt" % encoded),
        ("ddg-lite", "https://lite.duckduckgo.com/lite/?q=%s" % encoded),
        ("bing", "https://www.bing.com/search?q=%s&count=30&setlang=en" % encoded),
        ("mojeek", "https://www.mojeek.com/search?q=%s" % encoded),
    )
    last_error = ""
    for name, url in engines:
        ok, text, _, final_url, error = fetch(url, timeout=timeout)
        if not ok:
            last_error = "%s: %s" % (name, error)
            continue
        found = _search_links(text, final_url, tokens)[:limit]
        if found:
            return found, ""
        last_error = name + ": пустая выдача"
    return [], last_error


def search_many(queries, limit=6, timeout=10.0, log=None):
    """Ищет несколько запросов параллельно, возвращает (urls, errors)."""
    from concurrent.futures import ThreadPoolExecutor

    queries = [q for q in queries if str(q or "").strip()][:8]
    if not queries:
        return [], ""

    def one(query):
        found, error = search(query, limit=limit, timeout=timeout)
        return query, found, error

    urls = []
    seen = set()
    errors = []
    try:
        with ThreadPoolExecutor(max_workers=min(3, len(queries))) as ex:
            results = list(ex.map(one, queries))
    except Exception as exc:
        return [], str(exc)[:160]
    for query, found, error in results:
        if log:
            log("поиск «%s»: ссылок %d%s" % (
                query[:48], len(found), (" · " + error[:80]) if error else ""))
        if error:
            errors.append("%s: %s" % (query[:32], error))
        for url in found:
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls, "; ".join(errors[:3])


# ------------------------------------------------------------------ обход

def crawl(seeds, max_pages=120, max_depth=2, delay=0.7, timeout=15.0,
          respect_robots=True, max_per_site=20, log=None):
    """Обходит сайты и возвращает (raw_servers, pages)."""
    seeds = [s for s in seeds if s]
    seed_keys = set()
    for seed in seeds:
        host = urllib.parse.urlsplit(seed).hostname or ""
        if host:
            seed_keys.add(site_key(host))

    queue = deque((seed, 0) for seed in seeds)
    visited = set()
    fetched = 0
    per_site = {}
    per_host_last = {}
    pages = []
    raw = []
    stop = False

    def note(message):
        if log:
            log(message)

    while queue and not stop:
        url, depth = queue.popleft()
        url = urllib.parse.urldefrag(url)[0]
        if url in visited or depth > max_depth:
            continue
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https"):
            continue
        host = (parts.hostname or "").lower()
        if not host:
            continue
        key = site_key(host)
        if seed_keys and key not in seed_keys:
            continue
        if per_site.get(key, 0) >= max_per_site:
            continue
        if fetched >= max_pages:
            break
        visited.add(url)

        crawl_delay = 0.0
        if respect_robots:
            allowed, crawl_delay = robots_allowed(url, timeout=min(timeout, 8.0))
            if not allowed:
                pages.append({"url": url, "status": "robots", "bytes": 0,
                              "servers": 0, "depth": depth, "error": ""})
                continue

        fetched += 1
        wait = max(delay, crawl_delay)
        last = per_host_last.get(host, 0.0)
        if last:
            remaining = wait - (time.time() - last)
            if remaining > 0:
                time.sleep(remaining)
        ok, text, ctype, final_url, error = fetch(url, timeout=timeout)
        per_host_last[host] = time.time()
        per_site[key] = per_site.get(key, 0) + 1

        if not ok:
            pages.append({"url": url, "status": "error", "bytes": 0,
                          "servers": 0, "depth": depth, "error": error})
            note("  [..] %-60s %s" % (url[:60], error[:60]))
            continue

        default_type = guess_default_type(final_url, text)
        found = extract_servers(text, default_type=default_type, url=final_url)
        for item in found:
            item["_source"] = "web:" + key
        raw.extend(found)
        pages.append({"url": url, "status": "ok", "bytes": len(text),
                      "servers": len(found), "depth": depth, "error": ""})
        if found:
            note("  [ok] %-60s +%d" % (url[:60], len(found)))
        elif len(pages) % 10 == 0:
            note("  [..] %-60s 0" % url[:60])

        if depth < max_depth:
            for link in extract_links(text, final_url):
                link_host = (urllib.parse.urlsplit(link).hostname or "").lower()
                if not link_host:
                    continue
                if seed_keys and site_key(link_host) not in seed_keys:
                    continue
                if link not in visited:
                    queue.append((link, depth + 1))

    return raw, pages


def load_lines(path):
    items = []
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#"):
                    items.append(line)
    except OSError:
        return []
    return items
