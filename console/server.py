"""本地 HTTP 服务：控制台 UI + 给游戏内 Lua 的 OpenAI 兼容翻译端点。"""
from __future__ import annotations

import json
import mimetypes
import os
import threading
import time
import traceback
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import branding
import config_store as C
import ime_guard
import installer
import paths
import store
from translator import TranslateError, Translator

WEB_DIR = paths.web_dir()
CONSOLE_LOG = C.LOG_DIR / "console.log"
SEND_FILE = C.HOME / "send.txt"
_LOG_LOCK = threading.Lock()


def log(msg: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    with _LOG_LOCK:
        try:
            with CONSOLE_LOG.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


class App:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.translator = Translator(cfg)

    def save_cfg(self, new_cfg: dict) -> dict:
        key = ((new_cfg.get("api") or {}).get("key") or "").strip()
        if not key:
            new_cfg.setdefault("api", {})["key"] = self.cfg.get("api", {}).get("key", "")
        self.cfg = new_cfg
        self.translator.set_config(new_cfg)
        C.save(new_cfg)
        return new_cfg


APP: App | None = None


class Handler(BaseHTTPRequestHandler):
    server_version = "HD2ChatTranslator/0.1"
    protocol_version = "HTTP/1.1"

    # ---------- plumbing ----------
    def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
        log("HTTP " + (fmt % args))

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code: int = 200):
        # compact like a real API: the mod's minimal JSON reader looks for "content":"..."
        self._send(code, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def _error(self, code: int, message: str):
        self._json({"ok": False, "error": message}, code)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > 2 * 1024 * 1024:
            raise ValueError("body too large")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8", "replace"))

    # ---------- GET ----------
    def do_GET(self):  # noqa: N802
        try:
            u = urlparse(self.path)
            path, qs = u.path, parse_qs(u.query)
            if path in ("/", "/index.html"):
                return self._static("index.html")
            if path.startswith("/web/"):
                return self._static(path[5:])
            if path == "/api/status":
                return self._json(self._status())
            if path == "/api/config":
                return self._json(self._public_cfg())
            if path == "/api/history":
                return self._json({"ok": True, "rows": store.history(
                    int((qs.get("limit") or ["50"])[0]),
                    int((qs.get("offset") or ["0"])[0]),
                    (qs.get("direction") or [None])[0],
                )})
            if path == "/api/logs":
                tail = int((qs.get("tail") or ["150"])[0])
                source = (qs.get("source") or ["mod"])[0]
                if source == "console":
                    return self._json({"ok": True, "text": self._tail(CONSOLE_LOG, tail)})
                return self._json({"ok": True, "text": installer.log_tail(tail)})
            if path == "/api/install/status":
                return self._json({"ok": True, "status": installer.status()})
            if path == "/api/glossary":
                return self._json({"ok": True, "items": APP.cfg.get("glossary") or []})
            if path == "/api/send/status":
                exists = SEND_FILE.is_file()
                return self._json({
                    "ok": True, "pending": exists,
                    "text": SEND_FILE.read_text(encoding="utf-8", errors="replace") if exists else "",
                    "mtime": SEND_FILE.stat().st_mtime if exists else 0,
                })
            if path == "/api/ping":
                return self._json({"ok": True, "t": time.time()})
            if path == "/v1/models":
                # the mod's helper pings this to keep one connection warm
                return self._json({"object": "list", "data": [
                    {"id": "hd2ct-console", "object": "model", "owned_by": "local"}
                ]})
            return self._error(404, "not found")
        except Exception:
            log("GET failed:\n" + traceback.format_exc())
            return self._error(500, "internal error")

    # ---------- POST ----------
    def do_POST(self):  # noqa: N802
        try:
            path = urlparse(self.path).path
            if path == "/v1/chat/completions":
                return self._chat_completions()
            if path == "/api/config":
                return self._save_config()
            if path == "/api/test":
                return self._test()
            if path == "/api/glossary":
                return self._save_glossary()
            if path == "/api/install/open":
                body = self._read_json()
                ok, detail = installer.open_path(str(body.get("what") or ""))
                return self._json({"ok": ok, "detail": detail})
            if path == "/api/install/prepare":
                return self._prepare_install()
            if path == "/api/install/manual":
                return self._manual_install()
            if path == "/api/window/borderless":
                ok, detail = installer.set_borderless()
                return self._json({"ok": ok, "detail": detail})
            if path == "/api/send":
                return self._send_to_game()
            return self._error(404, "not found")
        except Exception:
            log("POST failed:\n" + traceback.format_exc())
            return self._error(500, "internal error")

    # ---------- handlers ----------
    def _static(self, rel: str):
        base = WEB_DIR.resolve()
        p = (base / rel).resolve()
        if base not in p.parents and p != base:
            return self._error(404, "not found")
        if not p.is_file():
            return self._error(404, "not found")
        ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, p.read_bytes(), ctype)

    def _status(self) -> dict:
        st = installer.status()
        st.update({
            "ok": True,
            "stats": store.stats(),
            "port": APP.cfg.get("port"),
            "ime": ime_guard.GUARD.status,
            "branding": {**branding.load(), "build_id": branding.build_id()},
            "config": self._public_cfg(),
        })
        return st

    def _public_cfg(self) -> dict:
        cfg = deepcopy(APP.cfg)
        key = (cfg.get("api") or {}).pop("key", "") or ""
        cfg["api"]["key_set"] = bool(key)
        cfg["api"]["key_hint"] = (key[:6] + "…" + key[-4:]) if len(key) > 12 else ("已设置" if key else "")
        return {"ok": True, "config": cfg}

    def _save_config(self):
        body = self._read_json()
        cfg = body.get("config") if isinstance(body.get("config"), dict) else body
        base = deepcopy(APP.cfg)
        for k, v in cfg.items():
            if k == "api" and isinstance(v, dict):
                base.setdefault("api", {}).update(v)
            elif k in C.DEFAULT_CONFIG:
                base[k] = v
        APP.save_cfg(base)
        if base.get("ime_guard", True):
            ime_guard.GUARD.start()
        else:
            ime_guard.GUARD.stop()
        return self._json({"ok": True, "config": self._public_cfg()["config"]})

    def _save_glossary(self):
        body = self._read_json()
        items = body.get("items")
        if not isinstance(items, list):
            return self._error(400, "items 必须是数组")
        clean = []
        for it in items[:200]:
            if isinstance(it, dict):
                src, dst = str(it.get("src") or "").strip(), str(it.get("dst") or "").strip()
                if src and dst:
                    clean.append({"src": src, "dst": dst})
        APP.save_cfg({**APP.cfg, "glossary": clean})
        return self._json({"ok": True, "items": clean})

    def _test(self):
        body = self._read_json()
        text = str(body.get("text") or "").strip()
        target = str(body.get("target") or APP.cfg.get("read_language") or "zh-CN")
        if not text:
            return self._error(400, "text 不能为空")
        try:
            res = APP.translator.translate(text, target, "in", "TEST")
        except TranslateError as exc:
            return self._error(500, str(exc))
        return self._json({"ok": res.get("ok", False), "result": res})

    def _send_to_game(self):
        """控制台输入 → 翻译 → 写 send.txt，由游戏内 mod 取走并走游戏自己的发送流程。"""
        body = self._read_json()
        text = str(body.get("text") or "").strip()
        if not text:
            return self._error(400, "text 不能为空")
        if not installer.game_running():
            return self._error(409, "游戏未运行：先进入游戏再发送")
        if SEND_FILE.is_file():
            return self._error(409, "上一条还在等待游戏取走，稍后再发")
        target = str(body.get("target") or APP.cfg.get("send_language") or "en")
        force = bool(body.get("force"))
        res = APP.translator.translate(text, target, "out", "CONSOLE")
        if not res.get("ok"):
            return self._error(502, res.get("error") or "翻译失败")
        if res.get("skip"):
            if not force:
                return self._error(400, "这段文字已经是目标语言；要原样发送请勾选「强制发送」")
            translation, lang = text, res.get("lang") or target
        else:
            translation = res.get("translation") or res.get("content") or ""
            lang = res.get("lang") or target
        prefix = APP.cfg.get("prefix") or "auto"
        if prefix == "auto":
            # the tag names the language the reader gets, not the source language
            head = "[%s] " % C.tag_for(target)
        elif prefix in ("", "0"):
            head = ""
        else:
            head = prefix + " "
        final = head + translation
        if len(final.encode("utf-8")) + 1 > 255:
            return self._error(400, "译文太长，超过游戏聊天输入框上限")
        tmp = SEND_FILE.with_suffix(".tmp")
        tmp.write_text(final, encoding="utf-8")
        os.replace(tmp, SEND_FILE)
        log("SEND queued (%d bytes): %s" % (len(final.encode("utf-8")), final))
        return self._json({"ok": True, "queued": final, "translation": translation, "lang": lang})

    def _chat_completions(self):
        body = self._read_json()
        if body.get("mod") == "hd2ct":
            kind = body.get("kind") if body.get("kind") in ("in", "out") else "in"
            text = str(body.get("text") or "")
            target = str(body.get("target") or (APP.cfg.get("read_language") if kind == "in" else APP.cfg.get("send_language")))
            name = str(body.get("name") or "")
        else:
            # 兼容标准 OpenAI 请求（方便用其它工具试）
            kind = "in"
            target = APP.cfg.get("read_language") or "zh-CN"
            name = "OPENAI"
            msgs = body.get("messages") or []
            text = ""
            for m in reversed(msgs):
                if isinstance(m, dict) and m.get("role") == "user":
                    text = str(m.get("content") or "")
                    break
        res = APP.translator.translate(text, target, kind, name)
        if not res.get("ok"):
            return self._json({"error": {"message": res.get("error") or "translate failed"}}, 502)
        content = res.get("content") or "__SKIP__"
        return self._json({
            "id": "hd2ct-" + str(int(time.time() * 1000)),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "hd2ct-console",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    def _prepare_install(self):
        st = installer.status()
        z = installer.mod_zip()
        if not z.is_file():
            return self._error(400, "找不到 mod 包，请先构建：mod/tools/pack_addon.py")
        dest = installer.staging_dir() / z.name
        dest.write_bytes(z.read_bytes())
        return self._json({"ok": True, "zip": str(z), "staged": str(dest), "status": st})

    def _manual_install(self):
        body = self._read_json()
        action = str(body.get("action") or "install")
        import contextlib
        import io

        import install_manual

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = install_manual.install() if action == "install" else install_manual.uninstall()
        return self._json({"ok": rc == 0, "code": rc, "output": buf.getvalue(),
                           "status": installer.status()})

    @staticmethod
    def _tail(path: Path, lines: int) -> str:
        try:
            data = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(data[-max(1, min(lines, 2000)):])
        except OSError:
            return ""


def serve(cfg: dict, port: int | None = None) -> ThreadingHTTPServer:
    global APP
    APP = App(cfg)
    store.init()
    store.cache_prune()
    C.save(cfg)  # 启动即写一份 config.ini，游戏内 2 秒内能读到
    if cfg.get("ime_guard", True):
        ime_guard.GUARD.start()
    if port is None:
        port = int(cfg.get("port") or 8731)
    httpd = ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)
    httpd.daemon_threads = True
    log(f"console listening on http://127.0.0.1:{httpd.server_address[1]}/")
    return httpd
