/* ═══════════════════════════════════════════════
   MEDI CARE — MAIN JAVASCRIPT
   ═══════════════════════════════════════════════ */

// ─── THEME ────────────────────────────────────────
function initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  if (saved === 'light') document.body.classList.add('light-mode');
  updateThemeIcon();
}

function toggleTheme() {
  document.body.classList.toggle('light-mode');
  const isLight = document.body.classList.contains('light-mode');
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
  updateThemeIcon();
}

function updateThemeIcon() {
  const btn = document.getElementById('themeToggle');
  if (!btn) return;
  const isLight = document.body.classList.contains('light-mode');
  btn.innerHTML = isLight ? '🌙' : '☀️';
  btn.title = isLight ? 'Switch to Dark Mode' : 'Switch to Light Mode';
}

// ─── LIVE CLOCK + BOOKING WINDOW STATUS ───────────
function updateLiveClock() {
  const clockEl = document.getElementById('liveClock');
  const statusEl = document.getElementById('bookingStatus');
  if (!clockEl || !statusEl) return;

  const now = new Date();
  const time = now.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  });
  clockEl.textContent = time;

  const currentHour = now.getHours();
  const isOpen = currentHour >= 7 && currentHour < 21;
  statusEl.textContent = isOpen ? 'Booking Window: Open (7 AM to 9 PM)' : 'Booking Window: Closed (Book for tomorrow)';
  statusEl.className = isOpen ? 'badge badge-green' : 'badge badge-red';
  statusEl.style.padding = '8px 10px';
  statusEl.style.fontSize = '0.74rem';
}

// ─── TOAST ────────────────────────────────────────
function showToast(message, type = 'info', duration = 3500) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon">${icons[type]}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast-hide');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ─── MODAL ────────────────────────────────────────
function openModal(id) {
  const overlay = document.getElementById(id);
  if (overlay) {
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(id) {
  const overlay = document.getElementById(id);
  if (overlay) {
    overlay.classList.remove('active');
    document.body.style.overflow = '';
  }
}

// Close modal on overlay click
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('active');
    document.body.style.overflow = '';
  }
});

// ─── DELETE CONFIRM ───────────────────────────────
async function deleteRecord(url, elementId, message = 'Are you sure you want to delete this record?') {
  if (!confirm(message)) return;

  try {
    const res = await fetch(url, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      const el = document.getElementById(elementId);
      if (el) {
        el.style.animation = 'fadeOut 0.3s ease forwards';
        setTimeout(() => el.remove(), 300);
      }
      showToast('Record deleted successfully', 'success');
    } else {
      showToast('Failed to delete record', 'error');
    }
  } catch {
    showToast('Network error', 'error');
  }
}

// ─── SEARCH ───────────────────────────────────────
function initSearch(inputId, callback) {
  const input = document.getElementById(inputId);
  if (!input) return;
  let timeout;
  input.addEventListener('input', () => {
    clearTimeout(timeout);
    timeout = setTimeout(() => callback(input.value), 300);
  });
}

// ─── STAGGER ANIMATIONS ───────────────────────────
function staggerAnimate(selector, delay = 60) {
  document.querySelectorAll(selector).forEach((el, i) => {
    el.style.animationDelay = `${i * delay}ms`;
    el.classList.add('fade-in');
  });
}

// ─── FORMAT DATE ──────────────────────────────────
function formatDate(str) {
  if (!str) return '—';
  const d = new Date(str);
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

// ─── MARKDOWN-LIKE BOLD ───────────────────────────
function parseBold(text) {
  return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

// ─── EMERGENCY MODAL ──────────────────────────────
function showEmergencyModal() {
  const html = `
    <div id="emergency-modal" class="modal-overlay active">
      <div class="modal" style="border-color: rgba(239,68,68,0.4); max-width: 400px; text-align: center;">
        <div style="font-size: 3rem; margin-bottom: 12px;">🚨</div>
        <h2 style="font-family: var(--font-display); color: var(--accent-red); margin-bottom: 12px;">EMERGENCY HELP</h2>
        <p style="color: var(--text-secondary); margin-bottom: 20px; font-size: 0.9rem;">
          If this is a medical emergency, call immediately:
        </p>
        <div style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px;">
          <a href="tel:108" style="display: block; padding: 14px; background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.3); border-radius: 10px; color: var(--accent-red); font-size: 1.2rem; font-weight: 700; text-decoration: none;">
            📞 108 — Ambulance
          </a>
          <a href="tel:112" style="display: block; padding: 14px; background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.3); border-radius: 10px; color: var(--accent-red); font-size: 1.2rem; font-weight: 700; text-decoration: none;">
            📞 112 — Emergency Services
          </a>
          <a href="tel:1066" style="display: block; padding: 14px; background: rgba(74,158,255,0.1); border: 1px solid rgba(74,158,255,0.25); border-radius: 10px; color: var(--accent-blue); font-size: 1.2rem; font-weight: 700; text-decoration: none;">
            📞 1066 — Poison Helpline
          </a>
        </div>
        <button onclick="closeModal('emergency-modal')" class="btn btn-secondary btn-block">Close</button>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML('beforeend', html);
}

// ─── KEYDOWN CLOSE MODAL ──────────────────────────
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.active').forEach(m => {
      m.classList.remove('active');
      document.body.style.overflow = '';
    });
  }
});

// ─── INIT ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  staggerAnimate('.stat-card', 80);
  staggerAnimate('.card.fade-in', 80);
  updateLiveClock();
  setInterval(updateLiveClock, 1000);

  // Nav active link
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-link, .sidebar-link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });
});

// fadeOut keyframe
const style = document.createElement('style');
style.textContent = `
  @keyframes fadeOut {
    from { opacity: 1; transform: scale(1); }
    to { opacity: 0; transform: scale(0.9); height: 0; padding: 0; margin: 0; }
  }
`;
document.head.appendChild(style);
