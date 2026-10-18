"""HD2 Chat Translator 控制台入口。

  HD2ChatTranslator.exe     双击启动控制台并打开浏览器（发布版）
  python app.py             开发模式
  python app.py --no-open   只启动服务
  python app.py --diagnose  打印环境/安装/日志状态后退出
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
import traceback
import webbrowser


def _early(msg: str) -> None:
    """最早期的落盘日志：冻结版启动失败时至少能知道走到哪一步。"""
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n"
    candidates = []
    if os.environ.get("HD2CT_DATA_DIR"):
        candidates.append(os.path.join(os.environ["HD2CT_DATA_DIR"], "early.log"))
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(os.path.join(os.environ["LOCALAPPDATA"], "HD2ChatTranslator", "early.log"))
    import tempfile
    candidates.append(os.path.join(tempfile.gettempdir(), "HD2ChatTranslator-early.log"))
    for path in candidates:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
            break
        except Exception:
            continue
    try:
        print("EARLY " + msg, flush=True)
    except Exception:
        pass


_early("module start frozen=%s" % getattr(sys, "frozen", False))

if getattr(sys, "stdout", None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if getattr(sys, "stderr", None):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
_early("stdout ready")

import config_store as C
import installer
import server
import store
_early("imports ready")


def say(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        pass


def boot_log(text: str) -> None:
    try:
        p = C.LOG_DIR / "startup.log"
        with p.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + text + "\n")
    except Exception:
        pass


def message_box(text: str, title: str = "HD2 Chat Translator", error: bool = False) -> None:
    try:
        flags = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(0, text, title, flags)
    except Exception:
        pass


def diagnose() -> int:
    st = installer.status()
    st["stats"] = store.stats()
    st["config_path"] = str(C.CONFIG_JSON)
    st["ini_path"] = str(C.CONFIG_INI)
    say(json.dumps(st, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--diagnose", action="store_true")
    args = ap.parse_args()

    if args.diagnose:
        return diagnose()

    cfg = C.load()
    if args.port:
        cfg["port"] = args.port
    missing = not ((cfg.get("api") or {}).get("key") or "").strip()
    boot_log("main start port=%s frozen=%s" % (cfg.get("port"), getattr(sys, "frozen", False)))

    try:
        httpd = server.serve(cfg)
    except OSError as exc:
        boot_log("serve failed: " + repr(exc))
        server.log("start failed: " + repr(exc))
        message_box(
            "控制台启动失败：端口 %s 可能被占用。\n\n%s\n\n"
            "请关掉旧的 HD2ChatTranslator 进程后重试。" % (cfg.get("port"), exc),
            error=True,
        )
        return 1

    url = "http://127.0.0.1:%d/" % httpd.server_address[1]
    boot_log("serving " + url)
    say("HD2 Chat Translator 控制台: " + url)
    if missing:
        say("提示：还没有填 API Key，打开页面 → 设置 → 翻译服务 填入。")
    say("按 Ctrl+C 停止。")
    if not args.no_open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        say("\n已停止。")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    _early("entry")
    try:
        code = main()
    except Exception:
        _early("FATAL\n" + traceback.format_exc())
        boot_log("FATAL\n" + traceback.format_exc())
        message_box("启动失败，详情见：\n%LOCALAPPDATA%\\HD2ChatTranslator\\early.log", error=True)
        code = 1
    raise SystemExit(code)
