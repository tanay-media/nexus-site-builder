/**
 * HEA-001 Trail 5 — Publisher theme interactions
 */
(function () {
  'use strict';

  /* Mobile nav */
  const navToggle = document.querySelector('[data-pub-nav-toggle]');
  const nav = document.querySelector('.pub-nav');
  if (navToggle && nav) {
    navToggle.addEventListener('click', () => {
      nav.classList.toggle('is-open');
      navToggle.setAttribute('aria-expanded', nav.classList.contains('is-open'));
    });
  }

  /* Nav dropdowns — tap to expand on mobile */
  document.querySelectorAll('[data-pub-nav-dropdown]').forEach((item) => {
    const link = item.querySelector('.pub-nav__link');
    if (!link) return;
    link.addEventListener('click', (e) => {
      if (!window.matchMedia('(max-width: 899px)').matches) return;
      e.preventDefault();
      const wasOpen = item.classList.contains('is-open');
      document.querySelectorAll('[data-pub-nav-dropdown].is-open').forEach((el) => {
        el.classList.remove('is-open');
      });
      if (!wasOpen) item.classList.add('is-open');
    });
  });

  /* Category filter tabs */
  document.querySelectorAll('[data-pub-filter]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const filter = btn.getAttribute('data-pub-filter');
      document.querySelectorAll('[data-pub-filter]').forEach((b) => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      document.querySelectorAll('[data-pub-cat]').forEach((card) => {
        const cat = card.getAttribute('data-pub-cat');
        card.classList.toggle('is-hidden', filter !== 'all' && cat !== filter);
      });
    });
  });

  /* Sort cards alphabetically */
  document.querySelectorAll('[data-pub-sort]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const grid = document.querySelector(btn.getAttribute('data-pub-sort'));
      if (!grid) return;
      const cards = [...grid.querySelectorAll('[data-pub-title]')];
      cards.sort((a, b) =>
        (a.getAttribute('data-pub-title') || '').localeCompare(b.getAttribute('data-pub-title') || '')
      );
      cards.forEach((c) => grid.appendChild(c.parentElement?.classList?.contains('pub-card') ? c.parentElement : c));
    });
  });

  /* TOC scroll-spy */
  const tocLinks = document.querySelectorAll('.pub-toc-vertical a[href^="#"]');
  const headings = [...document.querySelectorAll('.pub-prose h2[id], .pub-article-body h2[id]')];
  if (tocLinks.length && headings.length) {
    const onScroll = () => {
      let current = headings[0]?.id;
      for (const h of headings) {
        if (h.getBoundingClientRect().top <= 120) current = h.id;
      }
      tocLinks.forEach((a) => {
        a.classList.toggle('is-active', a.getAttribute('href') === '#' + current);
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* Copy link */
  document.querySelectorAll('[data-pub-copy-link]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(window.location.href);
        const orig = btn.textContent;
        btn.textContent = '✓ Copied';
        setTimeout(() => { btn.textContent = orig; }, 2000);
      } catch (_) { /* ignore */ }
    });
  });

  /* Trending marquee — CSS animation handles scroll; wheel optional for reduced-motion */
  const trending = document.querySelector('.pub-trending__marquee');
  if (trending && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    trending.addEventListener('wheel', (e) => {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        trending.scrollLeft += e.deltaY;
        e.preventDefault();
      }
    }, { passive: false });
  }
})();
