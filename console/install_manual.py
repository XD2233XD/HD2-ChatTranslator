"""手动部署/卸载（不依赖 Arsenal）：把两个 .patch 放进游戏 data 目录。

  python install_manual.py --install      # 需要先关闭游戏
  python install_manual.py --uninstall
  python install_manual.py --status

槽位约定：patch_1 = 本 mod，patch_2 = Bingus 加载器（加载器在后，符合它 README 的 "LAST"）。
只动这两个文件；游戏自带的 patch_0（语言包）不碰。
"""
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import installer  # noqa: E402
import paths  # noqa: E402

ROOT = paths.app_dir()
BUNDLE = "9ba626afa44a3aa3"
MOD_SLOT = 1
LOADER_SLOT = 2
MOD_MARKER = b"-- HD2-Addon: mods/hd2ct/chat_translator"
LOADER_MARKER = b"mods/codex/loader"


def loader_zip() -> Path | None:
    found = paths.loader_zip_candidates()
    return found[0] if found else None


def patch_from_zip(zpath: Path, inner: str) -> bytes:
    with zipfile.ZipFile(zpath) as z:
        return z.read(inner)


def slot_paths(game: Path, slot: int):
    base = game / "data" / f"{BUNDLE}.patch_{slot}"
    return base, Path(str(base) + ".stream"), Path(str(base) + ".gpu_resources")


def read_head(p: Path, n=65536) -> bytes:
    try:
        with p.open("rb") as f:
            return f.read(n)
    except OSError:
        return b""


def status() -> int:
    game = installer.find_game()
    if not game:
        print("找不到游戏目录")
        return 2
    print("game:", game)
    for slot, marker, name in (
        (MOD_SLOT, MOD_MARKER, "HD2 Chat Translator"),
        (LOADER_SLOT, LOADER_MARKER, "Bingus Shared Loader"),
    ):
        p, _, _ = slot_paths(game, slot)
        if not p.is_file():
            print(f"slot {slot}: 未安装（{name}）")
        elif marker in read_head(p):
            print(f"slot {slot}: 已安装 {name} ({p.stat().st_size} bytes)")
        else:
            print(f"slot {slot}: 被其它文件占用！{p}")
    print("loader zip:", loader_zip() or "缺失")
    return 0


def install() -> int:
    game = installer.find_game()
    if not game:
        print("找不到游戏目录")
        return 2
    if installer.game_running():
        print("游戏正在运行，请先完全退出游戏")
        return 3
    mzip = installer.mod_zip()
    lzip = loader_zip()
    if not mzip.is_file():
        print("找不到 mod 包：", mzip)
        return 2
    if not lzip:
        print("找不到 Bingus 加载器包：mod/vendor/Bingus-Shared-Loader-v20.zip")
        return 2
    mod_patch = patch_from_zip(mzip, f"Addon/{BUNDLE}.patch_0")
    loader_patch = patch_from_zip(lzip, f"data/{BUNDLE}.patch_0")
    assert MOD_MARKER in mod_patch[:1024], "mod 包缺少 addon 声明"
    # the loader is precompiled LuaJIT bytecode; its resource path appears later in the payload
    assert LOADER_MARKER in loader_patch, "加载器包标识不对"

    for slot, blob, marker, name in (
        (MOD_SLOT, mod_patch, MOD_MARKER, "mod"),
        (LOADER_SLOT, loader_patch, LOADER_MARKER, "loader"),
    ):
        p, s, g = slot_paths(game, slot)
        if p.exists() and marker not in read_head(p):
            print(f"槽位 patch_{slot} 已被别的 mod 占用，拒绝覆盖：{p}")
            return 4
        p.write_bytes(blob)
        s.write_bytes(b"")
        g.write_bytes(b"")
        print(f"已写入 patch_{slot} ({len(blob)} bytes) <- {name}")

    print("\n完成。启动游戏后检查：")
    print("  ", installer.LOG_PATH)
    print("  应出现 START version=1.0.0 与 ARMED")
    return 0


def uninstall() -> int:
    game = installer.find_game()
    if not game:
        print("找不到游戏目录")
        return 2
    if installer.game_running():
        print("游戏正在运行，请先完全退出游戏")
        return 3
    removed = 0
    for slot, marker in ((MOD_SLOT, MOD_MARKER), (LOADER_SLOT, LOADER_MARKER)):
        p, s, g = slot_paths(game, slot)
        if p.is_file() and marker in read_head(p):
            for x in (p, s, g):
                if x.exists():
                    x.unlink()
            removed += 1
            print(f"已删除 patch_{slot}")
        elif p.exists():
            print(f"patch_{slot} 不是本工具装的，跳过：{p}")
    print("卸载完成" if removed else "没有可卸载的文件")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--install", action="store_true")
    g.add_argument("--uninstall", action="store_true")
    g.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.install:
        return install()
    if a.uninstall:
        return uninstall()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())

