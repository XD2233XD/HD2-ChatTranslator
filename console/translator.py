"""翻译服务：DeepSeek / OpenAI 兼容端点，JSON 输出，含语言识别、术语表、缓存。"""
from __future__ import annotations

import hashlib
import http.client
import json
import re
import ssl
import threading
import time
from urllib.parse import urlsplit

import config_store as C
import slang
import store

SYSTEM_PROMPT = (
    "You are the translation engine for Helldivers 2 in-game chat. "
    "You always answer with one JSON object and nothing else."
)

# bump when the prompt / slang table changes so old cached answers are not reused
PROMPT_VERSION = 4

USER_TEMPLATE = """Target language: {target_name} ({target_code})
Message direction: {direction}
Sender: {sender}
Message:
{text}

Return JSON exactly in this shape:
{{"lang":"<ISO 639-1 source language>","system":<true|false>,"translation":"<translated text>"}}

Rules:
- lang: the source language of the message, two letters when possible (en, zh, ja, ko, ru, es, fr, de, pt, it, pl, tr, uk, ar, th, vi, id, nl).
- system: true ONLY for game or server notifications: a player joined/left/was kicked, connection or host migration notices, mission/server state messages. Player chat is never a system notification, even when it is one word or rude.
- If the message is already in {target_name}, return an empty translation "".
- Keep player names, numbers, [tags], stratagem names, weapon names and slang. Translate meaning, not word by word.
- Helldivers 2 abbreviations (RR, EAT, AC, AMR, HMG, SC, FRV, EXO, SOS, 500kg) must be rendered as the
  target-language name plus the original abbreviation in parentheses, for example RR -> 无后座力炮（RR）,
  EAT -> 一次性反坦克（EAT）. Never leave them as bare letters when the target reader may not know them.
- One chat line only, no newline, no quotes around the translation, at most 200 characters.
{slang}
{glossary}"""


class TranslateError(Exception):
    pass


def _extract_json(text: str):
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    a, b = s.find("{"), s.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        return json.loads(s[a:b + 1])
    except ValueError:
        return None


class LLMClient:
    def __init__(self, base_url: str, key: str, model: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.key = key
        self.model = model
        self.timeout = timeout
        self._conn = None
        self._sig = None

    def _connect(self):
        parts = urlsplit(self.base_url)
        scheme = (parts.scheme or "https").lower()
        host = parts.hostname or "api.deepseek.com"
        port = parts.port or (443 if scheme == "https" else 80)
        path = parts.path or ""
        if path.endswith("/chat/completions"):
            self._path = path
        else:
            self._path = path.rstrip("/") + "/chat/completions"
        if scheme == "https":
            ctx = ssl.create_default_context()
            self._conn = http.client.HTTPSConnection(host, port, timeout=self.timeout, context=ctx)
        else:
            self._conn = http.client.HTTPConnection(host, port, timeout=self.timeout)

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None

    def chat(self, messages, json_mode=True, max_tokens=300) -> str:
        if not self.key:
            raise TranslateError("尚未配置 API Key（设置 → 翻译服务）")
        if self._conn is None:
            self._connect()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": False,
            # 关掉推理：聊天短句没有可推理的内容，开着会多烧 100+ token 和 500ms
            "thinking": {"type": "disabled"},
            "reasoning_effort": "none",
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.key,
            "Accept": "application/json",
        }
        last = None
        for attempt in (0, 1):
            try:
                self._conn.request("POST", self._path, body=body, headers=headers)
                resp = self._conn.getresponse()
                raw = resp.read()
                if resp.status != 200:
                    detail = raw[:300].decode("utf-8", "replace")
                    # 有些兼容端点不认 response_format / thinking，去掉重试一次
                    if resp.status in (400, 422) and attempt == 0:
                        payload.pop("response_format", None)
                        payload.pop("thinking", None)
                        payload.pop("reasoning_effort", None)
                        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                        last = f"HTTP {resp.status}: {detail}"
                        continue
                    raise TranslateError(f"HTTP {resp.status}: {detail}")
                data = json.loads(raw.decode("utf-8", "replace"))
                return data["choices"][0]["message"]["content"]
            except TranslateError:
                raise
            except Exception as exc:  # 连接被对端关闭 / 超时
                last = str(exc)
                self.close()
                self._connect()
        raise TranslateError(f"请求失败：{last}")


class Translator:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._lock = threading.Lock()
        self._client = None
        self._client_sig = None

    def set_config(self, cfg: dict):
        self.cfg = cfg

    def _client_for_cfg(self):
        api = self.cfg.get("api") or {}
        sig = (api.get("base_url"), api.get("key"), api.get("model"), api.get("timeout"))
        if self._client is None or sig != self._client_sig:
            if self._client is not None:
                self._client.close()
            self._client = LLMClient(
                api.get("base_url") or "https://api.deepseek.com/v1",
                api.get("key") or "",
                api.get("model") or "deepseek-chat",
                float(api.get("timeout") or 20),
            )
            self._client_sig = sig
        return self._client

    def _glossary_text(self) -> str:
        terms = self.cfg.get("glossary") or []
        lines = []
        for item in terms[:40]:
            src = str(item.get("src") or "").strip()
            dst = str(item.get("dst") or "").strip()
            if src and dst:
                lines.append(f'- "{src}" => "{dst}"')
        if not lines:
            return ""
        return "Glossary (use when the source term appears):\n" + "\n".join(lines)

    def _tag_prefix(self, lang: str, target: str) -> str:
        mode = self.cfg.get("tag_mode", "source")
        if mode == "off":
            return ""
        if mode == "target":
            return f"[{C.tag_for(target)}] "
        if mode == "arrow":
            return f"[{C.tag_for(lang)}→{C.tag_for(target)}] "
        return f"[{C.tag_for(lang)}] "

    def translate(self, text: str, target: str, kind: str = "in", name: str = "") -> dict:
        text = (text or "").strip()
        target = (target or "zh-CN").strip()
        if not text:
            return {"ok": True, "skip": True, "content": "__SKIP__", "reason": "empty",
                    "lang": "", "system": False, "ms": 0, "cached": False}

        # 系统消息在 Lua 侧已按发送者名单过滤；这里再按名单兜底一次，省一次 API
        names = [x for x in (self.cfg.get("system_names") or []) if x]
        if name in names:
            return {"ok": True, "skip": True, "content": "__SKIP__", "reason": "system_name",
                    "lang": "", "system": True, "ms": 0, "cached": False}

        if not (self.cfg.get("inbound", True) if kind == "in" else self.cfg.get("outbound", True)):
            return {"ok": True, "skip": True, "content": "__SKIP__", "reason": "disabled",
                    "lang": "", "system": False, "ms": 0, "cached": False}

        # 游戏黑话：整条精确命中时直接翻，零延迟，也不会被模型当成人名/乱码
        fast = slang.lookup(text, target)
        if fast is not None:
            translation, lang = fast
            if not translation:
                store.add_history(kind, name, lang, target, text, "", 0, True, "skip:same_language")
                return {"ok": True, "skip": True, "content": "__SKIP__", "reason": "same_language",
                        "lang": lang, "system": False, "ms": 0, "cached": False, "fast": True}
            final = (self._tag_prefix(lang, target) + translation) if kind == "in" else translation
            store.add_history(kind, name, lang, target, text, final, 0, True, "slang")
            return {"ok": True, "skip": False, "content": final, "lang": lang,
                    "system": False, "translation": translation, "ms": 0, "cached": False,
                    "fast": True}

        glossary = self._glossary_text()
        ckey = hashlib.sha1(
            f"v{PROMPT_VERSION}|{kind}|{target}|{text}|{self.cfg.get('tag_mode')}|{glossary}"
            .encode("utf-8", "replace")
        ).hexdigest()
        cached = store.cache_get(ckey)
        if cached is not None:
            cached = dict(cached)
            cached["cached"] = True
            cached["ms"] = 0
            return cached

        direction = "teammate -> me" if kind == "in" else "my own message -> teammates"
        user = USER_TEMPLATE.format(
            target_name=C.english_name(target),
            target_code=target,
            direction=direction,
            sender=name or "(unknown)",
            text=text,
            slang=slang.prompt_block(),
            glossary=(glossary + "\n") if glossary else "",
        )
        t0 = time.perf_counter()
        try:
            with self._lock:
                content = self._client_for_cfg().chat(
                    [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": user}]
                )
        except TranslateError as exc:
            ms = int((time.perf_counter() - t0) * 1000)
            store.add_history(kind, name, "", target, text, "", ms, False, str(exc))
            return {"ok": False, "skip": False, "error": str(exc), "lang": "", "system": False,
                    "ms": ms, "cached": False, "content": ""}

        data = _extract_json(content)
        if isinstance(data, dict) and ("translation" in data or "text" in data):
            lang = str(data.get("lang") or "").lower()[:8]
            system = bool(data.get("system"))
            translation = str(data.get("translation") if "translation" in data else data.get("text") or "")
        else:
            lang, system, translation = "", False, content or ""
        translation = translation.strip().strip('"').replace("\n", " ").strip()
        ms = int((time.perf_counter() - t0) * 1000)

        lang = (lang or "").lower()
        if lang.startswith(target.split("-")[0].lower()) or (not translation):
            result = {"ok": True, "skip": True, "content": "__SKIP__", "reason": "same_language",
                      "lang": lang, "system": system, "ms": ms, "cached": False}
            store.cache_put(ckey, result)
            store.add_history(kind, name, lang, target, text, "", ms, True, "skip:same_language")
            return result
        if system:
            result = {"ok": True, "skip": True, "content": "__SKIP__", "reason": "system_text",
                      "lang": lang, "system": True, "ms": ms, "cached": False}
            store.cache_put(ckey, result)
            store.add_history(kind, name, lang, target, text, "", ms, True, "skip:system_text")
            return result
        if len(translation) > 240:
            translation = translation[:240].rstrip()

        if kind == "in":
            final = self._tag_prefix(lang, target) + translation
        else:
            final = translation

        result = {"ok": True, "skip": False, "content": final, "lang": lang,
                  "system": False, "translation": translation, "ms": ms, "cached": False}
        store.cache_put(ckey, result)
        store.add_history(kind, name, lang, target, text, final, ms, True, None)
        return result


def test_translation(cfg: dict, text: str, target: str) -> dict:
    tr = Translator(cfg)
    return tr.translate(text, target, "in", "TEST")
