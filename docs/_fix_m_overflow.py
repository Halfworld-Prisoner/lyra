# -*- coding: utf-8 -*-
r"""修手机端横向溢出(内容被右侧切掉):
   html/body 禁止横向滚动、卡片允许换行、按钮手机上两个一行、字号收一点。"""
import io
import os
import shutil
import subprocess

SRC = r"D:\Unity阅读器\webapp\static\m.html"
APP = r"D:\Lyra\app\webapp\static\m.html"
t = io.open(SRC, encoding="utf-8").read()

FIX = """  /* ---- 修横向溢出(手机上内容被切) ---- */
  html,body{overflow-x:hidden;max-width:100%}
  .app{min-width:0;max-width:100vw}
  .main{min-width:0;max-width:100%}
  .card,.kv,.list div{min-width:0;overflow-wrap:anywhere;word-break:break-word}
  .now{overflow-wrap:anywhere}
  .nav button{min-width:0}
  @media (max-width:820px){
    .row .b{min-width:calc(50% - 5px);flex:1 1 calc(50% - 5px);padding:13px 8px;font-size:14px}
    .grid{grid-template-columns:repeat(auto-fit,minmax(126px,1fr))}
    .big{font-size:32px}
    .pinbox{font-size:34px}
    .main{padding:12px 12px 92px}
  }
"""

anchor = "  @media (min-width:821px){ .scrim{display:none} }"
if "修横向溢出" not in t and anchor in t:
    t = t.replace(anchor, anchor + "\n" + FIX, 1)
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(t)
    print("已加入溢出修复")
elif "修横向溢出" in t:
    print("已有修复")
else:
    print("!! 找不到锚点")

# 语法检查
js = t.split("<script>")[-1].split("</script>")[0]
tmp = os.path.join(os.path.dirname(SRC), "_chk.js")
io.open(tmp, "w", encoding="utf-8", newline="\n").write(js)
r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
os.remove(tmp)
print("内联脚本:", "通过" if r.returncode == 0 else r.stderr[:200])

shutil.copy2(SRC, APP)
print("已部署")
