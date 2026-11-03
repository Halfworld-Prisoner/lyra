# -*- coding: utf-8 -*-
r"""新增:检测到"选择/卡牌界面"时暂停自动点击(玩家自己选)。

思路(不需要游戏配合):
  正常的剧情是一句一句来的;而选项/卡牌画面会在**几秒内连着吐出好几条短句**
  (而且没有台词引号)。据此判定"在选择界面":
    · 4 秒内出现 ≥3 条不同的短句(≤24 字、不带「」引号)
    · → 记下时刻,并在 25 秒内让自动点击停手(玩家自己点)
    · 期间状态栏/日志会给一句提示,玩家知道为什么没自动走

  注意:只在"本来就该朗读的行"里统计,界面文字/被丢弃的行不参与,免得菜单误触发。
"""
import io
import re
import subprocess

SH = r"D:\Unity阅读器\core\storyhook.py"
SV = r"D:\Unity阅读器\webapp\server.py"

t = io.open(SH, encoding="utf-8").read()

# ---------- ① 常量 ----------
if "CHOICE_HOLD" not in t:
    t = t.replace('MENU_SWALLOW = 1.5     # 紧挨着菜单文字出现的其它文字也不读(槽位缩略里的台词)',
'''MENU_SWALLOW = 1.5     # 紧挨着菜单文字出现的其它文字也不读(槽位缩略里的台词)

# 选择/卡牌界面:几秒内连着来好几条短句 → 认为玩家正在选项画面,自动点击先停手
CHOICE_HOLD = 25.0     # 检测到之后,暂停自动点击这么久(秒)
CHOICE_WINDOW = 4.0    # 统计窗口:多少秒内的短句算"连着来"
CHOICE_MIN = 3         # 至少几条不同的短句才判定为选项画面''', 1)
    print("① 常量已加")

# ---------- ② __init__ 里的状态 ----------
m = re.search(r"(\n        self\.menu_t = 0\.0[^\n]*)", t)
if m and "self.choice_t" not in t:
    t = t[:m.end()] + "\n        self.choice_t = 0.0                  # 检测到选择/卡牌界面的时刻" \
                      "\n        self._short_hist = []                # 最近的短句(判定选项画面用)" + t[m.end():]
    print("② 状态已加")
elif "self.choice_t" not in t:
    # 兜底:挂在 filtered 计数旁边
    t = t.replace("        self.filtered = 0", "        self.filtered = 0\n        self.choice_t = 0.0\n        self._short_hist = []", 1)
    print("② 状态已加(兜底位置)")

# ---------- ③ 判定函数(放在 menu_active 后面)----------
if "def choice_active" not in t:
    t = t.replace('''    def menu_active(self) -> bool:
        """现在是不是在存档/读档这类菜单界面里(自动点击据此停手)。"""
        return bool(self.menu_t) and (time.time() - self.menu_t) < MENU_HOLD''',
'''    def menu_active(self) -> bool:
        """现在是不是在存档/读档这类菜单界面里(自动点击据此停手)。"""
        return bool(self.menu_t) and (time.time() - self.menu_t) < MENU_HOLD

    def note_short_line(self, text: str):
        """每读一句都过一下:几秒内连着好几条短句 → 多半是选项/卡牌画面。

        判据故意保守(短 + 无引号 + 条数够),宁可漏判:漏判只是没暂停,
        误判会让自动点击白停 25 秒。
        """
        s = (text or "").strip()
        if not s or len(s) > 24:
            return
        if any(ch in s for ch in "「」『』“”"):
            return                                  # 带引号的是台词
        if len(s) < 3:
            return
        now = time.time()
        self._short_hist.append((now, s))
        self._short_hist = self._short_hist[-12:]
        uniq = {x for ts, x in self._short_hist if now - ts <= CHOICE_WINDOW}
        if len(uniq) >= CHOICE_MIN:
            first = not self.choice_active()
            self.choice_t = now
            if first:
                try:
                    self.on_status("看到选择/卡牌了:自动点击先停 %d 秒,你自己点" % int(CHOICE_HOLD))
                except Exception:
                    pass

    def choice_active(self) -> bool:
        """现在是不是(可能)在选项/卡牌界面里。"""
        return bool(self.choice_t) and (time.time() - self.choice_t) < CHOICE_HOLD''', 1)
    print("③ 判定函数已加")

# ---------- ④ 在读到的句子上调用 ----------
if "note_short_line(" not in t.split("def note_short_line")[-1]:
    m2 = re.search(r"\n    def commit\(self[^\n]*\n", t)
    if m2:
        # 在 commit 的第一个 return 之前插入调用
        seg_start = m2.end()
        seg_end = t.find("\n    def ", seg_start)
        seg = t[seg_start:seg_end]
        ret = re.search(r"\n(\s*)return ", seg)
        if ret:
            ins = "\n%s    self.note_short_line(local_text if 'local_text' in dir() else text)" % ret.group(1)[:-4]
            # 更保险:用 commit 里确实存在的变量名
            ins = "\n%s    try:\n%s        self.note_short_line(text)\n%s    except Exception:\n%s        pass" % (
                ret.group(1)[:-4], ret.group(1)[:-4] + "    ", ret.group(1)[:-4], ret.group(1)[:-4] + "    ")
            seg2 = seg[:ret.start()] + ins + seg[ret.start():]
            t = t[:seg_start] + seg2 + t[seg_end:]
            print("④ 已在 commit() 里挂钩(第一处 return 之前)")
        else:
            print("④ !! commit 里没找到 return,需人工挂")
    else:
        print("④ !! 没找到 commit()")
else:
    print("④ 已挂过")

io.open(SH, "w", encoding="utf-8", newline="\n").write(t)

# ---------- ⑤ server.py:三处自动点击闸门加上选择判定 ----------
s = io.open(SV, encoding="utf-8").read()
n = 0
for old, new in (
    ("    if HOOK.filter.menu_active():\n        return",
     "    if HOOK.filter.menu_active() or HOOK.filter.choice_active():\n        return"),
    ('                    "menu_active": HOOK.filter.menu_active(),',
     '                    "menu_active": HOOK.filter.menu_active(),\n'
     '                    "choice_active": HOOK.filter.choice_active(),'),
):
    c = s.count(old)
    if c:
        s = s.replace(old, new)
        n += c
        print("⑤ 替换 %d 处:%s" % (c, old.strip().split("\n")[0][:52]))
io.open(SV, "w", encoding="utf-8", newline="\n").write(s)

for f in (SH, SV):
    r = subprocess.run(["python", "-c", "import py_compile;py_compile.compile(r'%s',doraise=True)" % f],
                       capture_output=True, text=True)
    print("   语法 %-16s %s" % (f.split("\\")[-1], "通过" if r.returncode == 0 else (r.stderr or "")[:220]))
