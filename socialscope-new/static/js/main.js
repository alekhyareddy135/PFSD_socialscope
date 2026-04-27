// SocialScope v2 — Main JS

// ── CURSOR GLOW ─────────────────────────────────
const glow = document.getElementById('cursorGlow');
if (glow) {
  document.addEventListener('mousemove', e => {
    glow.style.left = e.clientX + 'px';
    glow.style.top  = e.clientY + 'px';
  });
}

// ── NAV SCROLL ──────────────────────────────────
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  if (navbar) navbar.classList.toggle('scrolled', window.scrollY > 30);
}, { passive: true });

// ── HAMBURGER ───────────────────────────────────
const ham = document.getElementById('hamburger');
const navLinks = document.getElementById('navLinks');
if (ham) ham.addEventListener('click', () => navLinks.classList.toggle('open'));

// ── SCROLL ANIMATIONS ───────────────────────────
const observer = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      observer.unobserve(e.target);
    }
  });
}, { threshold: 0.1, rootMargin: '0px 0px -30px 0px' });

document.querySelectorAll('.anim-fade').forEach(el => observer.observe(el));

// ── COUNTER ANIMATION ───────────────────────────
function animateCounter(el, target, duration = 1400) {
  const start = performance.now();
  const isFloat = target % 1 !== 0;
  const update = now => {
    const progress = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    const val = target * ease;
    el.textContent = isFloat ? val.toFixed(1) : Math.round(val).toLocaleString();
    if (progress < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

const counterObs = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      const target = parseFloat(e.target.dataset.count);
      if (!isNaN(target)) animateCounter(e.target, target);
      counterObs.unobserve(e.target);
    }
  });
}, { threshold: 0.5 });

document.querySelectorAll('[data-count]').forEach(el => counterObs.observe(el));

// ── UTILITY: API FETCH ───────────────────────────
async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  return res.json();
}

async function apiGet(url) {
  const res = await fetch(url);
  return res.json();
}

// ── TOAST NOTIFICATIONS ─────────────────────────
function showToast(msg, type='info') {
  const t = document.createElement('div');
  t.style.cssText = `
    position:fixed;bottom:28px;right:28px;z-index:9999;
    padding:14px 22px;border-radius:10px;font-size:14px;font-weight:500;
    color:#fff;backdrop-filter:blur(12px);
    border:1px solid rgba(255,255,255,.1);
    background:${type==='success'?'rgba(16,185,129,.2)':type==='error'?'rgba(239,68,68,.2)':'rgba(0,245,212,.15)'};
    animation:fadeUp .3s ease;
  `;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}
