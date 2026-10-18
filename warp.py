import base64
import json
import os
import time
import urllib.error
import urllib.request

WARP_API = "https://api.cloudflareclient.com/v0a2169/reg"
WARP_TOS = "2021-04-05T13:00:00.000+00:00"
WARP_PEER_PUBKEY = "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo="
WARP_HOST = "engage.cloudflareclient.com"
WARP_PORT = 2408
WARP_MTU = 1280

_P = 2 ** 255 - 19
_A24 = 121665


def _cswap(swap, x2, x3):
    if swap:
        return x3, x2
    return x2, x3


def _x25519_scalar_mult(k_bytes, u_bytes):
    k = bytearray(k_bytes)
    k[0] &= 248
    k[31] &= 127
    k[31] |= 64
    k = int.from_bytes(bytes(k), "little")
    u = int.from_bytes(u_bytes, "little") & ((1 << 255) - 1)

    x1 = u
    x2, z2, x3, z3 = 1, 0, x1, 1
    swap = 0
    for t in reversed(range(255)):
        k_t = (k >> t) & 1
        swap ^= k_t
        x2, x3 = _cswap(swap, x2, x3)
        z2, z3 = _cswap(swap, z2, z3)
        swap = k_t

        a = (x2 + z2) % _P
        aa = a * a % _P
        b = (x2 - z2) % _P
        bb = b * b % _P
        e = (aa - bb) % _P
        c = (x3 + z3) % _P
        d = (x3 - z3) % _P
        da = d * a % _P
        cb = c * b % _P
        x3 = pow(da + cb, 2, _P)
        z3 = x1 * pow(da - cb, 2, _P) % _P
        x2 = aa * bb % _P
        z2 = e * (aa + _A24 * e) % _P

    x2, x3 = _cswap(swap, x2, x3)
    z2, z3 = _cswap(swap, z2, z3)
    return (x2 * pow(z2, _P - 2, _P) % _P).to_bytes(32, "little")


def gen_keypair():
    priv = os.urandom(32)
    pub = _x25519_scalar_mult(priv, (9).to_bytes(32, "little"))
    return base64.b64encode(priv).decode(), base64.b64encode(pub).decode()


def _opener(proxy):
    if proxy:
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        return urllib.request.build_opener(handler)
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def register(proxy=None, timeout=25):
    """Регистрирует устройство WARP. proxy = 'http://ip:port' или None.
    Возвращает dict с ключами wg-конфигурации или вызывает RuntimeError."""
    priv_b64, pub_b64 = gen_keypair()
    body = json.dumps({
        "key": pub_b64,
        "install_id": "",
        "fcm_token": "",
        "tos": WARP_TOS,
        "model": "PC",
        "serial_number": os.urandom(8).hex(),
        "locale": "en_US",
    }).encode("utf-8")
    req = urllib.request.Request(
        WARP_API,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "CF-Client-Version": "a2169",
            "User-Agent": "okhttp/3.12.1",
        },
    )
    op = _opener(proxy)
    try:
        with op.open(req, timeout=timeout) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read()[:300].decode("utf-8", "ignore")
        except Exception:
            detail = ""
        raise RuntimeError(f"WARP API HTTP {e.code}: {detail}")
    except Exception as e:
        raise RuntimeError(f"WARP API недоступен: {e}")

    cfg = {
        "privkey": priv_b64,
        "peer_pubkey": WARP_PEER_PUBKEY,
        "host": WARP_HOST,
        "port": WARP_PORT,
        "mtu": WARP_MTU,
        "local_addrs": ["172.16.0.2/32"],
        "reg_id": resp.get("id", ""),
        "reg_ts": time.time(),
    }
    config = resp.get("config") or {}
    client_id = config.get("client_id") or ""
    peers = config.get("peers") or []
    if peers and peers[0].get("public_key"):
        cfg["peer_pubkey"] = peers[0]["public_key"]
    ep_host = ((peers[0].get("endpoint") or {}).get("host") or "") if peers else ""
    if ":" in ep_host:
        ep_addr, _, ep_port = ep_host.rpartition(":")
        if ep_port.isdigit():
            cfg["host"] = ep_addr
            cfg["port"] = int(ep_port)
    if client_id:
        try:
            raw = base64.b64decode(client_id)
            if len(raw) >= 3:
                cfg["reserved"] = [raw[0], raw[1], raw[2]]
        except Exception:
            pass
    iface = config.get("interface") or {}
    ia = iface.get("addresses") or {}
    addrs = []
    if isinstance(ia, dict):
        if ia.get("v4"):
            v4 = str(ia["v4"])
            if "/" not in v4:
                v4 += "/32"
            addrs.append(v4)
        if ia.get("v6"):
            v6 = str(ia["v6"])
            if "/" not in v6:
                v6 += "/128"
            addrs.append(v6)
    elif isinstance(ia, list):
        addrs = [str(x) for x in ia]
    if addrs:
        cfg["local_addrs"] = addrs
    return cfg


def reg_valid(reg):
    if not isinstance(reg, dict) or not reg.get("privkey") or not reg.get("peer_pubkey"):
        return False
    addrs = reg.get("local_addrs") or []
    return bool(addrs) and all("/" in str(a) for a in addrs)


def make_server(cfg):
    """dict регистрации -> сервер для state.servers"""
    return {
        "name": "Cloudflare WARP",
        "type": "wireguard",
        "host": cfg["host"],
        "port": cfg["port"],
        "privkey": cfg["privkey"],
        "peer_pubkey": cfg["peer_pubkey"],
        "local_addrs": cfg["local_addrs"],
        "reserved": cfg.get("reserved"),
        "mtu": cfg["mtu"],
        "source": "warp",
    }
