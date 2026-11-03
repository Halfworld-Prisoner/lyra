# -*- coding: utf-8 -*-
'''点不到 的根治:鼠标按着的时候不重建任何页面 DOM。'''
import io

p = r'D:\Unity阅读器\webapp\static\js\core.js'
t = io.open(p, encoding='utf-8').read()
if '__LY_DOWN' not in t:
    add = '''
/* ---------------- 鼠标按下期间禁止重建 DOM ---------------- */
/* 刷新每 0.4 秒一次;如果重建正好夹在 mousedown 与 mouseup 中间,
   click 就不会触发(两个事件落在不同元素上)——表现就是"点不到 / 下拉框被掀掉"。 */
window.__LY_DOWN = 0;
window.addEventListener('pointerdown', () => { window.__LY_DOWN = 1; }, true);
window.addEventListener('pointerup', () => { window.__LY_DOWN = 0; }, true);
window.addEventListener('pointercancel', () => { window.__LY_DOWN = 0; }, true);
window.addEventListener('blur', () => { window.__LY_DOWN = 0; }, true);
'''
    io.open(p, 'w', encoding='utf-8', newline='\n').write(t + add)
    print('core.js 已加鼠标按下标记')
else:
    print('core.js 已有标记')

p2 = r'D:\Unity阅读器\webapp\static\js\state.js'
s = io.open(p2, encoding='utf-8').read()
old = '  store.renderers.forEach((fn) => {'
new = ('  /* 鼠标按着的时候(pointerdown -> pointerup)一律不重建 DOM:\n'
       '     否则重建会夹在按下与抬起之间,click 直接丢失 —— 玩家会感觉点不到。 */\n'
       '  if (window.__LY_DOWN) return;\n'
       '  store.renderers.forEach((fn) => {')
if '__LY_DOWN' not in s:
    s = s.replace(old, new, 1)
    io.open(p2, 'w', encoding='utf-8', newline='\n').write(s)
    print('state.js 已加"按下时不渲染"')
else:
    print('state.js 已有该判断')
