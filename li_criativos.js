/* Criativos do LinkedIn — script por cliente (mesmo da PDV) (não mexe no template central).
   Injetado pelo index.html antes do </body>. Lê DASH_DATA.LINKEDIN_CRIATIVOS
   ({meta:{chave:{th,c,g,n,st}}, rows:[{d,k,sp,imp,cl,...}]}) e acrescenta a seção
   "Criativos" na página LinkedIn, respeitando o mesmo filtro de período. */
(function(){
  const CR = (window.DASH_DATA || {}).LINKEDIN_CRIATIVOS;
  if (!CR || !CR.rows || !CR.rows.length || typeof renderLinkedin !== 'function') return;

  const st = document.createElement('style');
  st.textContent = `
  .licr-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
  .licr-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
  .licr-img{aspect-ratio:1/1;background:var(--surface2);display:flex;align-items:center;justify-content:center;overflow:hidden;cursor:zoom-in}
  .licr-img img{width:100%;height:100%;object-fit:cover;display:block}
  .licr-body{padding:10px 12px 12px;display:flex;flex-direction:column;gap:8px}
  .licr-n{font-size:11.5px;font-weight:700;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .licr-c{font-size:10.5px;color:var(--muted2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .licr-m{display:grid;grid-template-columns:repeat(3,1fr);gap:6px 8px}
  .licr-m div{font-size:9.5px;color:var(--muted2);text-transform:uppercase;letter-spacing:.4px}
  .licr-m b{display:block;font-size:12.5px;color:var(--text);text-transform:none;letter-spacing:0;font-variant-numeric:tabular-nums;margin-top:1px}
  .licr-top{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap}
  .licr-zoom{position:fixed;inset:0;background:rgba(0,0,0,.8);display:flex;align-items:center;justify-content:center;z-index:9999;cursor:zoom-out}
  .licr-zoom img{max-width:92vw;max-height:92vh;border-radius:8px}`;
  document.head.appendChild(st);

  // ordem da página: Campanhas → Objetivos de campanha → Criativos
  const camps = document.getElementById('liCamps');
  if (!camps) return;
  const obj = document.getElementById('liObjSection');
  const sec = document.createElement('div');
  sec.className = 'section';
  sec.id = 'liCriativosSection';
  sec.innerHTML = `<div class="licr-top"><div class="sec-hd" style="margin:0">Criativos</div>
    <div style="display:flex;gap:2px;background:var(--bg);padding:3px;border-radius:8px;border:1px solid var(--border);" id="licrOrd">
      <button class="pb active" data-o="sp" style="font-size:10px;padding:3px 8px">Invest.</button>
      <button class="pb" data-o="eng" style="font-size:10px;padding:3px 8px">Engaj.</button>
      <button class="pb" data-o="cl" style="font-size:10px;padding:3px 8px">Cliques</button>
      <button class="pb" data-o="ctr" style="font-size:10px;padding:3px 8px">CTR</button>
    </div></div><div class="licr-grid" id="liCriativos"></div>`;
  (obj || camps.closest('.section')).after(sec);

  let ordem = 'sp';
  document.getElementById('licrOrd').onclick = e => {
    const b = e.target.closest('button'); if (!b) return;
    ordem = b.dataset.o;
    document.querySelectorAll('#licrOrd .pb').forEach(x => x.classList.toggle('active', x === b));
    renderCriativos();
  };
  document.getElementById('liCriativos').onclick = e => {
    const im = e.target.closest('.licr-img img'); if (!im) return;
    const z = document.createElement('div'); z.className = 'licr-zoom';
    z.innerHTML = `<img src="${im.src}">`; z.onclick = () => z.remove(); document.body.appendChild(z);
  };

  // mesmo recorte de datas do liFiltrado() do template
  function noPeriodo(d){
    const dt = parseDayStr(d);
    if (periodDays > 0){
      const fim = getOntem();
      const ini = new Date(fim); ini.setDate(ini.getDate() - (periodDays - 1)); ini.setHours(0,0,0,0);
      if (dt < ini || dt > fim) return false;
    }
    if (dateI && dt < dateI) return false;
    if (dateF && dt > dateF) return false;
    return true;
  }

  function renderCriativos(){
    const el = document.getElementById('liCriativos'); if (!el) return;
    const por = {};
    CR.rows.forEach(r => {
      if (!noPeriodo(r.d)) return;
      if (!por[r.k]){ por[r.k] = {k: r.k}; LI_SUM.forEach(x => por[r.k][x] = 0); }
      LI_SUM.forEach(x => por[r.k][x] += (r[x] || 0));
    });
    const lst = Object.values(por).map(liDerivadas).filter(o => o.sp > 0 || o.imp > 0)
      .sort((a, b) => (b[ordem] || 0) - (a[ordem] || 0));
    const temLeads = lst.some(o => o.ld > 0);
    if (!lst.length){ el.innerHTML = `<div style="color:var(--muted2);font-size:12px;padding:12px">Nenhum criativo com veiculação no período.</div>`; return; }
    el.innerHTML = lst.map(o => {
      const m = CR.meta[o.k] || {};
      const nome = m.n || (o.k.startsWith('c_') ? 'Criativo não identificado' : 'Criativo · #' + o.k.slice(-6));
      return `<div class="licr-card">
        <div class="licr-img">${m.th ? `<img src="${m.th}" loading="lazy" alt="">` : '<span style="color:var(--muted2);font-size:11px">sem imagem</span>'}</div>
        <div class="licr-body">
          <div><div class="licr-n" title="${nome}">${statusDot(m.st)}${nome}</div><div class="licr-c" title="${m.c || ''}">${m.c || ''}</div></div>
          <div class="licr-m">
            <div>Invest.<b>${fR(o.sp)}</b></div>
            <div>Impr.<b>${fN(o.imp)}</b></div>
            <div>Cliques<b>${fN(o.cl)}</b></div>
            <div>CTR<b>${fP(o.ctr)}</b></div>
            <div>Engaj.<b>${fN(o.eng)}</b></div>
            ${temLeads ? `<div>Leads<b>${fN(o.ld)}</b></div>` : `<div>CPE<b>${fR(o.cpe)}</b></div>`}
          </div>
        </div></div>`;
    }).join('');
  }

  // toda vez que a página LinkedIn redesenha (período, filtros), redesenha os criativos
  const _orig = renderLinkedin;
  renderLinkedin = function(){ const r = _orig.apply(this, arguments); try { renderCriativos(); } catch(e) { console.error(e); } return r; };
  renderCriativos();
})();
