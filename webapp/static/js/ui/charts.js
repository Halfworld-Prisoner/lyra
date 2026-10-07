/* charts.js —— 底栏两个小画布:读取/内存曲线(sparkline)与声波
   放在这里是因为 state.js(每 0.4 秒喂数据)和 boot.js(启动动画)都要用,
   而且它们跟具体页面无关。 */

export const sparkRate = [];
export const sparkMem = [];

export function pushSpark(rate, mem) {
  sparkRate.push(rate || 0);
  sparkMem.push(mem || 0);
  if (sparkRate.length > 60) sparkRate.shift();
  if (sparkMem.length > 60) sparkMem.shift();
}

export function drawSpark(cv, data, max) {
  if (!cv) return;
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth || 200, h = cv.clientHeight || 34;
  if (cv.width !== w * dpr || cv.height !== h * dpr) { cv.width = w * dpr; cv.height = h * dpr; }
  const c = cv.getContext('2d');
  c.clearRect(0, 0, cv.width, cv.height);
  if (data.length < 2) return;
  const top = Math.max(1, max || 1);
  const grad = c.createLinearGradient(0, 0, cv.width, 0);
  grad.addColorStop(0, '#6d5efc');
  grad.addColorStop(1, '#4aa8ff');
  c.strokeStyle = grad;
  c.lineWidth = 2 * dpr;
  c.beginPath();
  data.forEach((v, i) => {
    const x = (i / (data.length - 1)) * cv.width;
    const y = cv.height - Math.min(1, v / top) * (cv.height - 4 * dpr) - 2 * dpr;
    i === 0 ? c.moveTo(x, y) : c.lineTo(x, y);
  });
  c.stroke();
  c.lineTo(cv.width, cv.height);
  c.lineTo(0, cv.height);
  c.closePath();
  const g2 = c.createLinearGradient(0, 0, 0, cv.height);
  g2.addColorStop(0, 'rgba(109,94,252,.28)');
  g2.addColorStop(1, 'rgba(109,94,252,0)');
  c.fillStyle = g2;
  c.fill();
}

/* ---------------- 底栏声波 ---------------- */
let wavePhase = 0, waveAmp = 0.22, waveTarget = 0.22;
const wave = document.getElementById('wave');
const wctx = wave ? wave.getContext('2d') : null;

export function setWaveAmp(v) { waveTarget = v; }

function resizeWave() {
  if (!wave) return;
  const dpr = window.devicePixelRatio || 1;
  const w = wave.clientWidth || 300, h = wave.clientHeight || 44;
  if (wave.width !== w * dpr || wave.height !== h * dpr) { wave.width = w * dpr; wave.height = h * dpr; }
}

function drawWave() {
  if (wctx) {
    resizeWave();
    const w = wave.width, h = wave.height;
    wctx.clearRect(0, 0, w, h);
    wavePhase += 0.055;
    waveAmp += (waveTarget - waveAmp) * 0.07;
    const grad = wctx.createLinearGradient(0, 0, w, 0);
    grad.addColorStop(0, '#6d5efc');
    grad.addColorStop(1, '#4aa8ff');
    wctx.lineWidth = 2 * (window.devicePixelRatio || 1);
    wctx.strokeStyle = grad;
    wctx.shadowBlur = 10 * (window.devicePixelRatio || 1);
    wctx.shadowColor = 'rgba(109,94,252,.5)';
    wctx.beginPath();
    for (let x = 0; x <= w; x += 2) {
      const t = x / w;
      const env = Math.sin(Math.PI * t);
      const y = h / 2
        + Math.sin(t * Math.PI * 4 + wavePhase) * h * 0.40 * waveAmp * env
        + Math.sin(t * Math.PI * 9 - wavePhase * 1.6) * h * 0.15 * waveAmp * env;
      x === 0 ? wctx.moveTo(x, y) : wctx.lineTo(x, y);
    }
    wctx.stroke();
    wctx.shadowBlur = 0;
  }
  requestAnimationFrame(drawWave);
}

export function startWave() {
  if (wave) {
    requestAnimationFrame(drawWave);
    window.addEventListener('resize', resizeWave);
  }
}
