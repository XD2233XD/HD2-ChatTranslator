"""控制台离线自测：不联网、不碰真实游戏，用本地 mock 端点验证协议与翻译逻辑。

运行：E:\\Python312\\python.exe tests\\test_console.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TMP = tempfile.mkdtemp(prefix="hd2ct-test-")
os.environ["LOCALAPPDATA"] = TMP
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import config_store as C  # noqa: E402
import store  # noqa: E402
import translator as T  # noqa: E402


class MockLLM(BaseHTTPRequestHandler):
    reply = {"lang": "en", "system": False, "translation": "前方有敌人，需要支援"}
    calls = []

    def log_message(self, *a):
        pass

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n).decode("utf-8"))
        MockLLM.calls.append(body)
        content = json.dumps(self.reply, ensure_ascii=False)
        out = json.dumps({
            "choices": [{"message": {"content": content}}],
        }, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def start_mock():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), MockLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class TranslatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = start_mock()
        cls.cfg = json.loads(json.dumps(C.DEFAULT_CONFIG))
        cls.cfg["api"].update({
            "base_url": "http://127.0.0.1:%d/v1" % cls.srv.server_address[1],
            "key": "test-key",
        })
        store.init()

    def setUp(self):
        MockLLM.reply = {"lang": "en", "system": False, "translation": "前方有敌人，需要支援"}
        MockLLM.calls.clear()

    def test_inbound_prefix_and_lang(self):
        tr = T.Translator(self.cfg)
        res = tr.translate("Bug breach at my position", "zh-CN", "in", "PlayerOne")
        self.assertTrue(res["ok"])
        self.assertFalse(res["skip"])
        self.assertEqual(res["content"], "[EN] 前方有敌人，需要支援")
        self.assertEqual(res["lang"], "en")

    def test_outbound_has_no_tag(self):
        MockLLM.reply = {"lang": "zh", "system": False, "translation": "前方有敌人，需要支援"}
        tr = T.Translator(self.cfg)
        res = tr.translate("前方有敌人", "en", "out", "Me")
        self.assertTrue(res["ok"])
        self.assertEqual(res["content"], "前方有敌人，需要支援")

    def test_tag_mode_target(self):
        cfg = json.loads(json.dumps(self.cfg))
        cfg["tag_mode"] = "target"
        res = T.Translator(cfg).translate("hello", "zh-CN", "in", "P")
        self.assertEqual(res["content"], "[CN] 前方有敌人，需要支援")

    def test_tag_mode_source(self):
        cfg = json.loads(json.dumps(self.cfg))
        cfg["tag_mode"] = "source"
        res = T.Translator(cfg).translate("hello", "zh-CN", "in", "P")
        self.assertEqual(res["content"], "[EN] 前方有敌人，需要支援")

    def test_tag_mode_arrow(self):
        cfg = json.loads(json.dumps(self.cfg))
        cfg["tag_mode"] = "arrow"
        res = T.Translator(cfg).translate("hello", "zh-CN", "in", "P")
        self.assertEqual(res["content"], "[EN→CN] 前方有敌人，需要支援")

    def test_same_language_skips(self):
        MockLLM.reply = {"lang": "zh", "system": False, "translation": ""}
        res = T.Translator(self.cfg).translate("前方有敌人", "zh-CN", "in", "P")
        self.assertTrue(res["ok"])
        self.assertTrue(res["skip"])
        self.assertEqual(res["content"], "__SKIP__")

    def test_system_flag_skips(self):
        MockLLM.reply = {"lang": "en", "system": True, "translation": "X joined"}
        res = T.Translator(self.cfg).translate("X joined the squad", "zh-CN", "in", "P")
        self.assertTrue(res["skip"])

    def test_cache_avoids_second_call(self):
        tr = T.Translator(self.cfg)
        a = tr.translate("Cache me please", "zh-CN", "in", "P")
        b = tr.translate("Cache me please", "zh-CN", "in", "P")
        self.assertTrue(b["cached"])
        self.assertEqual(len(MockLLM.calls), 1)
        self.assertEqual(a["content"], b["content"])

    def test_slang_exact_hit_is_instant(self):
        res = T.Translator(self.cfg).translate("sr", "zh-CN", "in", "P")
        self.assertTrue(res["ok"])
        self.assertFalse(res["skip"])
        self.assertEqual(res["content"], "[EN] 抱歉")
        self.assertEqual(res["lang"], "en")
        self.assertEqual(res["ms"], 0)
        self.assertTrue(res.get("fast"))
        self.assertEqual(len(MockLLM.calls), 0)

    def test_slang_case_and_punctuation(self):
        res = T.Translator(self.cfg).translate("LOL!!", "zh-CN", "in", "P")
        self.assertEqual(res["content"], "[EN] 哈哈")

    def test_slang_chinese_to_english(self):
        res = T.Translator(self.cfg).translate("666", "en", "out", "Me")
        self.assertEqual(res["content"], "awesome")
        self.assertEqual(res["lang"], "zh")

    def test_hd2_abbreviation_keeps_original(self):
        res = T.Translator(self.cfg).translate("RR", "zh-CN", "in", "P")
        self.assertEqual(res["content"], "[EN] 无后座力炮（RR）")
        self.assertTrue(res.get("fast"))

    def test_slang_same_language_skips(self):
        res = T.Translator(self.cfg).translate("lol", "en", "in", "P")
        self.assertTrue(res["skip"])

    def test_plain_text_fallback_when_json_missing(self):
        MockLLM.reply = None
        orig = MockLLM.do_POST

        def plain(self):
            n = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(n)
            content = "为了民主"
            out = json.dumps({"choices": [{"message": {"content": content}}]},
                             ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        MockLLM.do_POST = plain
        try:
            res = T.Translator(self.cfg).translate("For democracy", "zh-CN", "in", "P")
        finally:
            MockLLM.do_POST = orig
        self.assertTrue(res["ok"])
        self.assertIn("为了民主", res["content"])


class ConfigTests(unittest.TestCase):
    def test_ini_roundtrip(self):
        cfg = json.loads(json.dumps(C.DEFAULT_CONFIG))
        cfg["system_names"] = ["SYSTEM", "系统"]
        cfg["source_tag"] = "zh"
        C.save(cfg)
        text = C.CONFIG_INI.read_text(encoding="utf-8")
        self.assertIn("system_names=SYSTEM|系统", text)
        self.assertIn("source_tag=zh", text)
        self.assertIn("api_base=http://127.0.0.1:8731/v1", text)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = start_mock()
        cls.cfg = json.loads(json.dumps(C.DEFAULT_CONFIG))
        cls.cfg["port"] = 0
        cls.cfg["api"].update({
            "base_url": "http://127.0.0.1:%d/v1" % cls.srv.server_address[1],
            "key": "test-key",
        })
        import server
        cls.httpd = server.serve(cls.cfg, port=0)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.srv.shutdown()

    def _post(self, path, obj):
        import http.client
        from urllib.parse import urlsplit
        u = urlsplit(self.base)
        conn = http.client.HTTPConnection(u.hostname, u.port, timeout=10)
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        conn.close()
        return res.status, json.loads(data)

    def test_chat_completions_returns_openai_shape(self):
        MockLLM.reply = {"lang": "en", "system": False, "translation": "前方有敌人"}
        code, data = self._post("/v1/chat/completions", {
            "mod": "hd2ct", "kind": "in", "target": "zh-CN", "text": "enemy ahead", "name": "P",
        })
        self.assertEqual(code, 200, data)
        self.assertEqual(data["choices"][0]["message"]["content"], "[EN] 前方有敌人")

    def test_models_endpoint_for_helper_warmup(self):
        import http.client
        from urllib.parse import urlsplit
        u = urlsplit(self.base)
        conn = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
        conn.request("GET", "/v1/models")
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        self.assertIn("data", json.loads(res.read().decode("utf-8")))

    def test_ui_index_served(self):
        import urllib.request
        html = urllib.request.urlopen(self.base + "/", timeout=5).read().decode("utf-8")
        self.assertIn("Chat Translator", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)


