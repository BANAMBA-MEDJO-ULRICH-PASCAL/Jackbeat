/* ════════════════════════════════════════════════════════════
   JACKBEAT — main.js v3
   Compatible Content Security Policy stricte : aucun gestionnaire
   inline (onclick=…), tout passe par des data-attributs et de la
   délégation d'événements. Les données venant de la base sont
   toujours insérées via textContent, jamais via innerHTML.
   ════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  const $  = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

  /* ── Configuration & textes traduits (JSON inerte fourni par le serveur) ── */
  const CONFIG = (() => {
    try { return JSON.parse($('#jb-config').textContent); } catch (e) { return { i18n: {} }; }
  })();
  const T = (key) => (CONFIG.i18n && CONFIG.i18n[key]) || key;
  const LOCALE = CONFIG.lang === 'en' ? 'en-GB' : 'fr-FR';
  const csrfToken = () => ($('meta[name="csrf-token"]') || {}).content || '';

  /** Crée un élément DOM : el('a', {href, class}, [enfants|texte]) */
  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') node.className = v;
      else if (k === 'text') node.textContent = v;
      else node.setAttribute(k, v);
    }
    (Array.isArray(children) ? children : [children]).forEach(c => {
      if (c === null || c === undefined) return;
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return node;
  }

  /** N'autorise que des URL http(s) ou relatives au site. */
  function safeUrl(u) {
    if (!u) return null;
    try {
      const parsed = new URL(u, location.origin);
      return (parsed.protocol === 'https:' || parsed.protocol === 'http:') ? parsed.href : null;
    } catch (e) { return null; }
  }

  /* ── 1. Navbar — ombre au défilement ─────────────────── */
  function initNavbar() {
    const nav = $('.jb-navbar');
    if (!nav) return;
    const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 60);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ── 2. Apparition au défilement ─────────────────────── */
  function initScrollReveal() {
    const items = $$('.reveal, .reveal-left, .reveal-right');
    if (!items.length) return;
    if (!('IntersectionObserver' in window)) { items.forEach(i => i.classList.add('shown')); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          const delay = parseInt(e.target.dataset.delay || 0, 10);
          setTimeout(() => e.target.classList.add('shown'), delay);
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    items.forEach(el => io.observe(el));
  }

  /* ── 3. Compteurs animés ─────────────────────────────── */
  function animateCounter(node) {
    const raw = node.dataset.target;
    const target = parseFloat(raw);
    const suffix = node.dataset.suffix || '';
    const isFloat = raw.includes('.');
    if (isNaN(target)) return;
    const fmt = (v) => (isFloat ? v.toFixed(1) : Math.floor(v).toLocaleString(LOCALE)) + suffix;
    const start = performance.now();
    function tick(now) {
      const p = Math.min((now - start) / 1200, 1);
      node.textContent = fmt(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(tick); else node.textContent = fmt(target);
    }
    requestAnimationFrame(tick);
  }

  function initCounters() {
    const counters = $$('[data-target]');
    if (!counters.length || !('IntersectionObserver' in window)) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { animateCounter(e.target); io.unobserve(e.target); } });
    }, { threshold: 0.4 });
    counters.forEach(c => io.observe(c));
  }

  /* ── 4. Messages flash : disparition automatique ─────── */
  function initFlashDismiss() {
    setTimeout(() => {
      $$('.alert-dismissible, .adm-flash').forEach(a => {
        if (a.querySelector('a')) return;          // garder les messages avec un lien d'action
        a.style.transition = 'opacity .5s, transform .5s';
        a.style.opacity = '0';
        a.style.transform = 'translateY(-8px)';
        setTimeout(() => a.remove(), 500);
      });
    }, 6000);
  }

  /* ── 5. Formulaires ──────────────────────────────────── */
  function initForms() {
    $$('form.needs-validation').forEach(form => {
      form.addEventListener('submit', e => {
        if (!form.checkValidity()) { e.preventDefault(); e.stopPropagation(); }
        form.classList.add('was-validated');
      });
    });

    // Confirmation des actions destructrices : data-confirm sur le bouton
    document.addEventListener('submit', e => {
      const btn = e.submitter;
      const msg = (btn && btn.dataset.confirm) || e.target.dataset.confirm;
      if (msg && !window.confirm(msg)) { e.preventDefault(); e.stopImmediatePropagation(); }
    }, true);

    // Soumission automatique d'un filtre
    document.addEventListener('change', e => {
      const t = e.target.closest('[data-autosubmit]');
      if (t && t.form) t.form.requestSubmit ? t.form.requestSubmit() : t.form.submit();
    });

    document.addEventListener('mousedown', () => document.body.classList.add('using-mouse'));
    document.addEventListener('keydown',   () => document.body.classList.remove('using-mouse'));
  }

  /* ── 6. Images : vignette de secours si le chargement échoue ── */
  function initImageFallback() {
    const replace = (img) => {
      const div = el('div', { class: img.className + ' thumb-fallback', 'aria-hidden': 'true' }, img.dataset.fallback || '🎵');
      img.replaceWith(div);
    };
    document.addEventListener('error', e => {
      const img = e.target;
      if (img && img.tagName === 'IMG' && img.dataset.fallback !== undefined) replace(img);
    }, true);
    // Images déjà en échec avant l'exécution du script
    $$('img[data-fallback]:not([loading="lazy"])').forEach(img => { if (img.complete && img.naturalWidth === 0 && img.src) replace(img); });
  }

  /* ── 7. Effet « tilt » léger sur les cartes de stats ─── */
  function initCardTilt() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    $$('.stat-card').forEach(card => {
      card.addEventListener('mousemove', e => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - .5;
        const y = (e.clientY - r.top) / r.height - .5;
        card.style.transform = `translateY(-5px) rotateX(${-y * 6}deg) rotateY(${x * 6}deg)`;
        card.style.transition = 'transform .1s';
      });
      card.addEventListener('mouseleave', () => {
        card.style.transform = '';
        card.style.transition = 'transform .4s ease';
      });
    });
  }

  /* ── 8. Défilement doux vers les ancres internes ─────── */
  function initSmoothScroll() {
    document.addEventListener('click', e => {
      const link = e.target.closest('a[href^="#"]');
      if (!link || link.getAttribute('href').length < 2) return;
      let target;
      try { target = $(link.getAttribute('href')); } catch (err) { return; }
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  /* ── 9. Recherche instantanée (navbar) ──────────────── */
  function initSearchSuggestions() {
    const input = $('#navSearchInput');
    const box = $('#searchSuggestions');
    if (!input || !box || !CONFIG.suggestUrl) return;
    let timer, controller;

    const close = () => { box.classList.remove('open'); box.replaceChildren(); };

    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) { close(); return; }
      timer = setTimeout(async () => {
        if (controller) controller.abort();
        controller = new AbortController();
        try {
          const res = await fetch(`${CONFIG.suggestUrl}?q=${encodeURIComponent(q)}`,
                                  { signal: controller.signal, headers: { Accept: 'application/json' } });
          if (!res.ok) { close(); return; }
          const data = await res.json();
          if (!Array.isArray(data) || !data.length) { close(); return; }
          box.replaceChildren(...data.map(item => {
            const url = safeUrl(item.url);
            if (!url) return document.createComment('');
            const thumbUrl = safeUrl(item.thumb);
            const thumb = thumbUrl
              ? el('img', { class: 'suggestion-thumb', src: thumbUrl, alt: '', 'data-fallback': '🎵' })
              : el('span', { class: 'suggestion-thumb', 'aria-hidden': 'true' }, item.type === 'artiste' ? '🎤' : '🎵');
            return el('a', { class: 'suggestion-item', href: url, role: 'option' }, [
              thumb,
              el('span', { style: 'min-width:0;' }, [
                el('span', { class: 'suggestion-label d-block', text: item.label }),
                el('span', { class: 'suggestion-sub d-block', text: item.sub }),
              ]),
              el('span', { class: 'suggestion-type ' + (item.type === 'artiste' ? 'artiste' : 'oeuvre'),
                           text: item.type === 'artiste' ? T('artist') : T('work') }),
            ]);
          }));
          box.classList.add('open');
        } catch (err) { if (err.name !== 'AbortError') close(); }
      }, 250);
    });
    input.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
    document.addEventListener('click', e => { if (!input.contains(e.target) && !box.contains(e.target)) close(); });
  }

  /* ── 10. Likes (POST protégé par jeton CSRF) ─────────── */
  function initLikes() {
    document.addEventListener('click', async e => {
      const btn = e.target.closest('[data-like-url]');
      if (!btn) return;
      e.preventDefault();
      btn.disabled = true;
      try {
        const res = await fetch(btn.dataset.likeUrl, {
          method: 'POST', credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken() },
        });
        if (!res.ok) throw new Error(res.status);
        const data = await res.json();
        btn.classList.toggle('liked', !!data.liked);
        btn.setAttribute('aria-pressed', data.liked ? 'true' : 'false');
        const heart = btn.querySelector('.heart');
        if (heart) heart.textContent = data.liked ? '❤️' : '🤍';
        const label = btn.querySelector('[data-like-label]');
        if (label) label.textContent = data.liked ? T('liked') : T('like');
        $$('[data-like-count]').forEach(n => { n.textContent = data.nb; });
      } catch (err) {
        console.error(err);
      } finally {
        btn.disabled = false;
      }
    });
  }

  /* ── 11. Lecteurs YouTube ────────────────────────────── */
  const YT_ID = /^[a-zA-Z0-9_-]{11}$/;
  const ytEmbed = (id) => `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0&modestbranding=1`;

  function initPlayers() {
    const wrap = $('#ytPlayerWrap');
    const iframe = $('#ytIframe');
    const title = $('#playerTitle');
    let currentRow = null;

    const setRowState = (row, playing) => {
      if (!row) return;
      row.classList.toggle('playing', playing);
      const icon = row.querySelector('[data-play-icon] i');
      if (icon) icon.className = playing ? 'bi bi-stop-fill' : 'bi bi-play-fill';
      const btn = row.querySelector('[data-play-icon]');
      if (btn) btn.classList.toggle('pause-state', playing);
    };
    const closePlayer = () => {
      if (!wrap) return;
      iframe.src = 'about:blank';
      wrap.classList.remove('visible');
      setRowState(currentRow, false);
      currentRow = null;
    };
    const playRow = (row) => {
      const id = row.dataset.yt;
      if (!wrap || !YT_ID.test(id)) return;
      if (currentRow === row && wrap.classList.contains('visible')) { closePlayer(); return; }
      setRowState(currentRow, false);
      iframe.src = ytEmbed(id);
      title.textContent = row.dataset.ytTitle || '';
      wrap.classList.add('visible');
      currentRow = row;
      setRowState(row, true);
    };

    document.addEventListener('click', e => {
      if (e.target.closest('[data-stop-propagation]')) return;
      if (e.target.closest('[data-close-player]')) { closePlayer(); return; }

      const row = e.target.closest('.oeuvre-row');
      if (row) {
        if (row.dataset.yt) playRow(row);
        else if (row.dataset.href) window.location.href = row.dataset.href;
        return;
      }

      const ph = e.target.closest('[data-yt-load]');
      if (ph && YT_ID.test(ph.dataset.ytLoad)) {
        const frame = el('iframe', {
          src: ytEmbed(ph.dataset.ytLoad), title: 'YouTube', allowfullscreen: '',
          referrerpolicy: 'strict-origin-when-cross-origin',
          allow: 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture',
        });
        ph.replaceWith(frame);
      }
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closePlayer();
      if ((e.key === 'Enter' || e.key === ' ') && e.target.classList && e.target.classList.contains('oeuvre-row')) {
        e.preventDefault(); e.target.click();
      }
    });
  }

  /* ── 12. Onglets (Top charts) ────────────────────────── */
  function initTabs() {
    document.addEventListener('click', e => {
      const tab = e.target.closest('[data-tab]');
      if (!tab) return;
      $$('.tab-panel').forEach(p => p.classList.remove('active'));
      $$('[data-tab]').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
      const panel = $('#panel-' + tab.dataset.tab);
      if (panel) panel.classList.add('active');
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
    });
  }

  /* ── 13. Graphiques Plotly (données JSON inertes) ───── */
  function initCharts() {
    const src = $('#jb-charts');
    if (!src || !window.Plotly) return;
    let graphs;
    try { graphs = JSON.parse(src.textContent); } catch (e) { return; }
    const cfg = Object.assign({}, window.PLOTLY_CONFIG);
    $$('.jb-chart[data-chart]').forEach(div => {
      const fig = graphs[div.dataset.chart];
      if (fig && fig.data) window.Plotly.newPlot(div, fig.data, fig.layout || {}, cfg);
    });
  }
  window.PLOTLY_CONFIG = {
    displayModeBar: true, displaylogo: false, responsive: true,
    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
    toImageButtonOptions: { filename: 'jackbeat_graphique', format: 'png', scale: 2 },
  };

  /* ── 14. Tableau : recherche + tri ───────────────────── */
  function initTable() {
    const input = $('#tableSearch');
    const tbody = $('#tableBody');
    if (!tbody) return;
    if (input) {
      input.addEventListener('input', () => {
        const q = input.value.toLowerCase().trim();
        $$('tr', tbody).forEach(row => { row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none'; });
      });
    }
    let sortState = {};
    const sort = (col) => {
      const rows = $$('tr', tbody);
      const asc = !sortState[col];
      sortState = { [col]: asc };
      rows.sort((a, b) => {
        const ta = (a.cells[col] && a.cells[col].textContent.trim().toLowerCase()) || '';
        const tb = (b.cells[col] && b.cells[col].textContent.trim().toLowerCase()) || '';
        const na = parseFloat(ta), nb = parseFloat(tb);
        if (!isNaN(na) && !isNaN(nb)) return asc ? na - nb : nb - na;
        return asc ? ta.localeCompare(tb, LOCALE) : tb.localeCompare(ta, LOCALE);
      });
      rows.forEach(r => tbody.appendChild(r));
    };
    $$('th[data-sort-col]').forEach(th => {
      th.addEventListener('click', () => sort(+th.dataset.sortCol));
      th.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); sort(+th.dataset.sortCol); } });
    });
  }

  /* ── 15. Carte du Cameroun ───────────────────────────── */
  function initMap() {
    const src = $('#jb-map-data');
    if (!src) return;
    const D = JSON.parse(src.textContent);
    const plural = (n, one, many) => `${n} ${n > 1 ? T(many) : T(one)}`;
    const tooltip = $('#mapTooltip');

    function stat(label, value) {
      return el('div', { class: 'region-stat' }, [el('span', { text: label }), el('span', { class: 'val', text: String(value) })]);
    }

    function selectRegion(name) {
      $$('.region-path').forEach(p => p.classList.toggle('active', p.dataset.region === name));
      $$('.region-card').forEach(c => c.classList.toggle('active', c.dataset.region === name));
      const nbA = D.artistes[name] || 0, nbO = D.oeuvres[name] || 0, genre = D.genres[name] || '—';
      const artistes = D.detail[name] || [];
      $('#regionEmpty').hidden = true;
      $('#regionContent').hidden = false;
      $('#regionName').textContent = D.labels[name] || name;
      $('#regionSub').textContent = nbA > 0 ? `${plural(nbA, 'artists_one', 'artists_many')} · ${plural(nbO, 'works_one', 'works_many')}` : T('no_data');

      const stats = $('#regionStats');
      if (nbA > 0) {
        stats.replaceChildren(stat(T('stat_artists'), nbA), stat(T('stat_works'), nbO), stat(T('stat_genre'), genre));
      } else {
        stats.replaceChildren(el('p', { style: 'color:var(--text-dim);font-size:.85rem;text-align:center;padding:1rem 0;' }, [
          T('no_artist_yet'), el('br'), el('a', { href: CONFIG.contributeUrl, style: 'color:var(--green);', text: T('contribute') }),
        ]));
      }

      const list = $('#regionArtistes');
      if (!artistes.length) { list.replaceChildren(); }
      else {
        list.replaceChildren(
          el('div', { style: 'font-size:.68rem;letter-spacing:.15em;text-transform:uppercase;color:var(--text-dim);margin-bottom:.6rem;', text: T('artists_label') }),
          ...artistes.map(a => {
            const photo = safeUrl(a.photo);
            const av = el('div', { class: 'artiste-mini-av' },
              photo ? el('img', { src: photo, alt: '', referrerpolicy: 'no-referrer', 'data-fallback': (a.nom || '?')[0] }) : (a.nom || '?')[0]);
            return el('a', { href: D.artisteUrl + encodeURIComponent(a.id), class: 'artiste-mini' }, [
              av,
              el('div', {}, [
                el('div', { style: 'font-size:.88rem;font-weight:600;', text: a.nom }),
                el('div', { style: 'font-size:.72rem;color:var(--text-dim);', text: `${a.type} · ${plural(a.nb, 'works_one', 'works_many')}` }),
              ]),
              el('i', { class: 'bi bi-chevron-right', style: 'color:var(--text-dim);margin-left:auto;font-size:.8rem;' }),
            ]);
          })
        );
      }
      if (window.innerWidth < 992) $('#regionSidebar').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    document.addEventListener('click', e => {
      const r = e.target.closest('[data-region]');
      if (r) selectRegion(r.dataset.region);
    });
    document.addEventListener('keydown', e => {
      const r = e.target.closest && e.target.closest('[data-region]');
      if (r && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); selectRegion(r.dataset.region); }
    });
    $$('.region-path').forEach(path => {
      const name = path.dataset.region;
      path.addEventListener('mousemove', e => {
        const rect = path.closest('.carte-wrap').getBoundingClientRect();
        const nbA = D.artistes[name] || 0, nbO = D.oeuvres[name] || 0;
        tooltip.replaceChildren(el('strong', { text: D.labels[name] || name }),
          ` · ${plural(nbA, 'artists_one', 'artists_many')} · ${plural(nbO, 'works_one', 'works_many')}`);
        tooltip.style.left = (e.clientX - rect.left + 12) + 'px';
        tooltip.style.top = (e.clientY - rect.top + 12) + 'px';
        tooltip.classList.add('visible');
      });
      path.addEventListener('mouseleave', () => tooltip.classList.remove('visible'));
    });
  }

  /* ── 16. Admin : sélection multiple + barre d'actions ── */
  function initBulk() {
    $$('form[data-bulk]').forEach(form => {
      const selectAll = form.querySelector('.select-all');
      const boxes = $$('.row-cb', form);
      const bar = form.querySelector('.bulk-bar');
      const count = form.querySelector('[data-bulk-count]');
      const update = () => {
        const n = boxes.filter(b => b.checked).length;
        if (bar) bar.classList.toggle('visible', n > 0);
        if (count) count.textContent = n;
      };
      if (selectAll) selectAll.addEventListener('change', () => { boxes.forEach(b => { b.checked = selectAll.checked; }); update(); });
      boxes.forEach(b => b.addEventListener('change', update));
    });
  }

  /* ── 17. Admin : fenêtre de traitement d'un signalement ── */
  function initModal() {
    const overlay = $('#modalOverlay');
    if (!overlay) return;
    const close = () => overlay.classList.remove('open');
    document.addEventListener('click', e => {
      const opener = e.target.closest('[data-modal-open]');
      if (opener) {
        const form = $('#modalForm');
        form.action = opener.dataset.action;
        $('#modalStatut').value = opener.dataset.statut;
        $('#modalNote').value = opener.dataset.note || '';
        overlay.classList.add('open');
        $('#modalStatut').focus();
        return;
      }
      if (e.target === overlay || e.target.closest('[data-modal-close]')) close();
    });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  }

  /* ── 18. Copier dans le presse-papiers ──────────────── */
  function initCopy() {
    document.addEventListener('click', async e => {
      const btn = e.target.closest('[data-copy]');
      if (!btn) return;
      try { await navigator.clipboard.writeText(btn.dataset.copy); btn.classList.add('copied'); } catch (err) { /* ignore */ }
    });
  }

  /* ── 19. Fondu d'entrée de page (sans intercepter la navigation) ── */
  function initPageFade() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity .35s ease';
    requestAnimationFrame(() => requestAnimationFrame(() => { document.body.style.opacity = '1'; }));
  }

  document.addEventListener('DOMContentLoaded', () => {
    initPageFade();
    initNavbar();
    initScrollReveal();
    initCounters();
    initFlashDismiss();
    initForms();
    initImageFallback();
    initCardTilt();
    initSmoothScroll();
    initSearchSuggestions();
    initLikes();
    initPlayers();
    initTabs();
    initCharts();
    initTable();
    initMap();
    initBulk();
    initModal();
    initCopy();
  });
})();
