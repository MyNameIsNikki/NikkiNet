# -*- coding: utf-8 -*-
"""Экспорт серверов NikkiNet для Android (v2rayNG / SFA).

Читает config.json и создаёт в папке android/:
  subscriptions.txt — URL подписок (импортируются одним нажатием и обновляются сами)
  links.txt         — share-ссылки vless/vmess/trojan/ss/hysteria2 (по одной в строке)

Публичные HTTP/SOCKS-прокси в links.txt не попадают — они приходят через
подписки, а формат их share-ссылок у разных клиентов отличается.

Запуск:  python export_android.py
"""
import base64
import json
import os
import urllib.parse

import subs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "android")
EXPORT_TYPES = {"vless", "vmess", "trojan", "ss", "hysteria2"}


def b64(text):
    return base64.b64encode(text.encode("utf-8")).decode().rstrip("=")


def quote(value):
    return urllib.parse.quote(str(value), safe="")


def fragment(name):
    return "#" + urllib.parse.quote(name or "", safe="")


def query(pairs):
    parts = []
    for key, value in pairs:
        if value in (None, "", 0):
            continue
        parts.append("%s=%s" % (key, quote(value)))
    return ("?" + "&".join(parts)) if parts else ""


def alpn_value(server):
    alpn = server.get("alpn")
    if isinstance(alpn, (list, tuple)):
        return ",".join(str(x) for x in alpn)
    return alpn or ""


def vless_uri(s):
    params = query([
        ("type", s.get("transport") or "tcp"),
        ("security", s.get("security") or "none"),
        ("sni", s.get("sni")),
        ("fp", s.get("fp")),
        ("alpn", alpn_value(s)),
        ("flow", s.get("flow")),
        ("pbk", s.get("pbk")),
        ("sid", s.get("sid")),
        ("path", s.get("path")),
        ("host", s.get("host_header")),
        ("serviceName", s.get("service_name")),
    ])
    return "vless://%s@%s:%s%s%s" % (
        quote(s.get("uuid", "")), s["host"], s["port"], params, fragment(s.get("name")))


def vmess_uri(s):
    data = {
        "v": "2",
        "ps": s.get("name") or ("%s:%s" % (s["host"], s["port"])),
        "add": s["host"],
        "port": str(s["port"]),
        "id": s.get("uuid", ""),
        "aid": "0",
        "scy": s.get("method") or "auto",
        "net": s.get("transport") or "tcp",
        "type": "none",
        "host": s.get("host_header") or "",
        "path": s.get("path") or "",
        "tls": s.get("security") or "",
        "sni": s.get("sni") or "",
        "alpn": alpn_value(s),
        "fp": s.get("fp") or "",
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return "vmess://" + base64.b64encode(payload.encode("utf-8")).decode()


def ss_uri(s):
    userinfo = b64("%s:%s" % (s.get("method", ""), s.get("password", "")))
    return "ss://%s@%s:%s%s" % (userinfo, s["host"], s["port"], fragment(s.get("name")))


def trojan_uri(s):
    params = query([
        ("security", s.get("security") or "tls"),
        ("sni", s.get("sni")),
        ("fp", s.get("fp")),
        ("alpn", alpn_value(s)),
        ("type", s.get("transport") or "tcp"),
        ("path", s.get("path")),
        ("host", s.get("host_header")),
        ("serviceName", s.get("service_name")),
    ])
    return "trojan://%s@%s:%s%s%s" % (
        quote(s.get("password", "")), s["host"], s["port"], params, fragment(s.get("name")))


def hysteria2_uri(s):
    params = query([
        ("sni", s.get("sni") or s["host"]),
        ("insecure", "1" if s.get("allow_insecure") else ""),
        ("obfs", s.get("obfs")),
        ("obfs-password", s.get("obfs_password")),
        ("up", s.get("up")),
        ("down", s.get("down")),
    ])
    return "hysteria2://%s@%s:%s%s%s" % (
        quote(s.get("password", "")), s["host"], s["port"], params, fragment(s.get("name")))


BUILDERS = {
    "vless": vless_uri,
    "vmess": vmess_uri,
    "ss": ss_uri,
    "trojan": trojan_uri,
    "hysteria2": hysteria2_uri,
}


def validate(uri, server):
    """Проверяем, что ссылка разбирается обратно тем же парсером без потерь."""
    try:
        parsed = subs.uri_to_server(uri)
    except Exception:
        return False
    if not parsed:
        return False
    if parsed.get("type") != server.get("type"):
        return False
    if parsed.get("host") != server.get("host"):
        return False
    try:
        if int(parsed.get("port") or 0) != int(server.get("port") or 0):
            return False
    except (TypeError, ValueError):
        return False
    for field in ("uuid", "password", "method"):
        want = server.get(field) or ""
        got = parsed.get(field) or ""
        if want and urllib.parse.unquote(got) != want:
            return False
    return True


def main():
    with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)

    os.makedirs(OUT_DIR, exist_ok=True)

    subs_lines = []
    for item in cfg.get("subs") or []:
        url = (item.get("url") or "").strip()
        if url:
            subs_lines.append(url)
    with open(os.path.join(OUT_DIR, "subscriptions.txt"), "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("\n".join(subs_lines) + ("\n" if subs_lines else ""))

    links = []
    skipped = []
    seen = set()
    servers = sorted(cfg.get("servers") or [],
                     key=lambda x: (0 if x.get("latency_ok") else 1,
                                    x.get("latency") or 99999))
    for server in servers:
        stype = server.get("type")
        if stype not in EXPORT_TYPES:
            continue
        build = BUILDERS.get(stype)
        if not build:
            continue
        try:
            uri = build(server)
        except Exception as exc:
            skipped.append("%s %s:%s (%s)" % (stype, server.get("host"), server.get("port"), exc))
            continue
        if uri in seen:
            continue
        if not validate(uri, server):
            skipped.append("%s %s:%s (round-trip mismatch)" % (stype, server.get("host"), server.get("port")))
            continue
        seen.add(uri)
        links.append(uri)

    with open(os.path.join(OUT_DIR, "links.txt"), "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("\n".join(links) + ("\n" if links else ""))

    print("android/subscriptions.txt:", len(subs_lines), "шт.")
    print("android/links.txt:", len(links), "шт.")
    if skipped:
        print("пропущено:", len(skipped))
        for row in skipped[:10]:
            print("  -", row)


if __name__ == "__main__":
    main()
