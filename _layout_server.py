# -*- coding: utf-8 -*-
"""布局编辑器的本地小服务。

做两件事：
1. 把工程目录当静态站发出去（这样编辑器能直接 fetch 到 _layout.json）
2. 收 POST /save，把 Ronny 在编辑器里调好的布局写回 _layout.json

用法：
    python _layout_server.py
然后浏览器开 http://127.0.0.1:8777/layout_editor.html
按 Ctrl+C 停。

⚠️ 只监听 127.0.0.1，不对外网开放。
"""
import http.server
import json
import os
import socketserver
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
LAYOUT = os.path.join(ROOT, "_layout.json")
BACKUP = os.path.join(ROOT, "_layout_prev.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8777


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        # 关掉缓存，编辑器每次都能拿到最新的 _layout.json
        if self.path.endswith(".json") or self.path.endswith(".html"):
            self.send_response(200)
            p = os.path.join(ROOT, self.path.lstrip("/").split("?")[0] or "layout_editor.html")
            if not os.path.isfile(p):
                self.send_error(404)
                return
            ctype = "application/json; charset=utf-8" if p.endswith(".json") else "text/html; charset=utf-8"
            with open(p, "rb") as f:
                data = f.read()
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/save":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", "0"))
        try:
            data = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception as e:
            self._json({"ok": False, "err": "JSON 解析失败: %s" % e})
            return

        # 合法性检查：宁可拒绝，也不要写一份把场景弄坏的布局
        for k in ("poles", "lamps", "trees", "grass", "cars"):
            if not isinstance(data.get(k), list):
                self._json({"ok": False, "err": "缺字段或类型不对: %s" % k})
                return
        for t in data["trees"]:
            if not isinstance(t.get("x"), (int, float)) or not isinstance(t.get("y"), (int, float)):
                self._json({"ok": False, "err": "树的 x/y 必须是数字"})
                return

        if os.path.isfile(LAYOUT):
            try:
                with open(LAYOUT, encoding="utf-8") as f, open(BACKUP, "w", encoding="utf-8") as g:
                    g.write(f.read())
            except Exception:
                pass
        with open(LAYOUT, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)

        cnt = "杆%d 灯%d 树%d 草%d 车%d" % (
            len(data["poles"]), len(data["lamps"]), len(data["trees"]),
            len(data["grass"]), len(data["cars"]))
        print("[SAVE] %s  %s" % (LAYOUT, cnt))
        self._json({"ok": True, "path": LAYOUT, "counts": cnt})

    def log_message(self, fmt, *args):
        if "/save" in (args[0] if args else ""):
            return
        sys.stderr.write("  %s\n" % (fmt % args))


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), H) as srv:
    print("布局编辑器: http://127.0.0.1:%d/layout_editor.html" % PORT)
    print("布局文件  : %s" % LAYOUT)
    print("Ctrl+C 停止")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n停。")
