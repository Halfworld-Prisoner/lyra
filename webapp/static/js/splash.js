/* splash.js —— 开机动画的播放与收尾
 *
 * 设计:
 *   · 动画本身全在 CSS 里(见 css/splash.css),这里只负责"什么时候放、什么时候收";
 *   · 最短播放 2.4 秒(让动画走完),但如果后端数据早就准备好了,**不额外等**;
 *   · 点击 / 按键 / 触摸 = 立刻跳过 —— 第二次打开的人不会烦;
 *   · 设置里可以永久关掉(config.translate 之外的界面设置 splash_on);
 *   · 尊重系统"减少动态效果":直接不播。
 */
import { $, get } from './core.js';

const MIN_MS = 2100;          // 动画走完所需时间
const MAX_MS = 3000;          // 兜底:再慢也要进主界面

export function splashEnabled(cfg) {
  if (localStorage.getItem('lyra_splash') === 'off') return false;      // 本机临时关
  if (cfg && cfg.splash_on === false) return false;                    // 设置里关
  try {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  } catch (e) { /* 老引擎没有 matchMedia,照常播 */ }
  return true;
}

/**
 * 播放开机动画。
 * @param {{splash_on?:boolean}} cfg 当前配置
 * @returns {Promise<void>} 动画结束(或被跳过)后 resolve
 */
export function playSplash(cfg) {
  const box = $('splash');
  if (!box || !splashEnabled(cfg)) {
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
