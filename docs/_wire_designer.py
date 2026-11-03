# -*- coding: utf-8 -*-
"""接线:
   ① index.html:引入 designer.css、侧栏加「工作台」「UI 设计」、加两个视图区块;
   ② boot.js:视图标题表补两项、加载 designer/board 模块、首屏可设为工作台;
   ③ server.py:/api/state 里带出 ui(布局),工作台靠它渲染;
   ④ designer.js:拖动期间/无变化时不要重画(否则 400ms 刷新会打断拖拽)。
"""
import io
import os
import subprocess

SRC = r"D:\Unity阅读器"
STATIC = os.path.join(SRC, "webapp", "static")


def patch(path, pairs, must=True):
    t = io.open(path, encoding="utf-8").read()
    for old, new in pairs:
        if old in t:
            t = t.replace(old, new, 1)
            print("  OK   %-18s %s" % (os.path.basename(path), old.strip().split("\n")[0][:46]))
        elif must:
            print("  --   %-18s 未匹配: %s" % (os.path.basename(path), old.strip().split("\n")[0][:46]))
    io.open(path, "w", encoding="utf-8", newline="\n").write(t)


# ---------------- ① index.html ----------------
P = os.path.join(STATIC, "index.html")
patch(P, [
    ('<link rel="stylesheet" href="/static/css/splash.css">',
     '<link rel="stylesheet" href="/static/css/splash.css">\n'
     '<link rel="stylesheet" href="/static/css/designer.css">'),
    ('  <button class="nav-item" data-view="settings"><i>⚙</i><span>设置</span></button>',
     '  <button class="nav-item" data-view="board"><i>▣</i><span>工作台</span></button>\n'
     '  <button class="nav-item" data-view="designer"><i>✎</i><span>UI 设计</span></button>\n'
     '  <button class="nav-item" data-view="settings"><i>⚙</i><span>设置</span></button>'),
])

DESIGNER_VIEW = '''
    <!-- ---------------- 工作台(按自定义布局渲染) ---------------- -->
    <section class="view" id="view-board">
      <div class="panel">
        <div class="panel-title">工作台
          <span class="muted sm">这一页的内容由你在「UI 设计」里摆的组件决定</span>
          <span class="grow"></span>
          <button class="btn ghost sm" id="boardDesign">去设计</button>
        </div>
        <div class="board-wrap"><div class="board-stage" id="boardStage"></div></div>
      </div>
    </section>

    <!-- ---------------- UI 设计(拖拽式界面设计器) ---------------- -->
    <section class="view" id="view-designer">
      <div class="panel">
        <div class="panel-title">UI 设计
          <span class="muted sm">拖组件、拉大小、改选项 —— 做成你自己的界面</span>
          <span class="grow"></span>
          <span id="dgState" class="muted sm">已保存</span>
        </div>

        <div class="dg-bar">
          <input id="dgName" class="input" style="width:150px" placeholder="布局名字">
          <span class="muted sm">画布</span>
          <input id="dgW" type="number" class="input" title="画布宽"> ×
          <input id="dgH" type="number" class="input" title="画布高">
          <button class="btn sm" id="dgSave">保存布局</button>
          <button class="btn ghost sm" id="dgSnap">吸附网格</button>
          <button class="btn ghost sm" id="dgPreview">预览</button>
          <button class="btn ghost sm" id="dgHome">设为首页</button>
          <button class="btn ghost sm" id="dgExport">导出 JSON</button>
          <button class="btn ghost sm" id="dgImportBtn">导入 JSON</button>
          <button class="btn ghost sm" id="dgReset">恢复默认</button>
        </div>
        <div id="dgImport" class="dg-import hidden">
          <p class="muted sm">把别人分享的布局 JSON 粘进来(会先校验,不合法的组件会被忽略):</p>
          <textarea id="dgImportText" spellcheck="false" placeholder='{"version":1,"canvas":{...},"items":[...]}'></textarea>
          <div class="dg-row"><button class="btn sm" id="dgImportDo">导入</button></div>
        </div>

        <div class="dg-wrap">
          <div class="dg-panel">
            <div class="dg-ptitle">组件</div>
            <div class="dg-palette" id="dgPalette"></div>
            <p class="muted sm" style="margin-top:8px">点一下放进画布,或直接拖过去。</p>
          </div>
          <div class="dg-panel">
            <div class="dg-scroll" id="dgWrap"><div class="dg-canvas grid" id="dgCanvas"></div></div>
            <p class="muted sm" style="margin-top:8px">拖动移动 · 右下角拉动改大小 · Delete 删除 · 方向键微调(按住 Shift 步进 8px)</p>
          </div>
          <div class="dg-panel dg-side-right">
            <div class="dg-ptitle">属性</div>
            <div id="dgProps"></div>
          </div>
        </div>
      </div>
    </section>
'''
P = os.path.join(STATIC, "index.html")
t = io.open(P, encoding="utf-8").read()
anchor = '    <!-- ---------------- 角色配音 ---------------- -->'
if 'id="view-designer"' not in t:
    t = t.replace(anchor, DESIGNER_VIEW + "\n" + anchor, 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("  OK   index.html 已加两个视图区块")

# 工作台里的「去设计」按钮
patch(os.path.join(STATIC, "js", "boot.js"), [
    ("  library: '游戏库', realtime: '实时剧情', cast: '角色配音',",
     "  library: '游戏库', realtime: '实时剧情', cast: '角色配音',\n"
     "  board: '工作台', designer: 'UI 设计',"),
    ("/* 开机动画:固定流程",
     "/* 自定义界面:工作台(渲染自定义布局)+ UI 设计(拖拽设计器) */\n"
     "import('./views/board.js').catch(() => {});\n"
     "import('./views/designer.js').then((m) => m.renderDesigner()).catch(() => {});\n\n"
     "/* 开机动画:固定流程"),
])

# ---------------- ③ server.py:/api/state 带出 ui ----------------
patch(os.path.join(SRC, "webapp", "server.py"), [
    ('                    "settings": {',
     '                    "ui": dict(cfg.get("ui") or {}),        # 自定义布局(工作台用)\n'
     '                    "settings": {'),
])

# ---------------- ④ designer.js:拖动中不重画 ----------------
patch(os.path.join(STATIC, "js", "views", "designer.js"), [
    ("let snap = true;", "let snap = true;\nlet dragging = false;          // 拖动/拉大小期间不重画(否则会打断手感)\nlet _sig = '';                // 上一帧的布局签名"),
    ("    const start = { x: e.clientX, y: e.clientY, ix: it.x, iy: it.y };",
     "    dragging = true;\n    const start = { x: e.clientX, y: e.clientY, ix: it.x, iy: it.y };"),
    ("    const up = () => {\n      document.removeEventListener('mousemove', move);\n      document.removeEventListener('mouseup', up);\n      markDirty();\n    };",
     "    const up = () => {\n      document.removeEventListener('mousemove', move);\n      document.removeEventListener('mouseup', up);\n      dragging = false;\n      markDirty();\n    };"),
    ("    const start = { x: e.clientX, y: e.clientY, w: it.w, h: it.h };",
     "    dragging = true;\n    const start = { x: e.clientX, y: e.clientY, w: it.w, h: it.h };"),
])

# renderDesigner:只在没拖动、且布局真的变了时重画
P2 = os.path.join(STATIC, "js", "views", "designer.js")
t = io.open(P2, encoding="utf-8").read()
old = '''export async function renderDesigner() {
  if (!$('dgCanvas')) return;
  bind();
  if (!LAYOUT) {
    await load();
    applyZoom();
  } else if (!dirty) {
    /* 从别处回来时刷新一下"预览"组件里的实时数据 */
    drawCanvas();
  }
}'''
new = '''export async function renderDesigner() {
  if (!$('dgCanvas')) return;
  bind();
  if (!LAYOUT) {
    await load();
    applyZoom();
    return;
  }
  if (dragging) return;                       /* 正在拖:别插手 */
  /* 只在"后端布局变了"或"预览数据变了"时才重画,免得每 400ms 拆一次 DOM */
  const sig = JSON.stringify(LAYOUT) + '|' + ((store.S && store.S.lines) || []).length;
  if (sig === _sig) return;
  _sig = sig;
  drawCanvas();
  applyZoom();
}

registerRender(renderDesigner);

/* 工作台里的「去设计」 */
document.addEventListener('click', (e) => {
  if (e.target && e.target.id === 'boardDesign') {
    const b = document.querySelector('.nav-item[data-view="designer"]');
    if (b) b.click();
  }
});'''
assert old in t, "renderDesigner 没匹配"
t = t.replace(old, new, 1)
io.open(P2, "w", encoding="utf-8", newline="\n").write(t)
print("  OK   designer.js 已加节流 + 注册渲染")

for f in ("js/boot.js", "js/views/designer.js", "js/views/board.js", "js/ui/widgets.js"):
    r = subprocess.run(["node", "--check", os.path.join(STATIC, f.replace("/", os.sep))],
                       capture_output=True, text=True)
    print("   node --check %-26s %s" % (f, "通过" if r.returncode == 0 else r.stderr[:150]))
