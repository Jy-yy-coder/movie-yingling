/* 影灵 CINE · 页面渲染 */
const Pages = (() => {
  const A = App;
  const DNA_DIMS = A.DNA_DIMS;

  /* 此刻心情快捷入口：点击跳聊天并自动发送预设 */
  const MOODS = [
    { label: '😔 最近有点累', q: '最近有点累，想看个轻松治愈的片子' },
    { label: '❤️ 想恋爱了', q: '想恋爱了，来一部甜甜的爱情片' },
    { label: '🌧 想哭一下', q: '想哭一下，催泪的尽管来' },
    { label: '🔥 想重新振作', q: '想重新振作，来部热血的片子' },
    { label: '😂 想轻松两小时', q: '想轻松两小时，来部搞笑喜剧' },
  ];

  const shortBrief = s => {
    if (!s) return '';
    const cut = 64;
    if (s.length <= cut) return s;
    const i = s.indexOf('。', 34);
    const j = (i > 0 && i < cut) ? i : s.lastIndexOf('，', cut);
    return s.slice(0, (j > 0 ? j : cut)) + '…';
  };
  const quoteHTML = (c, type) => c ? `<div class="quote ${type === '差评' ? 'bad' : ''}">
      <span class="q-type">${type}顶流</span>
      <div class="q-text">“${A.esc(c.text)}”</div>
      <div class="q-meta"><span class="q-votes">${Number(c.votes || 0).toLocaleString()} 票</span>
        ${c.star ? `<span>${A.star(c.star)}</span>` : ''}<span>${A.esc(c.author || '')}</span></div>
    </div>` : '';

  /* ================= 首页 ================= */
  async function home() {
    A.render(A.skeleton());
    try {
      const [top9, cn, jp, kr] = await Promise.all([
        A.get('/api/movies', { sort: 'dna', limit: 9 }),
        A.get('/api/movies', { region: '华语', limit: 8 }),
        A.get('/api/movies', { region: '日本', limit: 8 }),
        A.get('/api/movies', { region: '韩国', limit: 6 }),
      ]);
      A.render(`
        <section class="hero">
          <div class="eyebrow">影灵 CINE · MOVIE DNA</div>
          <h1>一部电影，<em>先看口碑</em>。</h1>
          <p class="lead">590 部高分片，从 11.7 万条真实短评提炼出五维口碑。先问影灵，再决定看不看。</p>
          <div class="nums">
            <div class="num"><div class="n">590</div><div class="l">高分电影</div></div>
            <div class="num"><div class="n">88,169</div><div class="l">真实短评</div></div>
            <div class="num"><div class="n">29,256</div><div class="l">长评</div></div>
            <div class="num"><div class="n">五维</div><div class="l">剧情·演技·情感·视听·节奏</div></div>
          </div>
          <div class="search"><input id="heroSearch" placeholder="搜电影名、台词、梗…（试试「陀螺」）"></div>
          <div class="chips">
            <a class="chip" href="#/list?region=华语">华语</a>
            <a class="chip" href="#/list?region=日本">日本</a>
            <a class="chip" href="#/list?region=韩国">韩国</a>
            <a class="chip" href="#/list?region=欧美">欧美</a>
            <a class="chip" href="#/chat">问影灵推荐</a>
          </div>
        </section>
        <div class="sect-title"><h2>🎭 此刻心情</h2><span class="mood-tip">点一下，影灵直接给你挑</span></div>
        <div class="mood-strip">
          ${MOODS.map(m => `<button class="mood-chip" data-q="${A.esc(m.q)}">${m.label}</button>`).join('')}
        </div>
        <div class="sect-title"><h2>口碑九强</h2><a class="more" href="#/list?sort=dna">全部 ›</a></div>
        <div class="mgrid">${top9.items.map(A.movieCard).join('')}</div>
        <div class="sect-title"><h2>华语经典</h2><a class="more" href="#/list?region=华语">更多 ›</a></div>
        <div class="mgrid">${cn.items.map(A.movieCard).join('')}</div>
        <div class="sect-title"><h2>日本电影</h2><a class="more" href="#/list?region=日本">更多 ›</a></div>
        <div class="mgrid">${jp.items.map(A.movieCard).join('')}</div>
        <div class="sect-title"><h2>韩国电影</h2><a class="more" href="#/list?region=韩国">更多 ›</a></div>
        <div class="mgrid">${kr.items.map(A.movieCard).join('')}</div>`, 'home');
      const hs = A.$('#heroSearch');
      if (hs) hs.addEventListener('keydown', e => { if (e.key === 'Enter') { const q = hs.value.trim(); if (q) location.hash = '#/list?q=' + encodeURIComponent(q); } });
      A.$$('.mood-chip').forEach(b => b.addEventListener('click', () => {
        location.hash = '#/chat?q=' + encodeURIComponent(b.dataset.q);
      }));
    } catch (e) { A.render(A.errView(e)); }
  }

  /* ================= 列表 ================= */
  const GENRES = ['剧情', '喜剧', '动作', '爱情', '科幻', '犯罪', '悬疑', '动画', '恐怖', '惊悚', '战争', '纪录片', '音乐', '奇幻'];
  async function list() {
    const q = A.hashQuery();
    A.render(A.skeleton());
    try {
      const d = await A.get('/api/movies', { region: q.region || '', genre: q.genre || '', sort: q.sort || 'dna', q: q.q || '', limit: 60 });
      A.render(`
        <div class="toolbar">
          <div class="row">
            <label>地区 <select id="fRegion">
              <option value="">全部</option>${['华语', '欧美', '日本', '韩国'].map(r => `<option ${q.region === r ? 'selected' : ''}>${r}</option>`).join('')}
            </select></label>
            <label>类型 <select id="fGenre">
              <option value="">全部</option>${GENRES.map(g => `<option ${q.genre === g ? 'selected' : ''}>${g}</option>`).join('')}
            </select></label>
            <label>排序 <select id="fSort">
              <option value="dna" ${q.sort !== 'rating' ? 'selected' : ''}>口碑五维</option>
              <option value="rating" ${q.sort === 'rating' ? 'selected' : ''}>豆瓣评分</option>
            </select></label>
            <input id="fQ" type="search" placeholder="关键词/片名" value="${A.esc(q.q || '')}" style="width:200px">
          </div>
        </div>
        <div class="dim-row"><span class="dim-lab">按维度排序</span>
          ${DNA_DIMS.map(d => `<button class="dim-chip ${q.sort === d ? 'on' : ''}" data-dim="${d}">${d}</button>`).join('')}
        </div>
        <div class="result-line">共 ${d.total} 部 · 全部来自 590 部高分片库</div>
        <div class="mgrid">${d.items.map(A.movieCard).join('')}</div>`, 'list');
      const bind = () => location.hash = '#/list?' + new URLSearchParams({
        region: A.$('#fRegion').value, genre: A.$('#fGenre').value, sort: A.$('#fSort').value, q: A.$('#fQ').value.trim() });
      A.$('#fRegion').onchange = bind; A.$('#fGenre').onchange = bind; A.$('#fSort').onchange = bind;
      A.$('#fQ').onkeydown = e => { if (e.key === 'Enter') bind(); };
      A.$$('.dim-chip').forEach(b => b.addEventListener('click', () => {
        location.hash = '#/list?' + new URLSearchParams({
          region: A.$('#fRegion').value, genre: A.$('#fGenre').value, sort: b.dataset.dim, q: A.$('#fQ').value.trim() });
      }));
    } catch (e) { A.render(A.errView(e)); }
  }

  /* ================= 详情 ================= */
  async function detail(id) {
    A.render(A.skeleton());
    try {
      const m = await A.get('/api/movies/' + id);
      const [cn, ...rest] = (m.title || '').split(/\s+/);
      const orig = rest.join(' ');
      const dna = m.dna || {};
      const conf = dna._conf === 'low' ? ' <span style="color:#c6522c">· 样本较少</span>' : '';
      const brief = m.brief || shortBrief(m.summary);
      const summary = m.summary || '';
      const quotes = m.quotes || {};
      const dnaDims = DNA_DIMS.map(d => [d, dna[d] || 0]).sort((a, b) => b[1] - a[1]);
      const topD = dnaDims[0], lowD = dnaDims[dnaDims.length - 1];
      const up1q = quotes.up1 || null, dn1q = quotes.dn1 || null;
      const longSummary = summary.length > 280;
      let favOn = false;
      A.render(`
        <div class="detail">
          <div class="dposter">
            <img src="${A.esc(m.poster_full || '')}" alt="${A.esc(m.title)}" onerror="this.style.opacity=.2">
          </div>
          <div>
            <div class="dtitle"><h1>${A.esc(cn)}</h1>${orig ? `<div class="orig">${A.esc(orig)}</div>` : ''}</div>
            <div class="dmeta">
              ${(m.genres || []).map(g => `<span class="meta-tag">${A.esc(g)}</span>`).join('')}
              ${(m.countries || []).slice(0, 3).map(c => `<span class="meta-tag">${A.esc(c)}</span>`).join('')}
              ${m.region ? `<span class="meta-tag">${A.esc(m.region)}</span>` : ''}
              ${m.year ? `<span class="meta-tag">${A.esc(m.year)}</span>` : ''}
              ${m.runtime_min ? `<span class="meta-tag">${A.esc(m.runtime_min)} 分钟</span>` : ''}
            </div>
            ${(m.director && m.director.length) ? `<div class="dmeta"><span class="meta-tag">导演 ${A.esc(m.director.join('/'))}</span></div>` : ''}
            ${(m.actors && m.actors.length) ? `<div class="dmeta"><span class="meta-tag">主演 ${A.esc(m.actors.slice(0, 4).join('/'))}</span></div>` : ''}
            <div class="dbigrate">
              <div class="score">${A.esc(m.rating || '—')}</div>
              <div class="cnt">豆瓣评分 · ${Number(m.rating_count || 0).toLocaleString()} 人评</div>
              <button class="fav-btn" id="favBtn">♥ 收藏</button>
            </div>
            <p class="summary">${A.esc(longSummary ? summary.slice(0, 280) + '…' : summary)}</p>
            ${longSummary ? `<button class="chip" id="sumToggle" style="margin-top:6px">展开剧情简介</button>` : ''}
            <div class="dna-block">
              <h3>口碑五维</h3>
              <div class="sub">由 11.7 万条真实短评加权统计${conf}</div>
              <div class="radar-wrap">
                ${A.radar(dna)}
                <div class="radar-legend">${DNA_DIMS.map(d => `<div>${d} <b>${dna[d] || 0}</b> <span>· 命中 ${dna._n ? dna._n[d] : 0} 条</span></div>`).join('')}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="sec-card ai-note">
          <h3>✨ 影灵口碑解读</h3>
          <p class="ai-note-main">《${A.esc(cn)}》的<b class="gold">${A.esc(topD[0])}维度 ${topD[1]} 分</b>最受好评。
            ${up1q ? `好评区有观众说「${A.esc(A.cleanSnip(up1q.text))}…」（高赞 ${Number(up1q.votes || 0).toLocaleString()} 票）` : ''}
            相对短板是${A.esc(lowD[0])}（${lowD[1]} 分）${dn1q ? `—— 有差评认为「${A.esc(A.cleanSnip(dn1q.text))}…」` : ''}。</p>
          <div class="ai-note-fit"><span class="fit-t">口碑最稳</span><b>${A.esc(topD[0])} ${topD[1]}</b></div>
        </div>

        <div class="sect-title"><h2>真实短评</h2><button class="chip" id="spoilerToggle" style="margin-left:auto">无剧透模式已开 · 展开</button></div>
        <div id="quoteArea" class="quotes" hidden>
          <div style="font-size:12.5px;color:#dd6a3d">以下为真实短评原文，可能含剧透，请自行斟酌。</div>
          ${quoteHTML(quotes.up1, '好评')}
          ${quoteHTML(quotes.dn1, '差评')}
        </div>
        ${m.warn ? `<div class="warnbox"><h3>避雷</h3><div class="w-line">${A.esc(m.warn.text)}</div>${m.warn.points && m.warn.points.length ? `<ul>${m.warn.points.map(p => `<li>${A.esc(p)}</li>`).join('')}</ul>` : ''}</div>` : ''}
        ${m.egg ? `<div class="eggbox"><b>冷知识</b> ${A.esc(m.egg.text)}</div>` : ''}
        ${(m.similar && m.similar.length) ? `<div class="sec-card"><h3>相似品味</h3>
          <div class="similar-grid">${m.similar.map(s => `<a class="sim" href="#/movie/${s.movie_id}"><img src="${A.esc(s.poster_thumb || '')}" loading="lazy"><div class="t">${A.esc(A.cnTitle(s.title))}</div></a>`).join('')}</div></div>` : ''}
        <div class="sec-card"><h3>数据</h3>
          <div style="color:#837a67;font-size:13px;font-family:monospace">
            短评 ${m.stats ? m.stats.comments_total : 0} 条 · 长评 ${m.stats ? m.stats.reviews_total : 0} 篇 · 短评获赞合计 ${m.stats ? m.stats.votes_sum.toLocaleString() : 0}</div>
        </div>`, '');

      /* 无剧透模式默认收起 */
      const st = A.$('#spoilerToggle'), qa = A.$('#quoteArea');
      st.addEventListener('click', () => {
        const on = qa.hidden;
        qa.hidden = !on; st.textContent = on ? '收起摘录' : '无剧透模式已开 · 展开';
      });
      const sumT = A.$('#sumToggle');
      if (sumT) sumT.addEventListener('click', () => { A.$('.summary').textContent = summary; sumT.hidden = true; });

      /* 收藏 */
      const fav = A.$('#favBtn');
      const setFav = on => { favOn = on; fav.textContent = on ? '✓ 已收藏' : '♥ 收藏'; fav.classList.toggle('on', on); };
      try { if (A.token()) { const acc = await A.get('/api/account', { token: A.token() }); if ((acc.favorites || []).some(f => f.movie_id === id)) setFav(true); } } catch (e) { /* ignore */ }
      fav.addEventListener('click', async () => {
        try {
          const t = await A.ensureGuest();
          if (!favOn) { await A.post('/api/favorites?token=' + encodeURIComponent(t), { movie_id: id }); setFav(true); A.toast('已收藏'); }
          else { await A.del('/api/favorites', { movie_id: id, token: t }); setFav(false); A.toast('已取消收藏'); }
        } catch (e) { A.toast('操作失败：' + e.message); }
      });
    } catch (e) { A.render(A.errView(e)); }
  }

  /* ================= 聊天 ================= */
  let _chatMode = 'rec';                 // rec 推荐选片 / talk 陪看讨论
  let _spoilerOn = localStorage.getItem('cine_spoiler') !== '0';

  const recCardHTML = c => {
    const poster = c.poster_thumb
      ? `<img src="${A.esc(c.poster_thumb)}" alt="${A.esc(c.title)}" onerror="this.style.opacity=.15"><span class="rc-rate">${A.esc(c.rating || '')}</span>`
      : `<span class="rc-noimg">${A.esc(A.cnTitle(c.title))}</span>`;
    return `<div class="rec-card">
      <a class="rc-poster" href="#/movie/${A.esc(c.movie_id)}">${poster}</a>
      <div class="rc-main">
        <div class="rc-top">
          <div class="rc-titles">
            <a class="rc-name" href="#/movie/${A.esc(c.movie_id)}">《${A.esc(A.cnTitle(c.title))}》</a>
            <div class="rc-meta">${A.esc(c.year || '')} · ${(c.genres || []).slice(0, 2).join('/')} · ${A.esc(c.rating || '')}分</div>
          </div>
          ${A.matchRing(c.match || 0, 50)}
        </div>
        <div class="rc-body">
          <div class="rc-radar">${A.miniRadar(c.dna || {}, 92)}</div>
          <div class="rc-reason">${A.esc(c.reason || '')}</div>
        </div>
        <div class="rc-ops"><a class="rc-detail" href="#/movie/${A.esc(c.movie_id)}">看完整口碑 →</a></div>
      </div>
    </div>`;
  };

  function chat() {
    const autoQ = A.hashQuery().q || '';
    A.render(`
      <div class="chat-layout">
        <div class="chat-head"><h1>问影灵</h1><p>推荐 · 陪看讨论 · 找评论 —— AI 只改表述，口碑忠于真实短评</p></div>
        <div class="chat-bar">
          <div class="mode-tabs" id="modeTabs">
            <button data-mode="rec" class="${_chatMode === 'rec' ? 'on' : ''}">🎬 推荐选片</button>
            <button data-mode="talk" class="${_chatMode === 'talk' ? 'on' : ''}">💬 陪看讨论</button>
          </div>
          <label class="spoiler-toggle"><span>🛡️ 无剧透</span><input type="checkbox" id="spoilerBox" ${_spoilerOn ? 'checked' : ''}></label>
        </div>
        <div class="chat-box">
          <div class="chips-row">
            <button class="q-chip">推荐一部催泪的日本动画</button>
            <button class="q-chip">霸王别姬讲什么</button>
            <button class="q-chip">哪部电影提到过陀螺</button>
          </div>
          <div class="chat-log" id="chatLog"></div>
          <div class="chat-input"><input id="chatInput" placeholder="试试：推荐一部燃的科幻片" autocomplete="off"><button id="chatSend">发送</button></div>
        </div>
      </div>`, 'chat');
    const log = A.$('#chatLog');
    const citHTML = c => `<div class="cit" data-id="${c.movie_id || ''}">
        <div class="c-t">${A.esc(c.title || '')}</div>
        <div class="c-x">${A.esc(A.cleanSnip(c.text))}</div>
        <div class="c-v">${Number(c.votes || 0).toLocaleString()} 票</div></div>`;
    const addMsg = (role, text, extra = {}) => {
      const { offline, cits, movies, movie } = extra;
      const div = document.createElement('div');
      div.className = 'msg ' + (role === 'user' ? 'user' : 'assistant');
      let html = `<div class="bub">${A.esc(text)}</div>`;
      if (movies && movies.length) html += `<div class="rec-row">${movies.map(recCardHTML).join('')}</div>`;
      else if (movie) html += `<div class="rec-row">${recCardHTML(movie)}</div>`;
      if (cits && cits.length) html += `<div class="cit-row">${cits.map(citHTML).join('')}</div>`;
      if (offline) html += `<div><span class="offline-tag">离线模式 · 规则推荐</span></div>`;
      div.innerHTML = html;
      log.appendChild(div);
      A.$$('.cit', div).forEach(c => c.addEventListener('click', () => { if (c.dataset.id) location.hash = '#/movie/' + c.dataset.id; }));
      log.scrollTop = log.scrollHeight;
    };
    const typing = () => { const d = document.createElement('div'); d.className = 'msg assistant'; d.id = 'typing'; d.innerHTML = '<div class="bub typing">影灵正在组织语言…</div>'; log.appendChild(d); log.scrollTop = log.scrollHeight; };
    const send = async text => {
      text = (text || '').trim(); if (!text) return;
      addMsg('user', text); typing();
      try {
        const r = await A.post('/api/chat', { message: text, device_id: A.deviceId(), mode: _chatMode, spoiler: _spoilerOn });
        A.$('#typing')?.remove();
        addMsg('assistant', r.text, { offline: !!r.offline, cits: r.citations || [], movies: r.movies || null, movie: r.movie || null });
      } catch (e) {
        A.$('#typing')?.remove();
        addMsg('assistant', '服务开小差了：' + e.message + '。稍后再试，或让我走离线规则推荐。', { offline: true });
      }
    };
    const inp = A.$('#chatInput'), btn = A.$('#chatSend');
    const fire = () => { const t = inp.value; inp.value = ''; send(t); };
    btn.addEventListener('click', fire);
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') fire(); });
    A.$$('.q-chip').forEach(c => c.addEventListener('click', () => send(c.textContent)));
    A.$$('#modeTabs button').forEach(b => b.addEventListener('click', () => {
      _chatMode = b.dataset.mode;
      A.$$('#modeTabs button').forEach(x => x.classList.toggle('on', x === b));
      if (_chatMode === 'talk') A.toast('陪看讨论：告诉我片名，我陪你聊（无剧透时只给看前导览）');
    }));
    const sp = A.$('#spoilerBox');
    sp.addEventListener('change', () => {
      _spoilerOn = sp.checked;
      localStorage.setItem('cine_spoiler', _spoilerOn ? '1' : '0');
      A.toast(_spoilerOn ? '已开启 🛡️ 无剧透模式' : '已关闭无剧透，讨论可能涉及关键剧情');
    });
    if (autoQ) {
      history.replaceState(null, '', '#/chat');       // 消费一次，避免 hashchange 重复触发
      send(autoQ);
    } else {
      addMsg('assistant', '你好，我是影灵。可以让我推荐电影、讲某部片的剧情，或在全库短评里找台词和梗。');
      inp.focus();
    }
  }

  /* ================= 登录 ================= */
  function login() {
    A.render(`
      <div class="auth-wrap">
        <h1>登录影灵</h1>
        <div class="auth-tabs">
          <button data-tab="code" class="active">验证码</button>
          <button data-tab="pass">密码</button>
          <button data-tab="guest">游客</button>
        </div>
        <div class="auth-form" id="authForm"></div>
      </div>`, 'login');
    const form = A.$('#authForm');
    let mode = 'login';   // login | register
    const codePanel = () => `
      <label>手机号<input id="aPhone" type="tel" placeholder="11 位手机号" maxlength="11"></label>
      <div class="row2"><input id="aCode" type="text" placeholder="验证码" maxlength="6"><button class="chip" id="aSend" type="button">获取验证码</button></div>
      ${mode === 'register' ? `<label>设置密码<input id="aPass" type="password" placeholder="至少 6 位"></label>` : ''}
      <button class="btn" id="aGo">${mode === 'register' ? '注册并登录' : '登录'}</button>
      <div class="hint"><a id="aSwitch" href="#">${mode === 'register' ? '已有账号？直接登录' : '没有账号？验证码注册'}</a></div>`;
    const passPanel = () => `
      <label>手机号<input id="aPhone" type="tel" placeholder="11 位手机号" maxlength="11"></label>
      <label>密码<input id="aPass" type="password" placeholder="请输入密码"></label>
      <button class="btn" id="aGo">登录</button>
      <div class="hint"><a id="aSwitch" href="#">没有账号？去验证码注册</a></div>`;
    const guestPanel = () => `
      <button class="btn" id="aGuestGo">以游客身份继续</button>
      <div class="guest">游客会获得临时账号，收藏与聊天记录会在注册时自动并入正式账号。</div>`;
    const show = tab => {
      form.innerHTML = tab === 'code' ? codePanel() : tab === 'pass' ? passPanel() : guestPanel();
      bindTab(tab);
    };
    function bindTab(tab) {
      if (tab === 'guest') {
        A.$('#aGuestGo').addEventListener('click', async () => {
          try { await A.ensureGuest(); A.toast('已以游客身份进入'); location.hash = '#/account'; }
          catch (e) { A.toast('失败：' + e.message); }
        });
        return;
      }
      A.$('#aSwitch').addEventListener('click', e => {
        e.preventDefault();
        mode = (tab === 'code' && mode === 'login') ? 'register' : 'login';
        if (tab === 'code') form.innerHTML = codePanel(); bindTab(tab);
      });
      if (tab === 'code') A.$('#aSend').addEventListener('click', async () => {
        const phone = A.$('#aPhone').value.trim();
        if (!/^1\d{10}$/.test(phone)) return A.toast('手机号格式不对');
        try { const r = await A.post('/api/auth/sms', { phone }); A.toast(r.dev_code ? '验证码：' + r.dev_code : '验证码已发送'); }
        catch (e) { A.toast(e.message); }
      });
      A.$('#aGo').addEventListener('click', async () => {
        const phone = A.$('#aPhone').value.trim();
        const pass = (A.$('#aPass')?.value || '');
        const code = (A.$('#aCode')?.value || '').trim();
        try {
          let r;
          if (tab === 'pass') r = await A.post('/api/auth/login', { phone, password: pass });
          else if (mode === 'register') r = await A.post('/api/auth/register', { phone, code, password: pass, device_id: A.deviceId() });
          else r = await A.post('/api/auth/login', { phone, code });
          A.setToken(r.token); A.toast('登录成功'); location.hash = '#/account';
        } catch (e) { A.toast(e.message); }
      });
    }
    A.$$('.auth-tabs button').forEach(b => b.addEventListener('click', () => {
      A.$$('.auth-tabs button').forEach(x => x.classList.remove('active'));
      b.classList.add('active'); mode = 'login'; show(b.dataset.tab);
    }));
    show('code');
  }

  /* ================= 账号 ================= */
  async function account() {
    A.render(A.skeleton());
    if (!A.token()) {
      A.render(`<div class="auth-wrap"><h1>我的</h1><div class="auth-form">
        <button class="btn" id="g1">以游客身份继续</button>
        <button class="btn" id="g2" style="background:#181512;color:#b5aa92;border:1px solid #362f27">已有账号 · 去登录</button>
        <div class="hint">游客账号的收藏与聊天记录，注册后自动并入正式账号</div></div></div>`, 'account');
      A.$('#g1').addEventListener('click', async () => { try { await A.ensureGuest(); Pages.account(); } catch (e) { A.toast(e.message); } });
      A.$('#g2').addEventListener('click', () => location.hash = '#/login');
      return;
    }
    try {
      const acc = await A.get('/api/account', { token: A.token() });
      const hist = (acc.history || []).slice().reverse();
      A.render(`
        <div class="sect-title"><h2>我的</h2></div>
        <div class="prof-line">${acc.is_guest ? '游客身份' : '手机号 ' + A.esc(acc.phone)} · 注册于 ${A.esc(acc.created_at || '')}</div>
        ${acc.is_guest ? `<div class="hint" style="text-align:left"><a href="#/login" style="color:#d9c07a">注册正式账号</a>，收藏与聊天记录会自动并入</div>` : ''}
        <div class="sect-title"><h2>收藏 · ${(acc.favorites || []).length}</h2></div>
        ${(acc.favorites || []).length ? `<div class="acc-grid">${acc.favorites.map(A.movieCard).join('')}</div>`
          : `<div class="empty" style="padding:30px 0">还没有收藏。<a href="#/list" class="more">去挑一部</a></div>`}
        <div class="sect-title"><h2>聊天记录 · ${hist.length}</h2></div>
        <div class="chat-box" style="height:auto;min-height:0;max-height:60vh">
          <div class="chat-log" style="max-height:60vh">${hist.map(m => `<div class="msg ${m.role === 'user' ? 'user' : 'assistant'}" style="max-width:90%"><div class="bub">${A.esc(m.content)}</div></div>`).join('') || '<div class="empty" style="padding:30px 0">还没有聊天记录。</div>'}</div>
        </div>
        <div style="margin-top:26px;text-align:center"><button class="chip" id="logoutBtn">退出登录</button></div>`, 'account');
      A.$('#logoutBtn').addEventListener('click', () => { A.setToken(''); location.hash = '#/'; A.toast('已退出'); });
    } catch (e) {
      A.setToken(''); A.render(A.errView('登录已失效，请重新登录。')); location.hash = '#/login';
    }
  }

  return { home, list, detail, chat, login, account };
})();
