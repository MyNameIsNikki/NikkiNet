# -*- coding: utf-8 -*-
"""Проверка и установка обновлений приложения из GitHub Releases.

Репозиторий задан в version.py (GITHUB_REPO). Модуль ничего не знает о
веб-панели: proxy_app опрашивает status()/update_available() и рисует
баннер сам.

Схема обновления:
  1) check_latest() — GET api.github.com/repos/<repo>/releases/latest
  2) download_and_prepare() — скачать zip-актив релиза в %TEMP%,
     распаковать в BASE_DIR/.update, сгенерировать apply_update.bat
  3) приложение завершает работу штатно (останавливает sing-box,
     снимает системный прокси, отпускает .lock), затем запускает
     apply_update.bat и выходит
  4) bat ждёт исчезновения старого PID, копирует .update поверх
     приложения (не трогая config.json/geo.json/.lock/логи),
     запускает start.bat и удаляет себя
"""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile

import version

API_LATEST = "https://api.github.com/repos/%s/releases/latest" % version.GITHUB_REPO
CHECK_INTERVAL = 6 * 3600  # проверять каждые 6 часов
TIMEOUT = 15
STAGE_DIR = ".update"
APPLY_BAT = "apply_update.bat"

_lock = threading.Lock()
_latest = None
_last_error = None
_last_check_ts = 0


def _headers():
    return {"User-Agent": "NikkiNet-Updater/" + version.APP_VERSION}


def check_latest():
    """Запросить последний релиз из GitHub. dict с данными или None при ошибке."""
    global _latest, _last_error, _last_check_ts
    try:
        req = urllib.request.Request(API_LATEST, headers=_headers())
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = str(data.get("tag_name") or "").strip().lstrip("vV")
        zip_asset = None
        for a in data.get("assets") or []:
            if str(a.get("name") or "").lower().endswith(".zip"):
                zip_asset = a
                break
        if not tag or not zip_asset:
            _last_error = "в последнем релизе нет zip-файла"
            return None
        info = {
            "version": tag,
            "zip_url": zip_asset.get("browser_download_url") or "",
            "zip_size": zip_asset.get("size") or 0,
            "notes": str(data.get("body") or "")[:4000],
            "url": data.get("html_url") or "",
            "checked_ts": int(time.time()),
        }
        if not info["zip_url"]:
            _last_error = "у zip-актива нет ссылки на скачивание"
            return None
        with _lock:
            _latest = info
            _last_error = None
            _last_check_ts = info["checked_ts"]
        return dict(info)
    except Exception as exc:
        _last_error = str(exc)
        return None


def is_newer(remote, local):
    """Сравнение версий вида '1.2.3' > '1.10.0' по числам, а не по строкам."""
    try:
        r = [int(x) for x in str(remote).split(".")]
        l = [int(x) for x in str(local).split(".")]
    except (TypeError, ValueError):
        return False
    n = max(len(r), len(l))
    r += [0] * (n - len(r))
    l += [0] * (n - len(l))
    return r > l


def current_latest():
    with _lock:
        return dict(_latest) if _latest else None


def update_available():
    latest = current_latest()
    if latest and is_newer(latest["version"], version.APP_VERSION):
        return latest
    return None


def status():
    with _lock:
        latest = dict(_latest) if _latest else None
        err = _last_error
        ts = _last_check_ts
    return {
        "current": version.APP_VERSION,
        "repo": version.GITHUB_REPO,
        "latest": latest,
        "available": bool(latest and is_newer(latest["version"], version.APP_VERSION)),
        "last_error": err,
        "last_check_ts": ts,
    }


def start_background(on_found=None):
    """Фоновый поток: раз в CHECK_INTERVAL проверять релизы.

    on_found(upd_dict) вызывается один раз на каждую новую версию
    (например, чтобы записать строку в лог панели).
    """
    def _loop():
        time.sleep(5)
        notified = ""
        while True:
            check_latest()
            upd = update_available()
            if upd and upd["version"] != notified:
                notified = upd["version"]
                print("Доступно обновление: v%s (текущая v%s) — панель предложит обновиться"
                      % (upd["version"], version.APP_VERSION))
                if on_found:
                    try:
                        on_found(upd)
                    except Exception:
                        pass
            time.sleep(CHECK_INTERVAL)

    threading.Thread(target=_loop, daemon=True).start()


# ---------- установка обновления ----------

def _download_zip(url):
    tmp = os.path.join(tempfile.gettempdir(), "nikkinet-update.zip")
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=600) as resp:
        with open(tmp, "wb") as fh:
            shutil.copyfileobj(resp, fh)
    return tmp


def _safe_members(zf):
    """Не позволять архиву писать вне папки назначения (zip-slip)."""
    bad = []
    for name in zf.namelist():
        norm = name.replace("\\", "/")
        parts = [p for p in norm.split("/") if p]
        if norm.startswith("/") or ":" in norm or ".." in parts:
            bad.append(name)
    if bad:
        raise ValueError("небезопасные пути в архиве: %r" % bad[:3])


def _stage_zip(zip_path, base_dir):
    stage = os.path.join(base_dir, STAGE_DIR)
    if os.path.isdir(stage):
        shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        _safe_members(zf)
        zf.extractall(stage)
    # если всё упаковано в одну подпапку (NikkiNet-1.2.3/...) — поднять на уровень
    entries = [e for e in os.listdir(stage) if e != APPLY_BAT]
    if len(entries) == 1 and os.path.isdir(os.path.join(stage, entries[0])):
        inner = os.path.join(stage, entries[0])
        for e in os.listdir(inner):
            os.rename(os.path.join(inner, e), os.path.join(stage, e))
        try:
            os.rmdir(inner)
        except OSError:
            pass
    return stage


_APPLY_BAT_TEMPLATE = r"""@echo off
rem ============================================================
rem  NikkiNet: применение скачанного обновления.
rem  Файл создан автоматически и удалит сам себя по завершении.
rem ============================================================
cd /d "%~dp0"
set OLDPID=%%PID%%

:waitloop
tasklist /FI "PID eq %OLDPID%" 2>nul | find /I "%OLDPID%" >nul
if %errorlevel% equ 0 (
  ping -n 2 127.0.0.1 >nul
  goto waitloop
)
ping -n 3 127.0.0.1 >nul
taskkill /IM sing-box.exe /F >nul 2>&1

robocopy ".update" "." /MIR /R:2 /W:1 /NFL /NDL /NJH /NJS /NP /XD .update __pycache__ .git .github /XF config.json geo.json .lock crash.log *.log apply_update.bat sing-box-config.json test-*.json .gitignore README.md >nul

start "" "%~dp0start.bat"
ping -n 4 127.0.0.1 >nul
rd /s /q ".update" 2>nul
(goto) 2>nul & del "%~f0"
exit /b 0
"""


def _write_apply_bat(base_dir):
    path = os.path.join(base_dir, APPLY_BAT)
    with open(path, "w", encoding="ascii", newline="\r\n") as fh:
        fh.write(_APPLY_BAT_TEMPLATE.replace("%%PID%%", str(os.getpid())))
    return path


def download_and_prepare(base_dir):
    """Скачать релиз, распаковать в BASE_DIR/.update, создать apply_update.bat.

    Возвращает путь к apply_update.bat — его надо запустить прямо перед
    завершением приложения (launch_apply_bat), а затем выйти.
    """
    upd = update_available()
    if not upd:
        raise RuntimeError("нет доступного обновления")
    zip_path = _download_zip(upd["zip_url"])
    try:
        stage = _stage_zip(zip_path, base_dir)
    finally:
        try:
            os.remove(zip_path)
        except OSError:
            pass
    if not os.path.isfile(os.path.join(stage, "proxy_app.py")):
        shutil.rmtree(stage, ignore_errors=True)
        raise RuntimeError("в архиве обновления нет proxy_app.py")
    if not os.path.isfile(os.path.join(stage, "start.bat")):
        shutil.rmtree(stage, ignore_errors=True)
        raise RuntimeError("в архиве обновления нет start.bat")
    return _write_apply_bat(base_dir)


def launch_apply_bat(bat_path):
    """Запустить apply_update.bat отдельным процессом: он ждёт, пока старый
    PID приложения исчезнет, заменяет файлы и поднимает приложение заново."""
    flags = 0
    if os.name == "nt":
        flags = 0x08000000  # CREATE_NO_WINDOW
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        cwd=os.path.dirname(os.path.abspath(bat_path)) or None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
