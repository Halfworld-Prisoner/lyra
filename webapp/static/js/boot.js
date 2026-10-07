/* boot.js —— 导航与启动
   左边栏切页、顶栏动作、底栏按钮、右键菜单;最后启动 0.4 秒轮询。
   各页面模块在这里被 import 一次(它们自己会往刷新循环里注册)。 */
import { $, $$, toast, post, choose } from './core.js';
import { store, refresh, setView } from './state.js';
import { startWave } from './ui/charts.js';
import { installContextMenu } from './ui/contextmenu.js';
import { loadRules } from './views/rules.js';
import './views/library.js';
import './views/cast.js';
import './views/logs.js';
import './views/translate.js';
import './views/settings.js';
import './views/settings_extra.js';

const TITLES = {
  library: '游戏库', realtime: '实时剧情', cast: '角色配音',
  translate: '文本翻译', rules: '过滤规则', logs: '日志', settings: '设置',
};

/* ---------------- 导航 ---------------- */
$('nav').addEventListener('click', (e) => {
  const b = e.target.closest('.nav-item');
  if (!b) return;
  setView(b.dataset.view);
  $$('.nav-item').forEach((x) => x.classList.toggle('active', x === b));
  $$('.view').forEach((x) => x.classList.toggle('active', x.id === 'view-' + store.view));
  $('viewTitle').textContent = TITLES[store.view] || store.view;
  movePill();
  if (store.view === 'rules') loadRules();
});

/* 侧栏滑动药丸:平滑滑到当前项 */
export function movePill() {
  const pill = $('navPill');
  const act = document.querySelector('.nav-item.active');
  if (!pill || !act) return;
  pill.style.height = act.offsetHeight + 'px';
  pill.style.transform = 'translateY(' + act.offsetTop + 'px)';
}
window.addEventListener('resize', movePill);
window.addEventListener('load', () => setTimeout(movePill, 60));

/* ---------------- 顶栏 ---------------- */
$('search').addEventListener('input', () => window.dispatchEvent(new CustomEvent('ly-search')));
$('openBrowser').onclick = async () => {
  const r = await post('/api/open_browser', {});
  toast(r.ok ? '已在浏览器里打开' : '请手动访问 http://127.0.0.1:' + location.port + '/');
};
$('quit').onclick = async () => {
  const ok = await choose('退出 Lyra',
    '<p>要退出 Lyra 吗?</p><p class="muted sm">游戏里的 LDC(如果装过)仍然有效,'
    + '下次启动游戏时再开本程序就行。</p>',
    [{ text: '退出', value: true, primary: true }, { text: '取消', value: false }]);
  if (!ok) return;
  await post('/api/quit', {});
  document.body.innerHTML = '<div style="padding:40px;font-family:Microsoft YaHei">Lyra 已退出,可以关掉这个窗口了。</div>';
};

/* ---------------- 底栏 ---------------- */
$('bbStop').onclick = () => { post('/api/stop'); toast('已停止朗读'); };
$('bbRead').onclick = () => post('/api/speak', { text: store.S.latest || '' });
$('bbAuto').onchange = (e) => {
  const v = e.target.checked;
  $$('input[data-cfg="auto_say"]').forEach((el) => { el.checked = v; });
  post('/api/settings', { auto_say: v });
};
$('clearStory').onclick = async () => { await post('/api/story/clear'); refresh(); };
$('allowReplay').onclick = async () => {
  const r = await post('/api/story/allow-replay', {});
  toast((r && r.msg) || '已放开去重,刚才那一段可以再读一遍了');
};

/* ---------------- 启动 ---------------- */
startWave();
installContextMenu();
refresh();
setInterval(refresh, 400);      /* 刷新间隔:越小越跟手 */
