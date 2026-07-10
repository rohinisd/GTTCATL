/**
 * GTTC PORTAL — SHELL JS
 * Drop into: app/static/js/portal-shell.js
 * Add to every template: <script src="/static/js/portal-shell.js"></script>
 */

/* ═══════════════════════════════════════════
   1. THEME — init + toggle
═══════════════════════════════════════════ */
(function initTheme() {
  const saved = localStorage.getItem('gttc_theme') || 'light';
  document.documentElement.dataset.theme = saved;
})();

function toggleTheme() {
  const html = document.documentElement;
  const next = html.dataset.theme === 'light' ? 'dark' : 'light';
  html.dataset.theme = next;
  localStorage.setItem('gttc_theme', next);

  // Update toggle button text/icon
  document.querySelectorAll('.btn-theme-toggle').forEach(btn => {
    const isDark = next === 'dark';
    btn.innerHTML = isDark
      ? '<i class="ti ti-sun"></i> Light'
      : '<i class="ti ti-moon"></i> Dark';
  });
}

/* ═══════════════════════════════════════════
   2. SIDEBAR NAVIGATION (single-page switching)
═══════════════════════════════════════════ */
function navigate(pageId) {
  // Hide all sections
  document.querySelectorAll('.page-section').forEach(s => {
    s.style.display = 'none';
  });

  // Show target
  const target = document.getElementById('page-' + pageId);
  if (target) {
    target.style.display = 'block';
    target.classList.remove('page-section');
    void target.offsetWidth; // force reflow
    target.classList.add('page-section');
  }

  // Update nav active state
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.page === pageId);
  });

  // Update topbar title
  const titleEl = document.getElementById('topbarTitle');
  if (titleEl) {
    const navItem = document.querySelector(`.nav-item[data-page="${pageId}"]`);
    if (navItem) titleEl.textContent = navItem.querySelector('span')?.textContent || pageId;
  }

  // Save to session
  sessionStorage.setItem('gttc_page', pageId);

  // Destroy + re-init charts on the target page
  if (window._portalCharts) {
    Object.values(window._portalCharts).forEach(c => {
      try { c.destroy(); } catch(e) {}
    });
    window._portalCharts = {};
  }
  if (typeof window.initPageCharts === 'function') {
    setTimeout(window.initPageCharts, 50);
  }
}

/* Restore last page on load */
document.addEventListener('DOMContentLoaded', function() {
  const saved = sessionStorage.getItem('gttc_page') || 'dashboard';
  navigate(saved);
});

/* ═══════════════════════════════════════════
   3. KPI COUNTUP ANIMATION
═══════════════════════════════════════════ */
function countUp(el, target, duration) {
  if (!el) return;
  const isNum = !isNaN(target.replace(/,/g, ''));
  if (!isNum) return;
  const end = parseInt(target.replace(/,/g, ''), 10);
  const start = Date.now();
  const step = () => {
    const p = Math.min(1, (Date.now() - start) / duration);
    const ease = 1 - Math.pow(1 - p, 3);
    const val = Math.round(end * ease);
    el.textContent = val.toLocaleString('en-IN');
    if (p < 1) requestAnimationFrame(step);
    else el.textContent = target;
  };
  requestAnimationFrame(step);
}

function initKPICountup() {
  document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
    countUp(el, el.dataset.target, 900);
  });
}

/* ═══════════════════════════════════════════
   4. TOAST
═══════════════════════════════════════════ */
function toast(msg, type = 'info') {
  let box = document.getElementById('toast');
  if (!box) {
    box = document.createElement('div');
    box.id = 'toast';
    document.body.appendChild(box);
  }
  const el = document.createElement('div');
  el.className = `toast-item toast-${type}`;
  const icons = { success:'ti-circle-check', error:'ti-circle-x', info:'ti-info-circle', warn:'ti-alert-triangle' };
  el.innerHTML = `<i class="ti ${icons[type] || 'ti-info-circle'}"></i> ${msg}`;
  box.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateX(110%)';
    el.style.transition = '.3s';
    setTimeout(() => el.remove(), 300);
  }, 3200);
}

/* ═══════════════════════════════════════════
   5. MODAL HELPERS
═══════════════════════════════════════════ */
function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add('open');
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove('open');
}
// Close on backdrop click
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('modal-bg')) {
    e.target.classList.remove('open');
  }
});

/* ═══════════════════════════════════════════
   6. TOPBAR DATE
═══════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', function() {
  const el = document.getElementById('topbarDate');
  if (el) {
    el.textContent = new Date().toLocaleDateString('en-IN', {
      weekday:'short', day:'2-digit', month:'short', year:'numeric'
    });
  }
});

/* ═══════════════════════════════════════════
   7. CHART.JS DEFAULT STYLES
═══════════════════════════════════════════ */
function getAccentColor() {
  return getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#2563EB';
}
function getTextColor() {
  return getComputedStyle(document.documentElement).getPropertyValue('--text3').trim() || '#64748B';
}
function getBorderColor() {
  return getComputedStyle(document.documentElement).getPropertyValue('--border').trim() || '#E2E8F0';
}

function buildLineChart(canvasId, labels, data, label) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const accent = getAccentColor();
  const textCol = getTextColor();
  const borderCol = getBorderColor();
  const ctx = canvas.getContext('2d');
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label,
        data,
        borderColor: accent,
        backgroundColor: hexToRgba(accent, 0.12),
        borderWidth: 2.5,
        tension: 0.4,
        fill: true,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: accent,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: borderCol }, ticks: { color: textCol, font: { size: 11 } } },
        y: { beginAtZero: false, grid: { color: borderCol }, ticks: { color: textCol, font: { size: 11 } } },
      }
    }
  });
  if (!window._portalCharts) window._portalCharts = {};
  window._portalCharts[canvasId] = chart;
  return chart;
}

function buildBarChart(canvasId, labels, data, label) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const accent = getAccentColor();
  const textCol = getTextColor();
  const borderCol = getBorderColor();
  const ctx = canvas.getContext('2d');
  const chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label,
        data,
        backgroundColor: data.map((_, i) => hexToRgba(accent, i === data.length - 1 ? 0.9 : 0.65)),
        borderRadius: 5,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: textCol, font: { size: 11 } } },
        y: { beginAtZero: true, grid: { color: borderCol }, ticks: { color: textCol, font: { size: 11 } } },
      }
    }
  });
  if (!window._portalCharts) window._portalCharts = {};
  window._portalCharts[canvasId] = chart;
  return chart;
}

function buildDonutChart(canvasId, labels, data) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const accent = getAccentColor();
  const colors = [accent, hexToRgba(accent, 0.65), hexToRgba(accent, 0.4), hexToRgba(accent, 0.25)];
  const ctx = canvas.getContext('2d');
  const chart = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0, hoverOffset: 4 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { color: getTextColor(), font: { size: 12 }, padding: 16, boxWidth: 12 } }
      }
    }
  });
  if (!window._portalCharts) window._portalCharts = {};
  window._portalCharts[canvasId] = chart;
  return chart;
}

/* ═══════════════════════════════════════════
   8. UTILS
═══════════════════════════════════════════ */
function hexToRgba(hex, alpha) {
  if (!hex || !hex.startsWith('#')) return hex;
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function badgeHTML(status) {
  return `<span class="badge badge-${status}">${status.charAt(0).toUpperCase()+status.slice(1)}</span>`;
}

function formatNumber(n) {
  if (!n && n !== 0) return '—';
  return Number(n).toLocaleString('en-IN');
}

/* Table search */
function filterTable(inputId, tbodyId) {
  const q = document.getElementById(inputId)?.value?.toLowerCase() || '';
  document.querySelectorAll(`#${tbodyId} tr`).forEach(row => {
    const text = row.textContent.toLowerCase();
    row.style.display = text.includes(q) ? '' : 'none';
  });
}

/* ═══════════════════════════════════════════
   9. API HELPER
═══════════════════════════════════════════ */
async function api(url, opts = {}) {
  const token = localStorage.getItem('gttc_token') ||
                localStorage.getItem('gttc_mt_token') ||
                sessionStorage.getItem('gttc_token');
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(url, { ...opts, headers });
  if (res.status === 401) {
    localStorage.clear();
    window.location.replace('/login');
    throw new Error('Unauthorised');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ═══════════════════════════════════════════
   10. LOGOUT
═══════════════════════════════════════════ */
function doLogout() {
  localStorage.removeItem('gttc_token');
  localStorage.removeItem('gttc_mt_token');
  localStorage.removeItem('gttc_mt_name');
  localStorage.removeItem('gttc_role');
  localStorage.removeItem('gttc_name');
  sessionStorage.clear();
  window.location.replace('/login');
}

/* ═══════════════════════════════════════════
   11. INIT
═══════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', function() {
  // Wire all nav-items
  document.querySelectorAll('.nav-item[data-page]').forEach(el => {
    el.addEventListener('click', () => navigate(el.dataset.page));
  });

  // Wire logout buttons
  document.querySelectorAll('[data-action="logout"]').forEach(el => {
    el.addEventListener('click', doLogout);
  });

  // Wire theme toggle buttons
  document.querySelectorAll('.btn-theme-toggle').forEach(btn => {
    btn.addEventListener('click', toggleTheme);
    const isDark = document.documentElement.dataset.theme === 'dark';
    btn.innerHTML = isDark ? '<i class="ti ti-sun"></i> Light' : '<i class="ti ti-moon"></i> Dark';
  });

  // KPI countup
  initKPICountup();
});
