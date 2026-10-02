/* Local Web Audio feedback. No network requests or sounds during background updates. */
(() => {
  'use strict';
  const KEY = 'field-archive-sound-v1';
  const actions = [
    {id:'select', name:'选择选项与状态', cue:'ui-tick'},
    {id:'navigate', name:'切换题目', cue:'column'},
    {id:'open', name:'打开档案、图片与记录', cue:'page-open'},
    {id:'close', name:'关闭窗口', cue:'page-close'},
    {id:'reveal', name:'展开答案与资料', cue:'text-reveal'},
    {id:'collapse', name:'收起答案与资料', cue:'page-close'},
    {id:'save', name:'保存记录完成', cue:'confirm'},
  ];
  const library = window.FieldSoundCues;
  const valid = new Set(['none', ...library.cues.map(c => c.id)]);
  const defaults = () => ({enabled:true, volume:60, mapping:Object.fromEntries(actions.map(a => [a.id,a.cue]))});
  let settings = defaults();
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (saved && typeof saved === 'object') {
      if (typeof saved.enabled === 'boolean') settings.enabled = saved.enabled;
      if (Number.isFinite(saved.volume)) settings.volume = Math.max(0,Math.min(100,saved.volume));
      for (const a of actions) if (valid.has(saved.mapping?.[a.id])) settings.mapping[a.id] = saved.mapping[a.id];
    }
  } catch { /* Unavailable storage or an old malformed preference keeps defaults. */ }
  let context, master, ready = false, previewBus;
  const buses = new Set();
  const last = new Map();
  const level = () => .95 * Math.pow(settings.volume / 100,.7);
  function persist() {
    try { localStorage.setItem(KEY,JSON.stringify(settings)); }
    catch { document.getElementById('soundNotice').textContent = '设置在本次使用中生效；浏览器暂时不能保存偏好。'; }
    paint();
  }
  function getContext() {
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return null;
    if (!context) {
      context = new Audio();
      master = context.createGain();
      master.gain.value = level();
      const limiter = context.createDynamicsCompressor();
      limiter.threshold.value = -9;
      limiter.knee.value = 6;
      limiter.ratio.value = 5;
      limiter.attack.value = .003;
      limiter.release.value = .12;
      master.connect(limiter);
      limiter.connect(context.destination);
    }
    return context;
  }
  // Resume is called inside the real gesture; delayed save feedback can then play safely.
  function unlock() {
    if (!settings.enabled || !settings.volume) return;
    try {
      const ctx = getContext();
      if (!ctx) return;
      if (ctx.state === 'running') ready = true;
      else ctx.resume().then(() => {ready = ctx.state === 'running';}).catch(() => {});
    } catch { /* Sound must never block study interactions. */ }
  }
  function stopPreview() {
    if (!previewBus || !context) return;
    previewBus.gain.setTargetAtTime(0,context.currentTime,.008);
    previewBus = null;
  }
  function silence() {
    if (!context) return;
    for (const bus of buses) bus.gain.setTargetAtTime(0,context.currentTime,.008);
    previewBus = null;
  }
  function emit(cue, preview = false) {
    if (!valid.has(cue) || cue === 'none' || document.hidden || !settings.volume) return false;
    try {
      const ctx = getContext();
      if (!ctx || ctx.state !== 'running') return false;
      if (preview) stopPreview();
      const bus = ctx.createGain();
      bus.connect(master);
      buses.add(bus);
      if (preview) previewBus = bus;
      library.play(ctx,bus,cue,ctx.currentTime + .004,0);
      setTimeout(() => {
        bus.disconnect(); buses.delete(bus);
        if (previewBus === bus) previewBus = null;
      },3500);
      return true;
    } catch { return false; }
  }
  function play(action) {
    if (!settings.enabled || !ready || document.hidden) return;
    const now = performance.now();
    // One feedback per action, even when an image click bubbles through an option.
    if (now - (last.get(action) ?? -Infinity) < 90) return;
    last.set(action,now);
    emit(settings.mapping[action]);
  }
  async function preview(cue) {
    if (cue === 'none') { stopPreview(); return; }
    const note = document.getElementById('soundNotice');
    if (!settings.volume) { note.textContent = '音量现在是 0，请先调高一点。'; return; }
    try {
      const ctx = getContext();
      if (!ctx) { note.textContent = '当前浏览器不支持音效。'; return; }
      if (ctx.state !== 'running') await ctx.resume();
      ready = ctx.state === 'running';
      if (emit(cue,true)) note.textContent = '试听只播放选中的声音，不改变音效开关。';
      else note.textContent = '声音未能播放，请检查浏览器的声音权限。';
    } catch { note.textContent = '声音未能播放，请检查浏览器的声音权限。'; }
  }
  function paint() {
    const trigger = document.getElementById('soundSettings');
    trigger.dataset.muted = String(!settings.enabled || !settings.volume);
    trigger.title = settings.enabled && settings.volume ? '音效设置 · 已开启' : '音效设置 · 已静音';
    document.getElementById('soundEnabled').checked = settings.enabled;
    document.getElementById('soundVolume').value = settings.volume;
    document.getElementById('soundVolume').style.setProperty('--sound-level',settings.volume + '%');
    document.getElementById('soundVolumeValue').textContent = settings.volume + '%';
    for (const a of actions) document.getElementById('sound-cue-'+a.id).value = settings.mapping[a.id];
  }
  function init() {
    const list = document.getElementById('soundMappings');
    for (const a of actions) {
      const row = document.createElement('div'); row.className = 'sound-row';
      const label = document.createElement('label'); label.textContent = a.name;
      label.htmlFor = 'sound-cue-'+a.id;
      const select = document.createElement('select'); select.id = label.htmlFor;
      select.add(new Option('无声','none'));
      for (const group of new Set(library.cues.map(c => c.group))) {
        const opt = document.createElement('optgroup'); opt.label = group;
        for (const cue of library.cues.filter(c => c.group === group)) opt.append(new Option(cue.name,cue.id));
        select.append(opt);
      }
      const button = document.createElement('button'); button.type = 'button';
      button.className = 'sound-preview'; button.textContent = '试听 ▷';
      button.setAttribute('aria-label','试听：'+a.name);
      select.onchange = () => {settings.mapping[a.id] = select.value; persist();};
      button.onclick = () => preview(settings.mapping[a.id]);
      row.append(label,select,button); list.append(row);
    }
    document.getElementById('soundSettings').onclick = () => document.getElementById('soundViewer').showModal();
    document.getElementById('soundEnabled').onchange = e => {
      settings.enabled = e.target.checked;
      if (settings.enabled) {unlock(); preview('ui-tick');} else silence();
      persist();
    };
    document.getElementById('soundVolume').oninput = e => {
      settings.volume = Number(e.target.value);
      if (master) master.gain.setTargetAtTime(level(),context.currentTime,.015);
      persist();
    };
    document.getElementById('soundReset').onclick = () => {
      settings.mapping = defaults().mapping; persist();
      document.getElementById('soundNotice').textContent = '已恢复推荐搭配。音量和开关保持不变。';
    };
    document.getElementById('soundViewer').addEventListener('close',stopPreview);
    document.addEventListener('pointerdown',e => {if(e.isTrusted) unlock();},true);
    document.addEventListener('keydown',e => {if(e.isTrusted) unlock();},true);
    document.addEventListener('visibilitychange',() => {if(document.hidden) silence();});
    paint();
  }
  window.FieldSound = Object.freeze({play,init});
})();
