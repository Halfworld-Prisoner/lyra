# -*- coding: utf-8 -*-
"""给 server.py 加上自定义 UI 的接口。

  GET  /api/ui/schema        组件清单 + 当前布局 + 开关状态
  POST /api/ui/layout        保存布局(会过校验)
  POST /api/ui/layout/reset  恢复默认布局
  POST /api/ui/layout/import 导入布局(JSON 文本或对象)
  GET  /api/ui/layout/export 导出布局(纯 JSON,可另存为文件)
  POST /api/ui               开/关自定义界面、是否作为首屏
"""
import io
import subprocess

P = r"D:\Unity阅读器\webapp\server.py"
t = io.open(P, encoding="utf-8").read()

# ---------- ① import ----------
if "import uilayout" not in t:
    t = t.replace("from core import storyhook",
                  "from core import storyhook\nfrom core import uilayout", 1)
    print("① 已 import uilayout")

# ---------- ② 辅助 ----------
if "def _ui_cfg(" not in t:
    t = t.replace("def apply_translate_cfg():",
'''def _ui_cfg() -> dict:
    """自定义界面的配置块(布局 + 开关)。"""
    cfg = cfgm.get()
    ui = cfg.setdefault("ui", {})
    if not isinstance(ui.get("layout"), dict):
        ui["layout"] = uilayout.default_layout()      # 首次使用给一份默认布局
    ui.setdefault("enabled", True)
    ui.setdefault("home", False)
    return ui


def apply_translate_cfg():''', 1)
    print("② 已加 _ui_cfg")

# ---------- ③ 接口 ----------
if '"/api/ui/schema"' not in t:
    ROUTES = '''            if p == "/api/ui/schema":
                ui = _ui_cfg()
                return self._json({
                    "components": [dict(id=k, **{kk: vv for kk, vv in v.items()})
                                   for k, v in uilayout.COMPONENTS.items()],
                    "canvas": ui["layout"].get("canvas"),
                    "layout": ui["layout"],
                    "enabled": bool(ui.get("enabled", True)),
                    "home": bool(ui.get("home")),
                    "max_items": uilayout.MAX_ITEMS,
                })

            if p == "/api/ui/layout":
                ui = _ui_cfg()
                clean, notes = uilayout.validate(d.get("layout"))
                ui["layout"] = clean
                cfgm.save()
                msg = "布局已保存"
                if notes:
                    msg += "(" + ";".join(notes) + ")"
                add_log(msg, "info")
                return self._json({"ok": True, "msg": msg, "layout": clean})

            if p == "/api/ui/layout/reset":
                ui = _ui_cfg()
                ui["layout"] = uilayout.default_layout()
                cfgm.save()
                return self._json({"ok": True, "msg": "已恢复默认布局", "layout": ui["layout"]})

            if p == "/api/ui/layout/import":
                raw = d.get("json")
                if isinstance(raw, str) and raw.strip():
                    try:
                        obj = json.loads(raw)
                    except Exception as e:
                        return self._json({"ok": False, "msg": "这段 JSON 读不了:%s" % e})
                else:
                    obj = d.get("layout")
                clean, notes = uilayout.validate(obj)
                ui = _ui_cfg()
                ui["layout"] = clean
                cfgm.save()
                msg = "已导入布局(%d 个组件)" % len(clean["items"])
                if notes:
                    msg += "(" + ";".join(notes) + ")"
                add_log(msg, "info")
                return self._json({"ok": True, "msg": msg, "layout": clean})

            if p == "/api/ui/layout/export":
                ui = _ui_cfg()
                return self._json({"ok": True, "name": ui["layout"].get("name"),
                                   "json": uilayout.dumps(ui["layout"]),
                                   "layout": ui["layout"]})

            if p == "/api/ui":
                ui = _ui_cfg()
                if "enabled" in d:
                    ui["enabled"] = bool(d.get("enabled"))
                if "home" in d:
                    ui["home"] = bool(d.get("home"))
                if "name" in d:
                    ui["layout"]["name"] = str(d.get("name"))[:40]
                cfgm.save()
                return self._json({"ok": True, "enabled": ui["enabled"], "home": ui["home"],
                                   "name": ui["layout"].get("name")})

'''
    anchor = '            if p == "/api/rules":'
    assert anchor in t, "找不到插入点"
    t = t.replace(anchor, ROUTES + anchor, 1)
    print("③ 已加 6 个 /api/ui/* 接口")

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % P],
                   capture_output=True, text=True)
print("语法:", "通过" if r.returncode == 0 else (r.stderr or "")[:300])
