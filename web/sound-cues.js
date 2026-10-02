(() => {
// Adapted from LBEILC/RhineLabUI src/audio.ts (MIT), via Intelligence Atlas.
// Copyright (c) 2026 LBEILC.
// The PV-derived typing samples are intentionally excluded.
// See THIRD_PARTY_NOTICES.md for the original copyright and license.

const noiseBuffers = new WeakMap();

const RHINE_SOUND_CUES = [
  { id: 'ui-tick', name: '轻触', group: '日常操作', note: '短、轻，适合频繁点击' },
  { id: 'text-reveal', name: '文字显现', group: '日常操作', note: '一闪而过的细小提示' },
  { id: 'inspect', name: '检查', group: '日常操作', note: '两次克制的电子提示' },
  { id: 'confirm', name: '确认', group: '日常操作', note: '两音上行，之前试听的声音' },
  { id: 'page-open', name: '页面展开', group: '页面变化', note: '柔和的上行提示' },
  { id: 'page-close', name: '页面收起', group: '页面变化', note: '短促下行，适合返回' },
  { id: 'tick', name: '玻璃轻点', group: '玻璃质感', note: '清脆的一次轻敲' },
  { id: 'column', name: '玻璃双点', group: '玻璃质感', note: '上一版用于切换分支' },
  { id: 'open', name: '玻璃展开', group: '玻璃质感', note: '现在只用于展开主分支' },
  { id: 'back', name: '玻璃返回', group: '玻璃质感', note: '上一版用于返回或收起' },
  { id: 'brand', name: '标识', group: '场景音效', note: '低音铺底，尾音较长' },
  { id: 'scan', name: '扫描', group: '场景音效', note: '连续的扫描提示' },
  { id: 'welcome', name: '欢迎', group: '场景音效', note: '上行和弦，适合少量出现' },
  { id: 'array', name: '阵列', group: '场景音效', note: '连续的玻璃颗粒' },
  { id: 'explode', name: '展开阵列', group: '场景音效', note: '三次逐渐升高的玻璃音' },
  { id: 'assemble', name: '收拢阵列', group: '场景音效', note: '三次逐渐降低的玻璃音' },
];

function schedule(ctx, destination, source, node, at, gain, duration, attack = .006) {
  const envelope = ctx.createGain();
  envelope.gain.setValueAtTime(0, at);
  envelope.gain.linearRampToValueAtTime(gain, at + Math.min(attack, duration * .3));
  envelope.gain.exponentialRampToValueAtTime(.00001, at + duration);
  envelope.gain.linearRampToValueAtTime(0, at + duration + .012);
  node.connect(envelope);
  envelope.connect(destination);
  source.start(at);
  source.stop(at + duration + .015);
  source.onended = () => {
    source.disconnect();
    if (node !== source) node.disconnect();
    envelope.disconnect();
  };
}

function tone(ctx, destination, at, startHz, endHz, gain, duration, attack = .006) {
  const oscillator = ctx.createOscillator();
  oscillator.frequency.setValueAtTime(startHz, at);
  oscillator.frequency.exponentialRampToValueAtTime(endHz, at + duration);
  schedule(ctx, destination, oscillator, oscillator, at, gain, duration, attack);
}

function air(ctx, destination, at, startHz, endHz, gain, duration, attack = .008) {
  let buffer = noiseBuffers.get(ctx);
  if (!buffer) {
    buffer = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
    const samples = buffer.getChannelData(0);
    let seed = 773;
    for (let i = 0; i < samples.length; i += 1) {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      samples[i] = seed / 2147483648 - 1;
    }
    noiseBuffers.set(ctx, buffer);
  }
  const source = ctx.createBufferSource();
  const filter = ctx.createBiquadFilter();
  source.buffer = buffer;
  filter.type = 'bandpass';
  filter.Q.value = .8;
  filter.frequency.setValueAtTime(startHz, at);
  filter.frequency.exponentialRampToValueAtTime(endHz, at + duration);
  source.connect(filter);
  schedule(ctx, destination, source, filter, at, gain, duration, attack);
}

function glass(ctx, destination, at, fundamental, gain, decay, airLevel) {
  const modes = [[1, 1, 1], [1.47, .39, .66], [2.09, .21, .4], [2.73, .095, .25], [3.86, .035, .15]];
  for (const [ratio, amplitude, damping] of modes) {
    const frequency = fundamental * ratio;
    if (frequency > Math.min(8500, ctx.sampleRate * .42)) continue;
    tone(ctx, destination, at, frequency, frequency, gain * amplitude, decay * damping, .0012);
  }
  if (airLevel > 0) air(ctx, destination, at, 4800, 3600, gain * .24 * airLevel, .013, .0008);
}

function playRhineSound(ctx, destination, kind, at, airLevel = 0) {
  const airy = (start, from, to, gain, duration, attack) => {
    if (airLevel > 0) air(ctx, destination, start, from, to, gain * airLevel, duration, attack);
  };
  const glassTone = (start, fundamental, gain, decay) =>
    glass(ctx, destination, start, fundamental, gain, decay, airLevel);
  switch (kind) {
    case 'open':
      glassTone(at, 1150, .071, .58);
      glassTone(at + .16, 2180, .025, .36);
      airy(at + .035, 3100, 4400, .014, .25, .025);
      break;
    case 'column':
      glassTone(at, 1280, .065, .32);
      glassTone(at + .045, 2050, .016, .18);
      break;
    case 'tick':
      glassTone(at, 1680, .064, .24);
      break;
    case 'confirm':
      tone(ctx, destination, at, 640, 640, .039, .095, .008);
      tone(ctx, destination, at + .095, 960, 960, .026, .15, .009);
      break;
    case 'back':
      glassTone(at, 1120, .066, .22);
      tone(ctx, destination, at + .025, 560, 560, .012, .1, .002);
      break;
    case 'page-open':
      airy(at, 700, 1800, .065, .18, .025);
      tone(ctx, destination, at, 360, 480, .032, .16, .014);
      tone(ctx, destination, at + .06, 960, 960, .009, .075, .01);
      break;
    case 'page-close':
      airy(at, 1300, 600, .05, .13, .014);
      tone(ctx, destination, at, 420, 280, .027, .13, .01);
      break;
    case 'ui-tick':
      airy(at, 1500, 1200, .042, .036, .003);
      tone(ctx, destination, at, 820, 820, .022, .052, .003);
      break;
    case 'text-reveal':
      airy(at, 2100, 1300, .033, .064, .005);
      tone(ctx, destination, at, 1050, 1050, .012, .06, .005);
      break;
    case 'inspect':
      tone(ctx, destination, at, 1120, 1120, .026, .055, .005);
      tone(ctx, destination, at + .11, 1120, 1120, .018, .055, .005);
      break;
    case 'brand':
      tone(ctx, destination, at, 146.83, 146.83, .039, .72, .08);
      tone(ctx, destination, at + .07, 293.66, 293.66, .03, .62, .07);
      tone(ctx, destination, at + .17, 440, 440, .022, .54, .055);
      airy(at, 420, 1750, .036, .7, .13);
      break;
    case 'scan':
      airy(at, 1800, 3400, .025, .8, .12);
      for (let i = 0; i < 4; i += 1) tone(ctx, destination, at + i * .19 + .15, 760, 760, .025, .064, .007);
      break;
    case 'welcome':
      [293.66, 440, 659.25, 739.99].forEach((frequency, i) =>
        tone(ctx, destination, at + i * .095, frequency, frequency, .034, 1.6, .05));
      airy(at, 600, 1800, .065, .9, .15);
      break;
    case 'array':
      airy(at, 1600, 3300, .025, .8, .12);
      for (let i = 0; i < 5; i += 1) glassTone(at + .05 + i * .105, 1180 + i * 170, .043 - i * .005, .31);
      break;
    case 'explode':
      [1220, 1680, 2260].forEach((frequency, i) =>
        glassTone(at + i * .115, frequency, .054 - i * .01, .4 - i * .055));
      break;
    case 'assemble':
      [2260, 1680, 1220].forEach((frequency, i) =>
        glassTone(at + i * .095, frequency, .035 + i * .008, .2));
      break;
  }
}

window.FieldSoundCues = Object.freeze({cues: RHINE_SOUND_CUES, play: playRhineSound});
})();
