"""离线验证：从 Lua 里抽出内嵌的 node 助手，跑通 job.json -> out.txt 的本地 http 链路。

不需要游戏，也不需要真实 API：mock 端点返回一个 OpenAI 形状的响应。
运行：E:\\Python312\\python.exe tests\\test_helper_transport.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LUA = os.path.join(HERE, "..", "mod", "src", "chat_translator.lua")


class Mock(BaseHTTPRequestHandler):
    hits = []

    def log_message(self, *a):
        pass

    def do_GET(self):  # noqa: N802
        Mock.hits.append(("GET", self.path))
        out = b'{"data":[{"id":"mock"}]}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        Mock.hits.append(("POST", self.path, self.rfile.read(n).decode("utf-8")))
        content = json.dumps({"lang": "en", "system": False, "translation": "收到"})
        out = json.dumps({"choices": [{"message": {"content": content}}]},
                         ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def extract_helper() -> str:
    src = open(LUA, encoding="utf-8").read()
    m = re.search(r"local HELPER_JS = \[==\[(.*?)\]==\]", src, re.S)
    if not m:
        raise AssertionError("HELPER_JS not found")
    return m.group(1)


class HelperTransportTest(unittest.TestCase):
    def test_helper_speaks_http_and_returns_body(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not on PATH")
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port = srv.server_address[1]

        tmp = tempfile.mkdtemp(prefix="hd2ct-helper-")
        js = os.path.join(tmp, "helper.js")
        open(js, "w", encoding="utf-8").write(extract_helper())
        open(os.path.join(tmp, "helper.cfg"), "w", encoding="utf-8").write(
            f"url=http://127.0.0.1:{port}/v1\ntoken=local\nidle=20000\nwarm=0\n"
        )
        proc = subprocess.Popen([node, js, tmp], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        try:
            ready = os.path.join(tmp, "helper.ready")
            for _ in range(60):
                if os.path.exists(ready):
                    break
                time.sleep(0.1)
            self.assertTrue(os.path.exists(ready), "helper.ready not written")

            job = {"id": "test-1", "body": json.dumps(
                {"mod": "hd2ct", "kind": "in", "target": "zh-CN", "text": "hello", "name": "P"},
                ensure_ascii=False)}
            open(os.path.join(tmp, "job.tmp"), "w", encoding="utf-8").write(
                json.dumps(job, ensure_ascii=False))
            os.replace(os.path.join(tmp, "job.tmp"), os.path.join(tmp, "job.json"))

            out = ""
            for _ in range(80):
                try:
                    out = open(os.path.join(tmp, "out.txt"), encoding="utf-8").read()
                except OSError:
                    out = ""
                if "id=test-1" in out:
                    break
                time.sleep(0.1)
            self.assertIn("id=test-1", out, "helper never answered: " + out)
            self.assertIn("ok=1", out, out)
            raw = open(os.path.join(tmp, "raw.txt"), encoding="utf-8").read()
            outer = json.loads(raw)
            inner = json.loads(outer["choices"][0]["message"]["content"])
            self.assertEqual(inner["translation"], "收到")
            self.assertTrue(any(h[0] == "POST" for h in Mock.hits))
        finally:
            proc.kill()
            srv.shutdown()


if __name__ == "__main__":
    unittest.main(verbosity=2)
