# -*- coding: utf-8 -*-
"""让「预览」更符合直觉:先保存当前设计,再跳到工作台。
   以前:设计完直接点预览 → 工作台显示的是**上一次保存**的布局,看起来像"没反应/没布局"。
   另外按钮文案改成「保存并预览」,并给保存加一个明显的 toast。"""
import io
import subprocess

STATIC = r"D:\Unity阅读器\webapp\static"

p = os.path.join(STATIC, "js", "views", "designer.js")
t = io.open(p, encoding="utf-8").read()
old = "  on('dgPreview', () => goView('board'));"
new = """  on('dgPreview', async () => {
    await save();                 /* 先保存,免得预览看到的是旧布局 */
    goView('board');
    toast('已保存,这是工作台的效果(不满意随时回「UI 设计」继续改)');
  });"""
assert old in t, "没找到 dgPreview 绑定"
t = t.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(t)
print("  designer.js:预览 = 先保存再跳转")

p2 = os.path.join(STATIC, "index.html")
h = io.open(p2, encoding="utf-8").read()
if 'id="dgPreview">预览<' in h:
    h = h.replace('id="dgPreview">预览<', 'id="dgPreview">保存并预览<', 1)
    io.open(p2, "w", encoding="utf-8", newline="\n").write(h)
    print("  index.html:按钮改名为「保存并预览」")

for f in ("js/views/designer.js",):
    r = subprocess.run(["node", "--check", os.path.join(STATIC, f.replace("/", os.sep))],
                       capture_output=True, text=True)
    print("  node --check %s -> %s" % (f, "通过" if r.returncode == 0 else r.stderr[:150]))
