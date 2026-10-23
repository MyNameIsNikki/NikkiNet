import base64
import binascii
import json
import re
import urllib.parse
import urllib.request

PROXY_BYPASS_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

VALID_TYPES = {"http", "https", "socks", "vless", "vmess", "trojan", "ss", "hysteria2", "tuic"}


def fetch_url(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "proxy-app-sub"})
        with PROXY_BYPASS_OPENER.open(req, timeout=timeout) as resp:
            data = resp.read()
        for enc in ("utf-8", "latin-1", "cp1251"):
            try:
                return True, data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return True, data.decode("utf-8", "ignore")
    except Exception as exc:
        return False, str(exc)


def _b64_decode(s):
    s = re.sub(r"\s+", "", s)
    if not s:
        return None
    for variant in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            raw = variant(s + "=" * (-len(s) % 4))
            return raw.decode("utf-8", "ignore")
        except (binascii.Error, ValueError):
            continue
    return None


def _looks_b64(s):
    if not re.fullmatch(r"[A-Za-z0-9+/=_-]+", s):
        return False
    return len(s) >= 8


def _host_port(text):
    text = text.strip().rstrip("/")
    if text.startswith("["):
        host, rest = text.split("]", 1)
        port = re.search(r":(\d+)", rest)
        return host[1:], int(port.group(1)) if port else None
    if ":" in text:
        host, _, pr = text.rpartition(":")
        if pr.isdigit():
            return host, int(pr)
    return text, None


def _base_server(_type, host, port, name=""):
    return {
        "name": name or f"{_type}:{host}:{port}",
        "type": _type,
        "host": host,
        "port": port,
        "uuid": "",
        "username": "",
        "password": "",
        "method": "",
        "flow": "",
        "security": "",
        "sni": "",
        "fp": "",
        "pbk": "",
        "sid": "",
        "transport": "",
        "path": "",
        "host_header": "",
        "service_name": "",
    }


def uri_to_server(token, force_type=None):
    token = token.strip()
    if not token:
        return None
    frag = ""
    if "#" in token:
        token, frag = token.rsplit("#", 1)

    if "://" in token:
        scheme, rest = token.split("://", 1)
        scheme = scheme.lower()
    else:
        scheme = None

    def query_dict(qs):
        return urllib.parse.parse_qs(qs, keep_blank_values=True)

    def get1(q, key, default=""):
        return q.get(key, [default])[0] if q.get(key) else default

    if scheme in ("http", "https"):
        user = ""
        pw = ""
        rest2 = rest
        if "@" in rest2:
            user, rest2 = rest2.rsplit("@", 1)
            if ":" in user:
                user, pw = user.split(":", 1)
        host, port = _host_port(rest2)
        if port is None:
            port = 443 if scheme == "https" else 80
        s = _base_server(scheme, host, port, urllib.parse.unquote(frag))
        s["username"] = user
        s["password"] = pw
        return s

    if scheme in ("socks", "socks5", "socks4", "socks4a"):
        rest2 = rest
        user = pw = ""
        if "@" in rest2:
            auth, rest2 = rest2.rsplit("@", 1)
            if ":" in auth:
                user, pw = auth.split(":", 1)
        host, port = _host_port(rest2)
        if port is None:
            port = 1080
        s = _base_server("socks", host, port, urllib.parse.unquote(frag))
        s["username"] = user
        s["password"] = pw
        return s

    if scheme == "vless":
        return _parse_vless_uri(token, frag)

    if scheme == "trojan":
        if "@" not in rest:
            return None
        pw, addr = rest.rsplit("@", 1)
        q, addr_head = _extract_query(addr)
        host, port = _host_port(addr_head)
        s = _base_server("trojan", host, port, urllib.parse.unquote(frag))
        s["password"] = pw
        if port is None:
            return None
        s["security"] = get1(q, "security", "tls")
        s["sni"] = get1(q, "sni") or get1(q, "peer")
        s["fp"] = get1(q, "fp")
        s["transport"] = get1(q, "type", "tcp")
        s["path"] = get1(q, "path")
        s["host_header"] = get1(q, "host")
        s["service_name"] = get1(q, "serviceName")
        return s

    if scheme == "ss":
        payload, rest2 = rest.split("@", 1) if "@" in rest else (rest, "")
        # SIP002: адрес может нести query (?plugin=...&...) — отрезаем, host:port парсим чисто
        if "?" in rest2:
            rest2, _qpart = rest2.split("?", 1)
        host, port = _host_port(rest2) if rest2 else (None, None)
        try:
            if port is None:
                # old format: base64(method:password@host:port)
                dec = _b64_decode(payload)
                if dec and "@" in dec:
                    cred, addr = dec.rsplit("@", 1)
                    method, password = cred.split(":", 1)
                    h, p = _host_port(addr)
                    s = _base_server("ss", h, p, urllib.parse.unquote(frag))
                    s["method"] = method
                    s["password"] = password
                    return s
                return None
            dec = _b64_decode(payload)
            if not dec or ":" not in dec:
                return None
            method, password = dec.split(":", 1)
            s = _base_server("ss", host, port, urllib.parse.unquote(frag))
            s["method"] = method
            s["password"] = password
            return s
        except (ValueError, TypeError):
            return None

    if scheme == "vmess":
        return _parse_vmess(token)

    if scheme == "hysteria2":
        body = rest
        auth = ""
        if "@" in body:
            auth, body = body.rsplit("@", 1)
        q, addr_head = _extract_query(body)
        host, port = _host_port(addr_head)
        if port is None:
            return None
        s = _base_server("hysteria2", host, port, urllib.parse.unquote(frag))
        s["password"] = auth
        s["sni"] = get1(q, "sni") or host
        s["obfs"] = get1(q, "obfs")
        s["obfs_password"] = get1(q, "obfspassword") or get1(q, "obfs-password")
        s["up"] = get1(q, "up")
        s["down"] = get1(q, "down")
        s["alpn"] = get1(q, "alpn")
        s["allow_insecure"] = get1(q, "insecure", "0") in ("1", "true", "true", "yes")
        return s

    if scheme == "tuic":
        body = rest
        uuid_, pw = "", ""
        if "@" in body:
            cred, body = body.rsplit("@", 1)
            if ":" in cred:
                uuid_, pw = cred.split(":", 1)
        q, addr_head = _extract_query(body)
        host, port = _host_port(addr_head)
        if port is None:
            return None
        s = _base_server("tuic", host, port, urllib.parse.unquote(frag))
        s["uuid"] = uuid_
        s["password"] = pw
        s["sni"] = get1(q, "sni") or host
        s["alpn"] = get1(q, "alpn")
        s["congestion_control"] = get1(q, "congestion_control", "bbr")
        s["allow_insecure"] = get1(q, "insecure", "0") in ("1", "true", "true", "yes")
        return s

    # bare host:port
    host, port = _host_port(token)
    if port is not None:
        btype = force_type if force_type in VALID_TYPES else "http"
        return _base_server(btype, host, port, frag or f"{host}:{port}")
    return None


def _extract_query(s):
    if "?" not in s:
        return {}, s
    head, q = s.split("?", 1)
    return urllib.parse.parse_qs(q, keep_blank_values=True), head


def _parse_vless_uri(token, frag=""):
    body = token.split("://", 1)[1]
    if "@" not in body:
        return None
    uuid, rest = body.rsplit("@", 1)
    q, addr_head = _extract_query(rest)
    host, port = _host_port(addr_head)
    if port is None:
        return None

    def g(key, default=""):
        return q.get(key, [default])[0] if q.get(key) else default

    s = _base_server("vless", host, port, urllib.parse.unquote(frag))
    s["uuid"] = uuid
    s["security"] = g("security", "none")
    s["sni"] = g("sni") or g("peer") or g("host")
    s["flow"] = g("flow")
    s["fp"] = g("fp")
    s["pbk"] = g("pbk")
    s["sid"] = g("sid")
    s["transport"] = g("type", "tcp")
    s["path"] = g("path")
    s["host_header"] = g("host")
    s["service_name"] = g("serviceName")
    return s


def _parse_vmess(token):
    body = token.split("://", 1)[1] if "://" in token else token
    dec = _b64_decode(body)
    if dec:
        try:
            data = json.loads(dec)
        except Exception:
            data = None
    else:
        data = None
    if data:
        port = int(data.get("port") or 0)
        host = data.get("add") or data.get("server") or ""
        if not host or not port:
            return None
        s = _base_server("vmess", host, port, data.get("ps") or f"vmess:{host}:{port}")
        s["uuid"] = data.get("id", "")
        s["method"] = data.get("scy", "auto")
        s["security"] = "tls" if str(data.get("tls", "")).lower() in ("tls", "true", "1") else ""
        s["sni"] = data.get("sni", "")
        s["fp"] = data.get("fp", "")
        s["transport"] = data.get("net", "tcp")
        s["path"] = data.get("path", "")
        s["host_header"] = data.get("host", "")
        s["service_name"] = data.get("serviceName", "")
        return s
    # new-style vmess like vless
    return _parse_vless_uri(token.replace("vmess://", "vless://", 1))


def parse_subscription(text, force_type=None):
    text = text.strip()
    raw = text
    decoded_raw = None
    if "://" not in text and _looks_b64(text):
        decoded_raw = _b64_decode(text)
        if decoded_raw:
            hostport = re.search(r"^\s*[\w.\-\[]+:\d+", decoded_raw, re.M)
            if "://" in decoded_raw or "\n" in decoded_raw or hostport:
                raw = decoded_raw
    lines = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if ln:
            lines.append(ln)
    if not lines and decoded_raw:
        lines = [l.strip() for l in decoded_raw.splitlines() if l.strip()]
    servers = []
    errors = []
    for ln in lines:
        if ln.startswith("{") or ln.startswith("<") or ln.startswith("%YAML") or "clash_config" in ln.lower():
            continue
        if "," in ln and not re.match(r"^[\d\.]+$", ln) and len(ln) > 40 and "://" not in ln and ":" in ln and ln.count("*") == 0:
            continue
        s = uri_to_server(ln, force_type)
        if s:
            servers.append(s)
        elif ln:
            errors.append(ln[:80])
    return servers, errors