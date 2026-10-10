/* state.js —— 全局状态与刷新循环
   S 里的东西全部来自 /api/state。各页面模块通过 registerRender() 注册自己的渲染函数,
   刷新时统一按注册顺序调用 —— 所以以后加一个页面,只要新建一个 views/xxx.js 并注册,
   不用回来改这个文件。 */
import { $, esc, get, post, toast, applyTheme, setStatusText } from './core.js';
import { pushSpark, drawSpark, sparkRate, sparkMem, setWaveAmp } from './ui/charts.js';

/* ---------------- 全局状态 ---------------- */
export const store = {
  S: { settings: {}, game_info: null, voices: [], games: [], metrics: {} },
  view: 'library',
  renderers: [],
};
export let scanData = { steam: [], desktop: [] };
export function setScanData(d) { scanData = d; }
export function setView(v) { store.view = v; }
/* 调试出口:出问题时可以在控制台/自动化脚本里看状态(也方便我自己排查) */
window.__LY = store;
/* 各页面模块在加载时注册渲染函数(可以重复调用,去重) */
export function registerRender(fn) {
  if (typeof fn === 'function' && store.renderers.indexOf(fn) < 0) store.renderers.push(fn);
}

export async function refresh() {
  try { await refreshInner(); }
  catch (e) { window.__JSERR = String((e && e.message) || e); console.error(e); }
}

async function refreshInner() {
  let st;
  try { st = await get('/api/state'); }
  catch (e) { setStatusText('连不上服务', 'err'); return; }
  store.S = st;
  /* 首次拿到数据 → 通知开机动画可以收尾了(见 js/splash.js) */
  if (document.body.dataset.stateReady !== '1') {
    document.body.dataset.stateReady = '1';
    if (typeof document.body.classList !== 'undefined') document.body.classList.add('ready');
  }
  const cfg = st.settings || {};
  const m = st.metrics || {};

  /* 顶栏状态 */
  setStatusText(st.status || '就绪');

  /* 侧栏内存仪表 */
  const mem = Number(m.mem_mb || 0);
  $('sideMem').textContent = mem ? mem + ' MB' : '—';
  $('sideMemBar').style.width = Math.min(100, mem / 8) + '%';

  /* 底栏 */
  const running = (st.running || {}).active;
  const busy = running || /识别|读取|朗读|安装|复制|扫描|LDC/.test(st.status || '');
  $('bbRate').textContent = m.rate ? m.rate + ' 字/秒' : '—';
  $('bbMem').textContent = mem ? mem + ' MB' : '—';
  $('bbCount').textContent = m.count != null ? m.count : (st.count || 0);
  $('waveLabel').textContent = running ? '忙碌中' : '空闲';
  $('waveLabel').style.color = running ? 'var(--c-mono)' : '';
  setWaveAmp(busy ? 0.95 : 0.22);

  /* 实时剧情页的指标卡(这页永远是可见的,放这里省一次注册) */
  $('mRate').textContent = m.rate ? m.rate : '—';
  $('mMem').textContent = mem ? mem : '—';
  $('mCount').textContent = m.count != null ? m.count : (st.count || 0);
  const avg = sparkRate.length ? (sparkRate.reduce((a, b) => a + b, 0) / sparkRate.length) : 0;
  $('mAvg').textContent = avg ? avg.toFixed(1) + ' 字/秒' : '—';
  const mine = (store.S.games || []).find((g) => g.path === cfg.game);
  $('mDlp').textContent = mine ? ((mine.dlp === false || mine.installed === false) ? '已关闭' : '已开启') : '—';
  $('mVoice').textContent = st.voice_label || cfg.voice || '—';
  $('filterStat').textContent = st.filtered ? '· 已过滤 ' + st.filtered + ' 条界面文字' : '';
  pushSpark(Number(m.rate || 0), mem);
  drawSpark($('sparkRate'), sparkRate, Math.max(10, ...sparkRate));
  drawSpark($('sparkMem'), sparkMem, Math.max(50, ...sparkMem));

  /* 剧情列表 */
  const ol = $('texts');
  const lines = st.lines || [];
  if (ol.dataset.n !== String(lines.length) || ol.dataset.last !== (lines[lines.length - 1] || '')) {
    ol.dataset.n = String(lines.length);
    ol.dataset.last = lines[lines.length - 1] || '';
    ol.innerHTML = '';
    if (!lines.length) {
      const li = document.createElement('li');
      li.className = 'muted';
      li.textContent = '还没有读取记录 —— 去游戏库启动一个游戏吧';
      ol.appendChild(li);
    }
    lines.slice().reverse().forEach((ln) => {
      const li = document.createElement('li');
      const mm = /^【([^】]+)】([\s\S]*)$/.exec(ln);
      li.innerHTML = mm ? `<span class="who">【${esc(mm[1])}】</span>${esc(mm[2])}` : esc(ln);
      /* ★不要再绑右键=标成"不是剧情"★
         那是自绘右键菜单上线之前的旧交互,结果与全局菜单冲突:
         随手右键一下就把这句学成忽略规则、句子当场从列表里消失(玩家反馈的 bug)。
         现在想标记请用右键菜单里的「标成"不是剧情"」。 */
      li.onclick = () => post('/api/speak', { text: ln });
      ol.appendChild(li);
    });
    ol.scrollTop = 0;              /* 最新在最上面 → 滚动条置顶 */
  }


  /* 累计阅读(永久记录):只在数值变化时改 DOM,免得每 400ms 重排 */
  const sta = st.stats;
  if (sta && $('statsChars')) {
    const sig = [sta.chars, sta.lines, sta.seconds, sta.today, JSON.stringify(sta.days)].join('|');
    if ($('statsChars').dataset.sig !== sig) {
      $('statsChars').dataset.sig = sig;
      $('statsChars').textContent = (sta.chars || 0).toLocaleString();
      $('statsLines').textContent = (sta.lines || 0).toLocaleString();
      const sec = sta.seconds || 0;
      $('statsTime').textContent = sec >= 3600 ? (sec / 3600).toFixed(1) + ' 小时'
        : (sec >= 60 ? Math.round(sec / 60) + ' 分钟' : Math.round(sec) + ' 秒');
      const fmt = (ts) => {
        if (!ts) return '—';
        const d = new Date(ts * 1000);
        return (d.getMonth() + 1) + '月' + d.getDate() + '日 '
          + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
      };
      $('statsFirst').textContent = fmt(sta.first);
      $('statsLast').textContent = fmt(sta.last);
      $('statsToday').textContent = sta.today ? ('今天 +' + sta.today.toLocaleString() + ' 字') : '';
      if ($('statsPath')) $('statsPath').textContent = sta.games > 1 ? ('共 ' + sta.games + ' 台游戏') : '';
      const box = $('statsDays');
      const days = sta.days || [];
      const max = Math.max(1, ...days.map((d) => d[1]));
      box.innerHTML = days.length
        ? days.map(([day, n]) => {
            const hh = Math.max(3, Math.round((n / max) * 46));
            const dd = day.slice(5).replace('-', '/');
            return `<i class="${n ? 'on' : ''}" style="height:${hh}px" title="${day}:${n} 字"><em>${dd}</em></i>`;
          }).join('')
        : '<span class="muted sm">还没有记录 —— 去读一段剧情吧</span>';
    }
  }

  /* 主题(以配置为准) */
  const th = cfg.theme || 'dark';
  if (document.documentElement.getAttribute('data-theme') !== th) applyTheme(th);

  /* 各页面自己的部分 */
  /* 鼠标按着的时候(pointerdown -> pointerup)一律不重建 DOM:
     否则重建会夹在按下与抬起之间,click 直接丢失 —— 玩家会感觉点不到。 */
  if (window.__LY_DOWN) return;
  store.renderers.forEach((fn) => {
    try { fn(st); }
    catch (e) { window.__JSERR = '渲染出错:' + ((e && e.message) || e); console.error(e); }
  });
}

async function markNotStory(line) {
  const r = await post('/api/story/mark', { text: line });
  toast(r.label ? `已学会:带【${r.label}】的都忽略` : '已标记这一句不是剧情');
  refresh();
}
