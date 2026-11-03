# -*- coding: utf-8 -*-
"""完整链路实测:保存布局 → /api/state 是否带出 → 工作台能否渲染。"""
import json
import urllib.error
import urllib.request

B = "http://127.0.0.1:8890"


def get(p):
    return json.loads(urllib.request.urlopen(B + p, timeout=10).read().decode())


def post(p, o):
    r = urllib.request.Request(B + p, data=json.dumps(o).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    try:
        return json.loads(urllib.request.urlopen(r, timeout=20).read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "http": e.code, "body": e.read().decode("utf-8", "ignore")[:150]}


LAY = {"canvas": {"w": 900, "h": 600, "grid": 8},
       "name": "测试布局",
       "items": [
           {"type": "clock", "x": 40, "y": 40, "w": 300, "h": 120, "props": {"show": "both"}},
           {"type": "note", "x": 40, "y": 200, "w": 400, "h": 200, "props": {"text": "这是我保存的布局"}},
       ]}

print("① 保存:", post("/api/ui/layout", {"layout": LAY}))
s = get("/api/state")
ui = s.get("ui") or {}
print("② /api/state.ui.enabled =", ui.get("enabled"),
      "| 布局组件 =", [i["type"] for i in ((ui.get("layout") or {}).get("items") or [])])
print("③ /api/ui/schema 里的布局 =",
      [i["type"] for i in (get("/api/ui/schema")["layout"].get("items") or [])])
print("④ 前端文件是否都在:")
for f in ("/static/js/views/board.js", "/static/js/views/designer.js",
          "/static/js/ui/widgets.js", "/static/css/designer.css", "/static/img/logo.png"):
    try:
        r = urllib.request.urlopen(B + f, timeout=8)
        print("   %-32s HTTP %s  %d 字节" % (f, r.status, len(r.read())))
    except Exception as e:
        print("   %-32s 取不到:%s" % (f, e))
print("⑤ 首页 HTML 里有没有新视图:")
html = urllib.request.urlopen(B + "/", timeout=8).read().decode("utf-8", "ignore")
for k in ('id="view-board"', 'id="view-designer"', 'data-view="board"', 'data-view="designer"',
          "designer.css", "dgCanvas", "boardStage"):
    print("   %-22s %s" % (k, "✓" if k in html else "✗ 缺失"))
