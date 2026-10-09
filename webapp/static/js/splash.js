/* splash.js —— 开机动画的播放与收尾
 *
 * 设计:
 *   · 动画本身全在 CSS 里(见 css/splash.css),这里只负责"什么时候放、什么时候收";
 *   · 最短播放 2.4 秒(让动画走完),但如果后端数据早就准备好了,**不额外等**;
 *   · 点击 / 按键 / 触摸 = 立刻跳过 —— 第二次打开的人不会烦;
 *   · 固定流程,界面上没有开关(调试时可在控制台 lyraSplashOff() 临时关掉);
 *   · 尊重系统"减少动态效果":直接不播。
 */
import { $, get } from './core.js';

const MIN_MS = 2100;          // 动画走完所需时间
const MAX_MS = 3000;          // 兜底:再慢也要进主界面

export function splashEnabled() {
  /* 开机动画是固定流程(玩家要求:不做开关)。
     只保留一条本机调试用的逃生口:控制台执行 lyraSplashOff() 可临时关掉,
     以及系统「减少动态效果」时不动画。 */
  if (localStorage.getItem('lyra_splash') === 'off') return false;
  try {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  } catch (e) { /* 老引擎没有 matchMedia,照常播 */ }
  return true;
}

/**
 * 播放开机动画(固定流程,没有开关)。
 * @returns {Promise<void>} 动画结束(或被跳过)后 resolve
 */
export function playSplash() {
  const box = $('splash');
  if (!box || !splashEnabled()) {
    if (box && box.parentNode) box.parentNode.removeChild(box);
    document.body.classList.add('ready');
    return Promise.resolve();
  }
  const t0 = Date.now();
  return new Promise((resolve) => {
    let done = false;
    const finish = (why) => {
      if (done) return;
      done = true;
      box.classList.add('out');
      document.body.classList.add('ready');      // 主界面淡入
      setTimeout(() => { if (box.parentNode) box.parentNode.removeChild(box); }, 500);
      resolve(why);
    };
    // 跳过:点击 / 按键 / 触摸
    const skip = () => finish('skip');
    box.addEventListener('click', skip);
    window.addEventListener('keydown', skip, { once: true });
    box.addEventListener('touchstart', skip, { passive: true });

    const waitMin = Math.max(0, MIN_MS - (Date.now() - t0));
    setTimeout(() => {
      // 到最短时间后,再等一小会儿让后端数据到位(最多 MAX_MS)
      const left = Math.max(0, MAX_MS - (Date.now() - t0));
      const poll = () => {
        if (document.body.dataset.stateReady === '1' || Date.now() - t0 >= MAX_MS) {
          finish('done');
        } else {
          setTimeout(poll, 120);
        }
      };
      if (left > 0) poll(); else finish('done');
    }, waitMin);
  });
}

/* 便于排查:控制台里 lyraSplashOff() 可永久关掉开机动画(本机) */
window.lyraSplashOff = () => localStorage.setItem('lyra_splash', 'off');
window.lyraSplashOn = () => localStorage.removeItem('lyra_splash');
