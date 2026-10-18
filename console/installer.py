"""安装与状态探测：找游戏、找 Arsenal / Bingus、看 mod 日志。"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from config_store import HOME
import paths

GAME_DIR_NAMES = ("Helldivers 2", "Helldivers2")
LOG_PATH = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CowboyBingus" / "Helldivers2" / "Logs" / "HD2ChatTranslator.log"
MOD_MARKER = b"-- HD2-Addon: mods/hd2ct/chat_translator"
LOADER_MARKER = b"mods/codex/loader"
BUNDLE = "9ba626afa44a3aa3"


def _steam_roots() -> list[Path]:
    roots: list[Path] = []
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steam = Path(winreg.QueryValueEx(k, "SteamPath")[0])
        roots.append(steam)
        vdf = steam / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            text = vdf.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                p = Path(m.group(1).replace("\\\\", "\\"))
                if p not in roots:
                    roots.append(p)
    except OSError:
        pass
    for d in "CDEFGH":
        p = Path(f"{d}:/SteamLibrary")
        if p.is_dir() and p not in roots:
            roots.append(p)
    return roots


def find_game() -> Path | None:
    for root in _steam_roots():
        for name in GAME_DIR_NAMES:
            p = root / "steamapps" / "common" / name
            if (p / "bin" / "helldivers2.exe").is_file():
                return p
    return None


def arsenal_mods_dir() -> Path | None:
    for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")):
        if not base:
            continue
        p = Path(base) / "hd2arsenal" / "mods"
        if p.is_dir():
            return p
    return None


def arsenal_dir() -> Path | None:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    for name in ("hd2arsenal", "HD2Arsenal"):
        p = Path(base) / name
        if p.is_dir():
            return p
    return None


def installed_mods() -> list[str]:
    mods = arsenal_mods_dir()
    if not mods:
        return []
    try:
        return sorted(x.name for x in mods.iterdir() if x.is_dir())
    except OSError:
        return []


def bingus_installed() -> bool:
    return any("bingus" in m.lower() for m in installed_mods())


def mod_installed() -> bool:
    if any("chat_translator" in m.lower() or "hd2ct" in m.lower() for m in installed_mods()):
        return True
    game = find_game()
    if not game:
        return False
    data = game / "data"
    if not data.is_dir():
        return False
    try:
        for f in data.glob("*.patch_*"):
            try:
                head = f.open("rb").read(1024)
            except OSError:
                continue
            if MOD_MARKER in head:
                return True
    except OSError:
        pass
    return False


def game_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq helldivers2.exe", "/NH"],
            capture_output=True, timeout=5,
        )
        return b"helldivers2.exe" in (out.stdout or b"").lower()
    except Exception:
        return False


def log_tail(lines: int = 120) -> str:
    try:
        data = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(data[-max(1, int(lines)):])
    except OSError:
        return ""


def log_mtime() -> float:
    try:
        return LOG_PATH.stat().st_mtime
    except OSError:
        return 0.0


def mod_zip() -> Path:
    found = paths.mod_zip_candidates()
    if found:
        return found[0]
    return paths.app_dir() / "mod" / "HD2ChatTranslator-1.0.0.zip"


def staging_dir() -> Path:
    p = HOME / "install"
    p.mkdir(parents=True, exist_ok=True)
    return p


def manual_slots() -> dict:
    """本工具手动部署的两个槽位（patch_1 = mod，patch_2 = loader）。"""
    game = find_game()
    out = {"mod": False, "loader": False, "paths": {}}
    if not game:
        return out
    for slot, marker, key in ((1, MOD_MARKER, "mod"), (2, LOADER_MARKER, "loader")):
        p = game / "data" / f"{BUNDLE}.patch_{slot}"
        out["paths"][key] = str(p)
        try:
            with p.open("rb") as f:
                out[key] = marker in f.read(65536)
        except OSError:
            out[key] = False
    return out


def settings_config() -> Path | None:
    base = os.environ.get("APPDATA")
    if not base:
        return None
    p = Path(base) / "Arrowhead" / "Helldivers2" / "user_settings.config"
    return p if p.is_file() else None


def set_borderless() -> tuple[bool, str]:
    """把游戏改成无边框窗口（IME 候选窗弹出时不容易把游戏切出去）。需先退出游戏。"""
    if game_running():
        return False, "游戏正在运行，请先完全退出"
    p = settings_config()
    if not p:
        return False, "找不到 user_settings.config"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, f"读配置失败：{exc}"
    backup = p.with_suffix(p.suffix + ".bak-hd2ct")
    try:
        backup.write_text(text, encoding="utf-8")
    except OSError:
        pass
    wanted = {"fullscreen": "false", "borderless_fullscreen": "true"}
    lines = text.splitlines()
    seen = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip().lower() if "=" in line else ""
        if key in wanted:
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}{key} = {wanted[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, val in wanted.items():
        if key not in seen:
            out.append(f"{key} = {val}")
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return True, "已改为无边框窗口（fullscreen=false, borderless_fullscreen=true），重启游戏生效。备份：" + str(backup)


def status() -> dict:
    game = find_game()
    mods = installed_mods()
    manual = manual_slots()
    return {
        "game": str(game) if game else "",
        "game_running": game_running(),
        "arsenal": str(arsenal_dir() or ""),
        "arsenal_mods": str(arsenal_mods_dir() or ""),
        "mods": mods,
        "bingus": bingus_installed() or manual["loader"],
        "mod_installed": mod_installed() or manual["mod"],
        "manual": manual,
        "log": str(LOG_PATH),
        "log_mtime": log_mtime(),
        "zip": str(mod_zip()),
        "zip_exists": mod_zip().is_file(),
    }


def open_path(what: str) -> tuple[bool, str]:
    """打开文件夹或下载页；只允许固定目标，避免变成任意路径执行器。"""
    game = find_game()
    targets = {
        "game": str(game) if game else "",
        "data": str(game / "data") if game else "",
        "arsenal_mods": str(arsenal_mods_dir() or ""),
        "home": str(HOME),
        "logs": str(LOG_PATH.parent if LOG_PATH.parent.is_dir() else HOME),
        "zip_dir": str(mod_zip().parent),
    }
    if what in targets:
        path = targets[what]
        if not path or not Path(path).exists():
            return False, "路径不存在：" + (path or "(空)")
        os.startfile(path)  # type: ignore[attr-defined]
        return True, path
    return False, "未知目标"

