/* ════════════════════════════════════════════════════════════
   JACKBEAT — main.js v2
   Scroll reveals · Compteurs · Navbar · UX polish
   ════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ── Utilitaires ─────────────────────────────────────── */
  const $  = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

  /* ── 1. Navbar — scroll effect ───────────────────────── */
  function initNavbar() {
    const nav = $('.jb-navbar');
    if (!nav) return;
    const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 60);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ── 2. Scroll reveal avec IntersectionObserver ──────── */
  function initScrollReveal() {
    const items = $$('.reveal, .reveal-left, .reveal-right');
    if (!items.length) return;

    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          // Délai en cascade si data-delay défini
          const delay = e.target.dataset.delay || 0;
          setTimeout(() => e.target.classList.add('shown'), delay);
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

    items.forEach(el => io.observe(el));
  }

  /* ── 3. Compteur animé ───────────────────────────────── */
  function animateCounter(el) {
    const raw    = el.dataset.target;
    const target = parseFloat(raw);
    const suffix = el.dataset.suffix || '';
    const isFloat = raw.includes('.');
    if (isNaN(target)) return;

    const duration = 1200; // ms
    const start    = performance.now();

    function tick(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = target * eased;

      if (isFloat) {
        el.textContent = current.toFixed(1) + suffix;
      } else {
        el.textContent = Math.floor(current).toLocaleString('fr-FR') + suffix;
      }
      if (progress < 1) requestAnimationFrame(tick);
      else el.textContent = (isFloat ? target.toFixed(1) : target.toLocaleString('fr-FR')) + suffix;
    }
    requestAnimationFrame(tick);
  }

  function initCounters() {
    const counters = $$('[data-target]');
    if (!counters.length) return;

    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          animateCounter(e.target);
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.4 });

    counters.forEach(el => io.observe(el));
  }

  /* ── 4. Auto-dismiss flash messages ─────────────────── */
  function initFlashDismiss() {
    setTimeout(() => {
      $$('.alert-dismissible').forEach(el => {
        el.style.transition = 'opacity .5s, transform .5s';
        el.style.opacity    = '0';
        el.style.transform  = 'translateY(-8px)';
        setTimeout(() => el.remove(), 500);
      });
    }, 4500);
  }

  /* ── 5. Form enhancements ────────────────────────────── */
  function initForms() {
    // Bootstrap validation
    $$('form.needs-validation').forEach(form => {
      form.addEventListener('submit', e => {
        if (!form.checkValidity()) { e.preventDefault(); e.stopPropagation(); }
        form.classList.add('was-validated');
      });
    });

    // YouTube URL auto-fix
    const yt = $('#lien_youtube');
    if (yt) {
      yt.addEventListener('blur', () => {
        const v = yt.value.trim();
        if (v && !v.startsWith('http')) yt.value = 'https://' + v;
      });
    }

    // Focus ring polish — enlève le focus visible quand on clique (garde pour clavier)
    document.addEventListener('mousedown', () => document.body.classList.add('using-mouse'));
    document.addEventListener('keydown',   () => document.body.classList.remove('using-mouse'));
  }

  /* ── 6. Hover tilt léger sur les cartes hero ─────────── */
  function initCardTilt() {
    $$('.stat-card').forEach(card => {
      card.addEventListener('mousemove', e => {
        const rect = card.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width  - .5;
        const y = (e.clientY - rect.top)  / rect.height - .5;
        card.style.transform = `translateY(-5px) rotateX(${-y * 6}deg) rotateY(${x * 6}deg)`;
        card.style.transition = 'transform .1s';
      });
      card.addEventListener('mouseleave', () => {
        card.style.transform  = '';
        card.style.transition = 'transform .4s ease';
      });
    });
  }

  /* ── 7. Parallax subtil sur le hero ─────────────────── */
  function initParallax() {
    const hero = $('.hero');
    if (!hero || window.innerWidth < 768) return;
    window.addEventListener('scroll', () => {
      const y = window.scrollY;
      if (y > window.innerHeight) return; // Stop après le fold
      hero.style.backgroundPositionY = `${y * .25}px`;
    }, { passive: true });
  }

  /* ── 8. Smooth scroll pour les ancres internes ───────── */
  function initSmoothScroll() {
    $$('a[href^="#"]').forEach(link => {
      link.addEventListener('click', e => {
        const target = $(link.getAttribute('href'));
        if (!target) return;
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  /* ── 9. Config Plotly global ─────────────────────────── */
  window.PLOTLY_CONFIG = {
    displayModeBar: true,
    displaylogo: false,
    responsive: true,
    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
    toImageButtonOptions: { filename: 'jackbeat_graphique', format: 'png', scale: 2 }
  };

  /* ── 10. Table search (réutilisable) ─────────────────── */
  function initTableSearch() {
    const input = $('#tableSearch');
    const tbody = $('#tableBody');
    if (!input || !tbody) return;
    input.addEventListener('input', function () {
      const q = this.value.toLowerCase().trim();
      $$('tr', tbody).forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    });
  }

  /* ── 11. Page transition fade ────────────────────────── */
  function initPageFade() {
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity .35s ease';
    requestAnimationFrame(() => {
      requestAnimationFrame(() => { document.body.style.opacity = '1'; });
    });

    $$('a:not([target="_blank"]):not([href^="#"]):not([href^="javascript"])').forEach(link => {
      if (link.hostname !== location.hostname) return;
      link.addEventListener('click', e => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) return;
        const href = link.getAttribute('href');
        if (!href || href.startsWith('#') || href.startsWith('javascript')) return;
        e.preventDefault();
        document.body.style.opacity = '0';
        setTimeout(() => { window.location.href = href; }, 280);
      });
    });
  }

  /* ── 12. Highlight nav active selon URL ──────────────── */
  function initActiveNav() {
    const path = location.pathname;
    $$('.jb-navbar .nav-link').forEach(link => {
      const href = link.getAttribute('href');
      if (!href) return;
      const isActive = path === href || (href !== '/' && path.startsWith(href));
      if (isActive) link.classList.add('active');
    });
  }

  /* ── INIT ────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    initNavbar();
    initScrollReveal();
    initCounters();
    initFlashDismiss();
    initForms();
    initCardTilt();
    initParallax();
    initSmoothScroll();
    initTableSearch();
    initActiveNav();

    // Page fade — désactivé si l'utilisateur préfère moins d'animation
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      initPageFade();
    }
  });

})();
