"""读取作者/水印/build 元数据（开发目录或发布包 exe 旁边）。"""
from __future__ import annotations

import json
from pathlib import Path

import paths

DEFAULT = {
    "author": "XD2233XD",
    "watermark_id": "HD2CT-XD2233XD-local",
    "namespace": "hd2ct",
}


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def load() -> dict:
    out = dict(DEFAULT)
    for base in (paths.app_dir(), paths.console_dir().parent):
        data = _read(Path(base) / "branding.json")
        if data:
            out.update({k: data[k] for k in ("author", "watermark_id", "namespace") if k in data})
            break
    return out


def build_id() -> str:
    for base in (paths.app_dir(), paths.console_dir().parent):
        data = _read(Path(base) / "WATERMARK.json")
        if data and data.get("build_id"):
            return str(data["build_id"])
    return "dev"
