/* 日志页 */
import { $, $$, esc, toast, get, post, dialog, closeModals, lsRow } from '../core.js';
import { loadRules } from './rules.js';
import { store, refresh, registerRender } from '../state.js';

/* ---------------- 日志面板 ---------------- */
const LOG_TAG = { game: '剧情', filter: '过滤', junk: '跳过', warn: '注意', error: '错误', info: '信息' };
let logTab = 'all';
let _logSig = '';

/* 一条日志 = 一个可点元素。剧情/已过滤/跳过这三类带原文,点开能直接拉黑或放行。 */
function logRow(x) {
  const el = document.createElement('div');
  el.className = 'log-row ' + esc(x.level || 'info');
  const hasText = !!(x.text || '').trim();
  el.innerHTML = '<span class="lt">' + esc(x.t) + '</span>'
    + '<span class="lv-tag">' + (LOG_TAG[x.level] || '信息') + '</span>'
    + '<span class="lm">' + esc(x.msg) + '</span>'
    + (hasText ? '<span class="lm-act" title="加入黑名单 / 白名单">⚖</span>' : '');
  if (hasText) {
    el.classList.add('clickable');
    el.title = '点一下:把这一句加入黑名单或白名单';
    el.onclick = () => logVerdict(x);
  }
  return el;
}

/* 日志 → 弹窗:选择加入黑名单 / 白名单(白名单=一定朗读,黑名单=彻底不读) */
function logVerdict(entry) {
  const text = String(entry.text || '').trim();
  if (!text) { toast('这一条没有原文,不能加名单'); return; }
  const html = ''
    + '<p class="muted sm" style="margin:0 0 6px">这一条对应的游戏原文:</p>'
    + '<div class="verdict-text">' + esc(text) + '</div>'
    + '<div class="field" style="margin-top:12px">'
    + '<label>要匹配的内容 <span class="muted sm">默认就是整句;改短一点 = 所有含它的行都命中</span></label>'
    + '<input id="vdWord" class="input" value="' + esc(text) + '" spellcheck="false">'
    + '</div>'
    + '<div class="row" style="gap:8px; margin-top:12px; flex-wrap:wrap">'
    + '<button class="btn primary" data-act="white-word">加入白名单(一定朗读)</button>'
    + '<button class="btn danger" data-act="black-word">加入黑名单(彻底不读)</button>'
    + '</div>'
    + '<div class="row" style="gap:8px; margin-top:8px; flex-wrap:wrap">'
    + '<button class="btn ghost sm" data-act="white-exact">只放行这一整句(= 完全相同)</button>'
    + '<button class="btn ghost sm" data-act="black-exact">只拉黑这一整句(= 完全相同)</button>'
    + '<button class="btn ghost sm" data-act="none">从名单里移除</button>'
    + '</div>'
    + '<p class="muted sm" style="margin:12px 0 0">'
    + '<b>白名单</b>:跳过界面文字判定、菜单判定,直接当剧情读出来(去重仍然生效,不会念两遍)。<br>'
    + '<b>黑名单</b>:不显示、不朗读、也不会被当成角色名。黑名单优先于白名单。</p>';
  dialog('这条怎么处理', html);
  const word = () => (($('vdWord') || {}).value || '').trim() || text;
  $$('#dlgBody [data-act]').forEach((b) => {
    b.onclick = async () => {
      const act = b.dataset.act;
      const to = act.indexOf('white') === 0 ? 'white' : (act.indexOf('black') === 0 ? 'black' : 'none');
      const exact = act.indexOf('-exact') > 0;
      const r = await post('/api/filter/verdict', {
        text: text,
        word: exact ? text : word(),
        to: to,
        mode: exact ? 'exact' : 'word',
      });
      toast(r.msg || '已保存');
      closeModals();
      if (store.view === 'rules') loadRules(true);
    };
  });
}

function logLevelOk(lv) {
  if (logTab === 'all') return true;
  if (logTab === 'system') return ['info', 'warn', 'error'].indexOf(lv) >= 0;
  return lv === logTab;
}

export async function renderLogs() {
  let d;
  try { d = await get('/api/logs'); } catch (e) { return; }
  const bar = diagBar;
  if (bar && d.diag) {
    bar.className = 'diag-bar ' + (d.diag.level || 'info');
    bar.textContent = d.diag.text || '';
  }
  const g = d.game || {}, r = d.reader || {}, run = d.running || {}, m = d.metrics || {};
  const box = $('logStatus');
  if (box) {
    box.innerHTML =
      lsRow('当前游戏', g.name || '(未选)')
      + lsRow('是否运行', run.active ? ('运行中 · ' + (run.name || '')) : '未运行', run.active ? 'ok' : '')
      + lsRow('LDC', g.dlp ? '已开启' : '已关闭', g.dlp ? 'ok' : 'warn')
      + lsRow('LDC 状态', g.installed ? '已安装' : '未安装', g.installed ? 'ok' : 'warn')
      + lsRow('后端 / 位数', (g.backend || '-') + ' · ' + (g.bits || '-') + ' 位', 'blue')
      + lsRow('读取端', r.started ? (r.paused ? '已暂停(游戏已关)' : '已接上日志') : '未接上',
              r.started ? (r.paused ? 'warn' : 'ok') : 'bad')
      + lsRow('已读 / 已过滤', (r.count || 0) + ' 句 / ' + (r.filtered || 0) + ' 条')
      + lsRow('跳过引擎噪音', (r.skipped || 0) + ' 行')
      + lsRow('内存 / 读取速度', (m.mem_mb || 0) + ' MB / ' + (m.rate || 0) + ' 字/秒')
      + lsRow('日志文件', (r.log_exists ? '就绪 · ' : '不存在 · ')
              + Math.round((r.log_size || 0) / 1024) + ' KB,读到 '
              + Math.round((r.log_pos || 0) / 1024) + ' KB',
              r.log_exists ? '' : 'bad');
  }
  /* 分类页签上的条数 */
  const tabs = $('logTabs');
  const cnt = d.log_counts || {};
  if (tabs) {
    const sysN = (cnt.info || 0) + (cnt.warn || 0) + (cnt.error || 0);
    const num = { all: (d.logs || []).length, game: cnt.game || 0, filter: cnt.filter || 0,
                  junk: cnt.junk || 0, system: sysN };
    $$('#logTabs button').forEach((b) => {
      const lv = b.dataset.lv;
      const base = { all: '全部', game: '剧情', filter: '已过滤', junk: '跳过噪音', system: '系统' }[lv];
      b.textContent = base + (num[lv] ? ' ' + num[lv] : '');
      b.classList.toggle('on', lv === logTab);
    });
  }
  const list = $('logList');
  if (list) {
    const rows = (d.logs || []).filter((x) => logLevelOk(x.level || 'info')).slice().reverse();
    /* 400 行 × 每 0.4 秒重建太浪费(还会打断正在点的行)—— 内容没变就不动 DOM */
    const sig = logTab + '#' + rows.length + '#' + ((rows[0] || {}).t || '') + '#'
      + ((rows[0] || {}).msg || '').slice(0, 40) + '#' + ((d.logs || []).length);
    if (sig !== _logSig || !list.childElementCount) {
      _logSig = sig;
      list.innerHTML = '';
      if (!rows.length) {
        list.innerHTML = '<div class="muted">这个分类暂时没有内容</div>';
      } else {
        rows.forEach((x) => list.appendChild(logRow(x)));
      }
    }
  }
  const hint = $('logHint');
  if (hint) {
    const names = { all: '全部', game: '剧情', filter: '已过滤(被规则挡下的)', junk: '跳过噪音(引擎内部文字)', system: '系统消息' };
    hint.textContent = '最近 ' + ((d.logs || []).length) + ' 条 · 正在看:' + names[logTab];
  }
}

if ($('logTabs')) {
  $('logTabs').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    logTab = b.dataset.lv;
    $$('#logTabs button').forEach((x) => x.classList.toggle('on', x === b));
    renderLogs();
  });
}
$('logsCopy').onclick = async () => {
  const d = await get('/api/logs');
  const txt = (d.logs || []).map((x) => x.t + ' [' + x.level + '] ' + x.msg).join('\n');
  try {
    await navigator.clipboard.writeText(txt);
    toast('已复制 ' + (d.logs || []).length + ' 条日志');
  } catch (e) {
    dialog('日志内容', '<textarea class="input" style="height:40vh">' + esc(txt) + '</textarea>');
  }
};
$('logsClear').onclick = async () => { await post('/api/logs/clear', {}); renderLogs(); toast('日志已清空'); };

/* 注册到刷新循环:数据一变就重画这一页 */
registerRender(renderLogs);
