"""运行路径：开发目录 vs PyInstaller 冻结目录。"""
from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """exe 所在目录（冻结）或项目根目录（开发）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def console_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def web_dir() -> Path:
    return console_dir() / "web"


def mod_zip_candidates() -> list[Path]:
    base = app_dir()
    dirs = [base / "mod", base / "mod" / "dist", base.parent / "mod" / "dist"]
    out: list[Path] = []
    for d in dirs:
        if d.is_dir():
            out.extend(sorted(d.glob("HD2ChatTranslator-*.zip"),
                              key=lambda p: p.stat().st_mtime, reverse=True))
    return out


def loader_zip_candidates() -> list[Path]:
    base = app_dir()
    names = ("Bingus-Shared-Loader-v20.zip", "Bingus-Shared-Loader-v19.zip")
    dirs = [base / "loader", base / "mod" / "vendor", base / "调研"]
    out: list[Path] = []
    for d in dirs:
        for n in names:
            p = d / n
            if p.is_file():
                out.append(p)
    return out
