/* 影灵 CINE · 前端核心：路由 / API / 渲染助手 */
const App = (() => {
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

  const DNA_DIMS = ['剧情', '演技', '情感', '视听', '节奏'];

  /* ---------- 设备 & 登录态 ---------- */
  const deviceId = () => {
    let d = localStorage.getItem('cine_device');
    if (!d) { d = 'd' + Math.random().toString(36).slice(2, 10); localStorage.setItem('cine_device', d); }
    return d;
  };
  const token = () => localStorage.getItem('cine_token') || '';
  const setToken = t => t ? localStorage.setItem('cine_token', t) : localStorage.removeItem('cine_token');

  /* ---------- API ---------- */
  async function api(path, opts = {}) {
    const init = { headers: { 'Content-Type': 'application/json' }, ...opts };
    if (init.body && typeof init.body === 'object') init.body = JSON.stringify(init.body);
    const r = await fetch(path, init);
    if (!r.ok) {
      let detail = '';
      try { detail = (await r.json()).detail || ''; } catch (e) { /* ignore */ }
      throw new Error(detail || ('请求失败 ' + r.status));
    }
    return r.json();
  }
  const get = (p, params) => api(p + (params ? '?' + new URLSearchParams(params) : ''));
  const post = (p, body) => api(p, { method: 'POST', body: body || {} });
  const del = (p, params) => api(p + (params ? '?' + new URLSearchParams(params) : ''), { method: 'DELETE' });

  /* ---------- 路由 ---------- */
  const routes = {
    '#/': () => Pages.home(), '#/list': () => Pages.list(), '#/chat': () => Pages.chat(),
    '#/login': () => Pages.login(), '#/account': () => Pages.account(),
  };
  function route() {
    const hash = location.hash || '#/';
    const base = hash.split('?')[0];            // 去掉查询串，路由只看 #/xxx
    const m = base.match(/^#\/movie\/([\w]+)/);
    if (m) { Pages.detail(m[1]); return; }
    const fn = routes[base] || routes['#/'];
    fn();
  }
  const hashQuery = () => {
    const i = (location.hash || '').indexOf('?');
    return i < 0 ? {} : Object.fromEntries(new URLSearchParams(location.hash.slice(i + 1)));
  };

  /* ---------- 小工具 ---------- */
  let toastTimer;
  const toast = msg => { const el = $('#toast'); el.textContent = msg; el.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => el.hidden = true, 2600); };
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const star = s => { const n = Number(s); return Number.isInteger(n) && n > 0 ? '★'.repeat(n) + '☆'.repeat(5 - n) : ''; };
  const topDim = dna => { let b = DNA_DIMS[0], bs = -1; for (const d of DNA_DIMS) if ((dna[d] || 0) > bs) { bs = dna[d]; b = d; } return b; };
  const cleanSnip = s => (s || '').replace(/\s+/g, '').slice(0, 46);
  const cnTitle = t => String(t || '').split(/\s+/)[0];

  /* ---------- 电影卡片 ---------- */
  function movieCard(m) {
    const t = topDim(m.dna || {});
    const dim = m.dna && m.dna[t] != null ? `${t} ${m.dna[t]}` : '';
    const meta = [m.year, (m.genres || []).slice(0, 2).join('/')].filter(Boolean).join(' · ');
    return `<a class="mcard" href="#/movie/${esc(m.movie_id)}">
      <div class="poster">
        <img src="${esc(m.poster_thumb || '')}" alt="${esc(m.title)}" loading="lazy" onerror="this.style.opacity=.18">
        ${m.rating ? `<span class="rate">${esc(m.rating)}</span>` : ''}
        ${dim ? `<span class="dna-tag">${esc(dim)}</span>` : ''}
      </div>
      <div class="m-title">${esc(cnTitle(m.title))}</div>
      <div class="m-meta">${esc(meta)}</div></a>`;
  }

  /* ---------- 口碑罗盘（DNA 五维雷达 SVG） ---------- */
  function radar(dna, size = 230, showLabels = true) {
    const cx = size / 2, cy = size / 2, R = size / 2 - 30, n = 5;
    const pt = (i, r) => { const a = -Math.PI / 2 + i * 2 * Math.PI / n; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
    const poly = s => DNA_DIMS.map((_, i) => pt(i, R * s).join(',')).join(' ');
    const rings = [0.25, 0.5, 0.75, 1].map(s => `<polygon points="${poly(s)}" fill="none" stroke="#362f27"/>`).join('');
    const axes = DNA_DIMS.map((_, i) => { const [x, y] = pt(i, R); return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#2a241d"/>`; }).join('');
    const vals = DNA_DIMS.map((d, i) => pt(i, R * Math.max(0, Math.min(10, dna[d] || 0)) / 10).join(',')).join(' ');
    const labels = showLabels ? DNA_DIMS.map((d, i) => { const [x, y] = pt(i, R + 20); return `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle" font-size="12.5" fill="#b5aa92">${d}</text>`; }).join('') : '';
    const vtxt = DNA_DIMS.map((d, i) => { const [x, y] = pt(i, R * 0.62); const v = dna[d] || 0; return `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle" font-size="12" font-family="monospace" font-weight="700" fill="${v >= 8 ? '#d9c07a' : '#837a67'}">${v}</text>`; }).join('');
    return `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img" aria-label="口碑五维雷达">
      ${rings}${axes}<polygon points="${vals}" fill="rgba(198,82,44,.22)" stroke="#c6522c" stroke-width="2" stroke-linejoin="round"/>
      ${labels}${vtxt}</svg>`;
  }

  /* ---------- 匹配度环 ---------- */
  function matchRing(pct, size = 56) {
    const r = (size - 8) / 2, L = 2 * Math.PI * r, off = L * (1 - Math.max(0, Math.min(100, pct)) / 100);
    const fs = Math.max(11, Math.round(size * 0.26));
    return `<div class="match-ring" style="width:${size}px;height:${size}px"><svg width="${size}" height="${size}">
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="#2a241d" stroke-width="3.5"/>
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="#c6522c" stroke-width="3.5" stroke-linecap="round"
        stroke-dasharray="${L.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}" style="transition:stroke-dashoffset 1s cubic-bezier(.22,.61,.36,1)"/>
      <text x="${size / 2}" y="${size / 2}" text-anchor="middle" dominant-baseline="middle" font-size="${fs}" font-family="monospace" font-weight="700" fill="#d9c07a">${Math.round(pct)}<tspan font-size="${fs - 5}">%</tspan></text></svg></div>`;
  }

  /* ---------- 迷你雷达（聊天推荐卡内的小号五维图，无标签） ---------- */
  function miniRadar(dna, size = 92) {
    const cx = size / 2, cy = size / 2, R = size * 0.38, n = 5;
    const pt = (i, r) => { const a = -Math.PI / 2 + i * 2 * Math.PI / n; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
    const poly = s => DNA_DIMS.map((_, i) => pt(i, R * s).join(',')).join(' ');
    const rings = [0.5, 1].map(s => `<polygon points="${poly(s)}" fill="none" stroke="#362f27"/>`).join('');
    const vals = DNA_DIMS.map((d, i) => pt(i, R * Math.max(0, Math.min(10, dna[d] || 0)) / 10).join(',')).join(' ');
    return `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img" aria-label="五维口碑速览">
      ${rings}<polygon points="${vals}" fill="rgba(198,82,44,.22)" stroke="#c6522c" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
  }

  /* ---------- 全局搜索 ---------- */
  function bindGlobal() {
    const tgl = $('#searchToggle'), bar = $('#searchbar'), inp = $('#globalSearch'), sug = $('#globalSuggest');
    tgl.addEventListener('click', () => { bar.hidden = !bar.hidden; if (!bar.hidden) inp.focus(); });
    let t;
    inp.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(async () => {
        const q = inp.value.trim();
        if (!q) { sug.innerHTML = ''; return; }
        try {
          const d = await get('/api/suggest', { q });
          sug.innerHTML = d.items.map(i => `<button data-t="${esc(i.title)}"><span>${esc(i.title)}</span><span class="s-ty">${i.type === 'core' ? '片库' : '全库'}</span><span class="s-tag">${esc(i.year || '')}</span></button>`).join('');
          $$('button', sug).forEach(b => b.addEventListener('click', () => {
            const t = b.dataset.t, coreHit = d.items.find(i => i.type === 'core' && i.title === t);
            location.hash = coreHit ? `#/movie/${coreHit.movie_id}` : `#/list?q=${encodeURIComponent(t)}`;
            bar.hidden = true; sug.innerHTML = '';
          }));
        } catch (e) { sug.innerHTML = ''; }
      }, 220);
    });
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') { const q = inp.value.trim(); if (q) { location.hash = `#/list?q=${encodeURIComponent(q)}`; bar.hidden = true; sug.innerHTML = ''; } } });
    document.addEventListener('click', e => { if (!bar.contains(e.target) && !tgl.contains(e.target)) sug.innerHTML = ''; });
  }

  function setNav(key) { $$('.nav a').forEach(a => a.classList.toggle('active', a.dataset.nav === key)); }
  const view = () => $('#view');

  function render(tpl, nav) { view().innerHTML = tpl; if (nav) setNav(nav); window.scrollTo(0, 0); }
  const skeleton = () => '<div class="loading">正在放映…</div>';
  const errView = e => `<div class="empty">${esc(e.message || e)}</div>`;

  /* ---------- 自动游客登录（收藏/历史用） ---------- */
  async function ensureGuest() {
    if (token()) return token();
    try { const r = await post('/api/auth/guest', { device_id: deviceId() }); setToken(r.token); return r.token; }
    catch (e) { throw e; }
  }

  window.addEventListener('DOMContentLoaded', () => { bindGlobal(); route(); });
  window.addEventListener('hashchange', route);

  return { $, $$, get, post, del, esc, star, topDim, cleanSnip, cnTitle, DNA_DIMS,
           movieCard, radar, matchRing, miniRadar, deviceId, token, setToken, ensureGuest, hashQuery,
           route, toast, render, skeleton, errView, setNav, view };
})();
