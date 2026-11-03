# -*- coding: utf-8 -*-
"""修「API Key 被刷新覆盖」这一类 bug:

① core.js:加"脏值"保护(玩家碰过的输入框,保存成功前不许被重绘覆盖);
② settings_extra.js:AI 的 5 个输入框 + 3 个滑条接入保护,保存成功后解除;
③ translate.js:等待时间输入框接入保护;
④ core/ai.py:把 HTTP 错误分成"Key 不对 / 地址不对 / 限额 / 服务器错 / 网络不通",
   而不是笼统的"检查 Key/网络"。
"""
import io
import os

SRC = r"D:\Unity阅读器"
JS = os.path.join(SRC, "webapp", "static", "js")


def patch(path, pairs, must=True):
    t = io.open(path, encoding="utf-8").read()
    for old, new in pairs:
        if old in t:
            t = t.replace(old, new, 1)
            print("  OK   %-22s %s" % (os.path.basename(path), old.strip().split("\n")[0][:44]))
        elif must:
            print("  !!   %-22s 没找到: %s" % (os.path.basename(path), old.strip().split("\n")[0][:44]))
    io.open(path, "w", encoding="utf-8", newline="\n").write(t)


# ---------- ① core.js:脏值保护 ----------
core = os.path.join(JS, "core.js")
t = io.open(core, encoding="utf-8").read()
if "isDirty" not in t:
    t += '''

/* ---------------- 输入框"脏值"保护 ---------------- */
/* 设置页每 0.4 秒按状态重绘一次。玩家输完内容去点「保存」的那一瞬间,焦点已经离开
   输入框,重绘就会把刚输入的内容当成"过期值"覆盖掉 —— 实测把 API Key 覆盖成空,
   玩家以为保存了、其实存进去是空的,然后测试连接报"Key 不对"。
   规则:玩家碰过的输入框,在保存成功前不许被重绘覆盖。 */
const _dirtyEls = new WeakSet();

export function touchTrack(el) {
  if (el && !el.__lyTracked) {
    el.__lyTracked = 1;
    el.addEventListener('input', () => _dirtyEls.add(el));
    el.addEventListener('change', () => _dirtyEls.add(el));
  }
  return el;
}
export function isDirty(el) { return !!el && _dirtyEls.has(el); }
export function clearDirty(el) { if (el) _dirtyEls.delete(el); }
export function clearDirtyAll(els) { (els || []).forEach(clearDirty); }
'''
    io.open(core, "w", encoding="utf-8", newline="\n").write(t)
    print("  OK   core.js 已加 touchTrack / isDirty / clearDirty")
else:
    print("  --   core.js 已有保护")

# ---------- ② settings_extra.js ----------
patch(os.path.join(JS, "views", "settings_extra.js"), [
    ("import { $, esc, toast, get, post } from '../core.js';",
     "import { $, esc, toast, get, post, touchTrack, isDirty, clearDirtyAll } from '../core.js';"),
    # 滑条:正在拖的时候别覆盖
    ("  if ($('rate') && document.activeElement !== $('rate')) {",
     "  if ($('rate') && !isDirty($('rate')) && document.activeElement !== $('rate')) {"),
    ("  if ($('pitch') && document.activeElement !== $('pitch')) {",
     "  if ($('pitch') && !isDirty($('pitch')) && document.activeElement !== $('pitch')) {"),
    ("  if ($('volume') && document.activeElement !== $('volume')) {",
     "  if ($('volume') && !isDirty($('volume')) && document.activeElement !== $('volume')) {"),
    # AI 五个输入框:脏值优先
    ("  if (eps && document.activeElement !== eps) eps.value",
     "  if (eps && !isDirty(eps) && document.activeElement !== eps) eps.value"),
    ("  if (md && document.activeElement !== md) md.value",
     "  if (md && !isDirty(md) && document.activeElement !== md) md.value"),
    ("  if (key && document.activeElement !== key) key.value",
     "  if (key && !isDirty(key) && document.activeElement !== key) key.value"),
    ("  if (pin && document.activeElement !== pin) pin.value",
     "  if (pin && !isDirty(pin) && document.activeElement !== pin) pin.value"),
    ("  if (pout && document.activeElement !== pout) pout.value",
     "  if (pout && !isDirty(pout) && document.activeElement !== pout) pout.value"),
    # 保存:提交后解除脏标记;失败时保留(内容还在,玩家可重试)
    ("""$('aiSave').onclick = async () => {
  const ep = ($('aiEndpoint').value || '').trim() || 'https://api.deepseek.com/v1/chat/completions';
  await post('/api/settings', {""",
     """$('aiSave').onclick = async () => {
  const ep = ($('aiEndpoint').value || '').trim() || 'https://api.deepseek.com/v1/chat/completions';
  const r = await post('/api/settings', {"""),
    ("""  toast('AI 设置已保存');
  refresh();
};""",
     """  if (r && r.ok === false) {
    toast('保存失败:' + (r.msg || r.error || '后端没接受'));
    return;                      /* 保留脏标记,内容不会被刷新清掉 */
  }
  clearDirtyAll([$('aiEndpoint'), $('aiModel'), $('aiKey'), $('aiPriceIn'), $('aiPriceOut')]);
  clearDirtyAll([$('rate'), $('pitch'), $('volume')]);
  const k = ($('aiKey').value || '').trim();
  toast(k ? 'AI 设置已保存(Key 长度 ' + k.length + ')' : '已保存,但 API Key 是空的');
  refresh();
};"""),
    # 测试失败时把后端那句人话直接显示出来
    ("  st.textContent = r.ok ? ('连接正常 ✓ ' + (r.msg || '')) : ('连接失败:' + (r.msg || ''));\n  toast(r.ok ? 'AI 连接正常' : '连接失败,检查 Key/网络');",
     "  st.textContent = r.ok ? ('连接正常 ✓ ' + (r.msg || '')) : ('连接失败:' + (r.msg || ''));\n  toast(r.ok ? 'AI 连接正常' : ('连接失败:' + (r.msg || '原因不详')));"),
])

# ---------- ③ translate.js ----------
patch(os.path.join(JS, "views", "translate.js"), [
    ("import { $, $$, esc, toast, get, post, lsRow } from '../core.js';",
     "import { $, $$, esc, toast, get, post, lsRow, isDirty, clearDirty } from '../core.js';"),
    ("  if (document.activeElement !== $('trWait')) $('trWait').value = Number(d.wait);",
     "  if (!isDirty($('trWait')) && document.activeElement !== $('trWait')) $('trWait').value = Number(d.wait);"),
], must=False)

# ---------- ④ core/ai.py:错误分类 ----------
patch(os.path.join(SRC, "core", "ai.py"), [
    ("""    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "ignore")[:200]
        except Exception:
            pass
        raise RuntimeError(f"AI 接口返回 {e.code}: {detail or e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"连不上 AI 接口: {e.reason}")""",
     """    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "ignore")[:200]
        except Exception:
            pass
        code = e.code
        if code in (401, 403):
            hint = "API Key 不对或没有权限 —— 请重新复制一次 Key(注意别带上空格),确认它属于这个接口"
        elif code == 404:
            hint = "接口地址不对 —— 地址要以 /v1/chat/completions 结尾(不是 /v1 或网页地址)"
        elif code == 429:
            hint = "调用太频繁或额度用完 —— 等一会儿再试,或去官网看余额"
        elif 500 <= code < 600:
            hint = "对方服务器暂时出错 —— 过几分钟再试"
        elif code == 400:
            hint = "请求被拒绝 —— 多半是模型名写错了(例如应为 deepseek-chat)"
        else:
            hint = "接口拒绝了这次请求"
        raise RuntimeError(f"{hint}(HTTP {code}{':' + detail if detail else ''})")
    except urllib.error.URLError as e:
        reason = str(getattr(e, "reason", e))
        if "timed out" in reason.lower() or "timeout" in reason.lower():
            raise RuntimeError("连接超时 —— 检查网络,或这台机器是否需要开代理才能访问 AI 接口")
        raise RuntimeError(f"连不上 AI 接口 —— 检查网络或代理设置({reason})")"""),
])
print("完成")
