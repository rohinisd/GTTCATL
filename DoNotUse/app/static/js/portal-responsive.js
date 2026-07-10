/* portal-responsive.js — adds a mobile hamburger toggle + slide-in drawer
   to every GTTC dashboard. Works with both shell conventions:
     • admin:  #topbar / #sidebar / #content
     • others: .topbar / .sidebar / .main
   The actual show/hide is done in portal-compat.css via the
   `nav-open` class on <html>; this file only wires up the controls. */
(function () {
  'use strict';
  var MOBILE = 860;

  function setup() {
    var sidebar = document.querySelector('#sidebar, .sidebar');
    var topbar  = document.querySelector('#topbar, .topbar');
    if (!sidebar) return false;            // shell not in DOM yet — retry

    // 1. Hamburger button (once)
    if (!document.getElementById('nav-toggle')) {
      var btn = document.createElement('button');
      btn.id = 'nav-toggle';
      btn.className = 'nav-toggle';
      btn.type = 'button';
      btn.setAttribute('aria-label', 'Toggle navigation menu');
      btn.innerHTML = '<i class="ti ti-menu-2"></i>';
      if (!btn.querySelector('i')) btn.textContent = '☰'; // ☰ fallback
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        document.documentElement.classList.toggle('nav-open');
      });
      if (topbar) topbar.insertBefore(btn, topbar.firstChild);
      else document.body.appendChild(btn);
    }

    // 2. Backdrop (once) — tap to close
    if (!document.getElementById('nav-backdrop')) {
      var bd = document.createElement('div');
      bd.id = 'nav-backdrop';
      bd.className = 'nav-backdrop';
      bd.addEventListener('click', close);
      document.body.appendChild(bd);
    }

    // 3. Close the drawer after picking a nav item on mobile
    sidebar.addEventListener('click', function (e) {
      if (e.target.closest('.nav-item, a') && window.innerWidth <= MOBILE) close();
    });

    return true;
  }

  function close() { document.documentElement.classList.remove('nav-open'); }

  // Close automatically when widening back to desktop / pressing Esc
  window.addEventListener('resize', function () {
    if (window.innerWidth > MOBILE) close();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') close();
  });

  // The shell may be revealed/built after auth, so retry a few times.
  function init() {
    if (setup()) return;
    var tries = 0;
    var t = setInterval(function () {
      if (setup() || ++tries > 40) clearInterval(t);  // up to ~10s
    }, 250);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
