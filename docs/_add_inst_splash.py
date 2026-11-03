# -*- coding: utf-8 -*-
"""给安装程序 / 卸载程序的网页界面加一个轻量开场动画(与应用同源:天琴座 + Logo)。

注意:这两个页面是 **NavigateToString 内嵌**渲染的,外部 CSS/JS 一律加载不到,
     所以样式与脚本必须**内联**写进 HTML 里。
"""
import io
import os

INST = r"D:\Unity阅读器\installer"

SPLASH_CSS = '''
  /* ---------- 开场动画:天琴座星座 + Logo(与应用同款,轻量内联版) ---------- */
  #sp { position: fixed; inset: 0; z-index: 99; display: grid; place-items: center;
        background: radial-gradient(120% 100% at 50% 0%, #ffffff, #eef1f8 60%);
        transition: opacity .45s ease, visibility .45s ease; }
  #sp.out { opacity: 0; visibility: hidden; }
  #sp .cst { position: absolute; top: 50%; left: 50%; width: 430px; height: 280px;
        transform: translate(-50%, -178px); opacity: .42; pointer-events: none; }
  #sp .cst line { stroke: #7c5cff; stroke-width: 1.1; stroke-linecap: round;
        stroke-dasharray: 220; stroke-dashoffset: 220; animation: spDraw 1.1s ease-out forwards; }
  #sp .cst line:nth-child(2) { animation-delay: .12s }
  #sp .cst line:nth-child(3) { animation-delay: .24s }
  #sp .cst line:nth-child(4) { animation-delay: .36s }
  #sp .cst line:nth-child(5) { animation-delay: .48s }
  #sp .cst circle { fill: #4aa8ff; opacity: 0; animation: spStar 1.1s ease-out forwards; }
  #sp .cst circle.vega { fill: #7c5cff; filter: drop-shadow(0 0 8px rgba(124,92,255,.6)); animation-delay: .5s }
  #sp .cst circle:nth-of-type(2) { animation-delay: .58s }
  #sp .cst circle:nth-of-type(3) { animation-delay: .66s }
  #sp .cst circle:nth-of-type(4) { animation-delay: .74s }
  #sp .cst circle:nth-of-type(5) { animation-delay: .82s }
  @keyframes spDraw { to { stroke-dashoffset: 0 } }
  @keyframes spStar { 0% { opacity: 0; transform: scale(.4) } 60% { opacity: 1; transform: scale(1.5) } 100% { opacity: .95; transform: scale(1) } }
  #sp .box { display: grid; justify-items: center; gap: 16px; }
  #sp .big { width: 120px; height: 120px; border-radius: 30px; overflow: hidden; background: #fff;
        box-shadow: 0 18px 44px rgba(26,31,43,.22), 0 0 0 1px #e3e6ef;
        opacity: 0; transform: perspective(700px) rotateY(-22deg) scale(.84);
        animation: spIn .95s cubic-bezier(.2,.9,.25,1) .45s forwards, spSway 5.5s ease-in-out 1.5s infinite; }
  #sp .big img { width: 100%; height: 100%; object-fit: cover; display: block; }
  #sp .big::after { content: ''; position: absolute; }
  @keyframes spIn { to { opacity: 1; transform: perspective(700px) rotateY(0) scale(1) } }
  @keyframes spSway { 0%,100% { transform: perspective(700px) rotateY(-5deg) translateY(0) } 50% { transform: perspective(700px) rotateY(5deg) translateY(-5px) } }
  #sp .t { display: flex; gap: 3px; font-size: 34px; font-weight: 700; letter-spacing: .06em; color: #1a1f2b; }
  #sp .t span { opacity: 0; transform: translateY(16px); animation: spLet .6s cubic-bezier(.2,.9,.25,1) forwards; }
  #sp .t span:nth-child(1) { animation-delay: .85s }
  #sp .t span:nth-child(2) { animation-delay: .93s }
  #sp .t span:nth-child(3) { animation-delay: 1.01s }
  #sp .t span:nth-child(4) { animation-delay: 1.09s }
  #sp .t span:nth-child(5) { animation-delay: 1.17s }
  @keyframes spLet { to { opacity: 1; transform: none } }
  #sp .s { font-size: 12.5px; color: #687084; opacity: 0; animation: spFade .7s ease 1.2s forwards; }
  #sp .bar { width: 170px; height: 3px; border-radius: 99px; background: #e4e7f0; overflow: hidden; }
  #sp .bar i { display: block; height: 100%; width: 0; border-radius: 99px;
        background: linear-gradient(90deg, #7c5cff, #4aa8ff); animation: spLoad 1.5s cubic-bezier(.4,.1,.2,1) .3s forwards; }
  @keyframes spLoad { to { width: 100% } }
  @keyframes spFade { to { opacity: 1 } }
  @media (prefers-reduced-motion: reduce) {
    #sp .cst line, #sp .cst circle, #sp .big, #sp .t span, #sp .bar i { animation: none !important; opacity: 1 !important; }
    #sp .big { transform: none } #sp .bar i { width: 100% }
  }
'''

SPLASH_HTML = '''
<div id="sp" role="presentation">
  <svg class="cst" viewBox="0 0 460 300" aria-hidden="true">
    <line x1="300" y1="40" x2="238" y2="92"></line>
    <line x1="238" y1="92" x2="140" y2="118"></line>
    <line x1="140" y1="118" x2="92" y2="206"></line>
    <line x1="92" y1="206" x2="186" y2="238"></line>
    <line x1="186" y1="238" x2="238" y2="92"></line>
    <circle class="vega" cx="300" cy="40" r="4.6"></circle>
    <circle cx="238" cy="92" r="2.8"></circle>
    <circle cx="140" cy="118" r="2.8"></circle>
    <circle cx="92" cy="206" r="2.8"></circle>
    <circle cx="186" cy="238" r="2.8"></circle>
  </svg>
  <div class="box">
    <div class="big"><img id="spLogo" alt=""></div>
    <div class="t"><span>L</span><span>y</span><span>r</span><span>a</span></div>
    <div class="s" id="spSub">正在准备界面…</div>
    <div class="bar"><i></i></div>
  </div>
</div>
<script>
  (function () {
    var sp = document.getElementById('sp');
    if (!sp) return;
    var id = setTimeout(function () { sp.classList.add('out'); }, 1750);
    sp.addEventListener('click', function () { clearTimeout(id); sp.classList.add('out'); });
  })();
</script>
'''

for fn in ("ui.html", "ui_uninstall.html"):
    p = os.path.join(INST, fn)
    t = io.open(p, encoding="utf-8").read()
    if 'id="sp"' in t:
        print("  --  %s 已有开场动画" % fn)
        continue
    # 样式插到 </style> 前
    t = t.replace("</style>", SPLASH_CSS + "</style>", 1)
    # markup 插到 <body> 后
    t = t.replace("<body>", "<body>\n" + SPLASH_HTML, 1)
    # logo 数据由原有的 __lyra.src() 注入,这里让开场动画的图也跟着设置
    t = t.replace("src(u) { const i = document.getElementById('logo'); if (i && u) i.src = u; },",
                  "src(u) { const i = document.getElementById('logo'); if (i && u) i.src = u;\n"
                  "             const b = document.getElementById('spLogo'); if (b && u) b.src = u; },")
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("  OK  %s 已加开场动画" % fn)
