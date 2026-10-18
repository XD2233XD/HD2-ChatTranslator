"""配置存储：console.json（含密钥，仅本机）+ config.ini（给游戏内 Lua 读）。"""
from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path

APP_NAME = "HD2ChatTranslator"

LANGUAGES = {
    "zh-CN": ("简体中文", "Simplified Chinese", "中"),
    "zh-TW": ("繁體中文", "Traditional Chinese", "繁"),
    "en": ("英语", "English", "英"),
    "ja": ("日语", "Japanese", "日"),
    "ko": ("韩语", "Korean", "韩"),
    "ru": ("俄语", "Russian", "俄"),
    "uk": ("乌克兰语", "Ukrainian", "乌"),
    "es": ("西班牙语", "Spanish", "西"),
    "fr": ("法语", "French", "法"),
    "de": ("德语", "German", "德"),
    "pt": ("葡萄牙语", "Portuguese", "葡"),
    "it": ("意大利语", "Italian", "意"),
    "pl": ("波兰语", "Polish", "波"),
    "tr": ("土耳其语", "Turkish", "土"),
    "ar": ("阿拉伯语", "Arabic", "阿"),
    "th": ("泰语", "Thai", "泰"),
    "vi": ("越南语", "Vietnamese", "越"),
    "id": ("印尼语", "Indonesian", "印尼"),
    "nl": ("荷兰语", "Dutch", "荷"),
}

TAGS = {
    "zh": "CN", "en": "EN", "ja": "JA", "ko": "KO", "ru": "RU", "uk": "UA",
    "es": "ES", "fr": "FR", "de": "DE", "pt": "PT", "it": "IT", "pl": "PL",
    "tr": "TR", "ar": "AR", "th": "TH", "vi": "VI", "id": "ID", "nl": "NL",
}

DEFAULT_CONFIG = {
    "read_language": "zh-CN",
    "send_language": "en",
    "inbound": True,
    "outbound": True,
    "inbound_self": False,        # 调试：把自己发的行也写一次译文（验证入站写入链路）
    "inbound_render": "line",     # line = 本地单独一条消息（默认）；row = 写回原行
    "line_prefix": "↳",           # line 模式的前缀
    "source_tag": "code",          # code | zh | off  （旧字段，保留兼容）
    "tag_mode": "source",          # source | target | arrow | off，入站译文前的标注
    "inbound_label": "",           # 空 = Lua 用默认的换行
    "system_names": ["SYSTEM", "System", "系统", "服务器", "SERVER"],
    "system_prefixes": [],
    "chat_log": False,
    "ime_guard": True,            # 游戏前台时把 IME 切到英文/字母模式
    "debug_peer": False,          # 调试：允许 @peer 命令走完整入站队列（仅测试）
    "mode": "mem",
    "prefix": "auto",
    "transport": "auto",
    "port": 8731,
    "api": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "key": "",
        "timeout": 20,
        "temperature": 0.2,
    },
    "glossary": [],
}


def _writable(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        t = p / ".write_test"
        t.write_text("x", encoding="utf-8")
        t.unlink()
        return True
    except OSError:
        return False


def home_dir() -> Path:
    # 允许便携/测试模式把数据放在指定目录（发布版默认仍用 %LOCALAPPDATA%）
    override = os.environ.get("HD2CT_DATA_DIR")
    if override:
        p = Path(override)
        p.mkdir(parents=True, exist_ok=True)
        return p
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    p = Path(base) / APP_NAME
    if _writable(p):
        return p
    # AppData 不可写时退回 exe 旁边的 data\（便携模式），避免“双击没反应”
    import paths
    fallback = paths.app_dir() / "data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


HOME = home_dir()
CONFIG_JSON = HOME / "console.json"
CONFIG_INI = HOME / "config.ini"
HISTORY_DB = HOME / "history.db"
LOG_DIR = HOME / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    cfg = deepcopy(DEFAULT_CONFIG)
    try:
        raw = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            cfg = _merge(cfg, raw)
    except (OSError, ValueError):
        pass
    # 端口/超时这类值来自手改 JSON 时要能纠正
    try:
        cfg["port"] = int(cfg.get("port") or 8731)
    except (TypeError, ValueError):
        cfg["port"] = 8731
    try:
        cfg["api"]["timeout"] = float(cfg["api"].get("timeout") or 20)
    except (TypeError, ValueError):
        cfg["api"]["timeout"] = 20
    return cfg


def save(cfg: dict) -> None:
    """原子写 console.json，再写 Lua 用的 config.ini。"""
    CONFIG_JSON.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_mod_ini(cfg)


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def write_mod_ini(cfg: dict) -> None:
    port = int(cfg.get("port") or 8731)
    names = "|".join(x for x in (cfg.get("system_names") or []) if x != "")
    prefixes = "|".join(x for x in (cfg.get("system_prefixes") or []) if x != "")
    lines = [
        "# HD2 Chat Translator - 由控制台自动生成，手改会被覆盖",
        f"read_language={cfg.get('read_language', 'zh-CN')}",
        f"send_language={cfg.get('send_language', 'en')}",
        f"inbound={'on' if cfg.get('inbound', True) else 'off'}",
        f"inbound_self={'1' if cfg.get('inbound_self', False) else '0'}",
        f"inbound_render={cfg.get('inbound_render', 'row')}",
        f"line_prefix={cfg.get('line_prefix', '↳')}",
        f"outbound={'on' if cfg.get('outbound', True) else 'off'}",
        f"source_tag={cfg.get('source_tag', 'code')}",
        f"inbound_label={cfg.get('inbound_label', '') or ''}",
        f"system_names={names}",
        f"system_prefixes={prefixes}",
        f"chat_log={'1' if cfg.get('chat_log', False) else '0'}",
        f"debug_peer={'1' if cfg.get('debug_peer', False) else '0'}",
        f"mode={cfg.get('mode', 'mem')}",
        f"prefix={cfg.get('prefix', 'auto')}",
        f"transport={cfg.get('transport', 'auto')}",
        f"api_base=http://127.0.0.1:{port}/v1",
        "api_key=local",
    ]
    _atomic_write(CONFIG_INI, "\n".join(lines) + "\n")


def tag_for(lang: str) -> str:
    return TAGS.get((lang or "").split("-")[0].lower(), (lang or "??").upper())


def label_for(lang: str) -> str:
    meta = LANGUAGES.get(lang)
    return meta[2] if meta else (lang or "?")


def english_name(lang: str) -> str:
    meta = LANGUAGES.get(lang)
    return meta[1] if meta else (lang or "English")
