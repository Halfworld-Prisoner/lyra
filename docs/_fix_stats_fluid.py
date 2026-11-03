# -*- coding: utf-8 -*-
r"""修统计页"用不满窗口"的问题(玩家:旁边一大片空白没用到):

   · 内容不再锁死 1180px → 宽度用满(只留一点点边距),4K / 宽屏也撑开
   · 宽屏自动分栏:上半区通栏,"最近 14 天"和"各游戏排行"并排
   · 让波浪条 / 圆盘随可用空间变大,纵向也别空一大截
   · 窄窗口(笔记本小屏 / 半屏)自动退回单列
"""
import io
import shutil

CSS = r"D:\Unity阅读器\webapp\static\css\extra.css"
c = io.open(CSS, encoding="utf-8").read()

BLOCK = '''

/* ================= 阅读统计:用满窗口 + 宽屏分栏 ================= */
.stats-overlay { padding: 14px clamp(10px, 2vw, 30px) 22px; }
.stats-overlay-inner {
  max-width: none !important;            /* ★不再锁 1180px,用满宽度★ */
  width: 100%;
  min-height: calc(100vh - 44px);
  align-content: start;
  grid-template-columns: 1fr;            /* 默认单列(窄窗口) */
  gap: 12px;
}
/* 宽屏:上两块通栏,后两块并排;图表也跟着变大 */
@media (min-width: 1080px) {
  .stats-overlay-inner { grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); }
  .stats-overlay-inner > *:nth-child(1),
  .stats-overlay-inner > *:nth-child(2) { grid-column: 1 / -1; }
}
/* 超宽屏(2K/4K):三块一起排,排行放右侧 */
@media (min-width: 1700px) {
  .stats-overlay-inner { grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr) minmax(0, .95fr); }
  .stats-overlay-inner > *:nth-child(1) { grid-column: 1 / -1; }
  .stats-overlay-inner > *:nth-child(2) { grid-column: 1 / -1; }
  .stats-overlay-inner > *:nth-child(3) { grid-column: 1 / 3; }
  .stats-overlay-inner > *:nth-child(4) { grid-column: 3 / 4; }
}
/* 图表随空间长大 */
.stats-hero { gap: clamp(16px, 2.5vw, 40px); }
.stats-hero-main { min-width: 260px; }
.stats-donut { width: clamp(150px, 13vw, 230px); height: clamp(150px, 13vw, 230px); }
.stats-wave { height: clamp(110px, 16vh, 220px); }
.stat-big b { font-size: clamp(38px, 3.6vw, 64px); }
@media (min-width: 1080px) {
  .stats-overlay .mini-stats { grid-template-columns: repeat(6, minmax(0, 1fr)); }
}
/* 让"最近 14 天"面板把纵向空当吃掉一点 */
.stats-overlay-inner > *:nth-child(3) { display: flex; flex-direction: column; }
.stats-overlay-inner > *:nth-child(3) .stats-wave { flex: 1; }
'''
if "用满窗口 + 宽屏分栏" not in c:
    c += BLOCK
    io.open(CSS, "w", encoding="utf-8", newline="\n").write(c)
    print("① 已追加自适应样式")
else:
    print("① 已有自适应样式")
shutil.copy2(CSS, r"D:\Lyra\app\webapp\static\css\extra.css")
print("② 已部署")
