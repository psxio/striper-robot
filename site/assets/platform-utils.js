/**
 * Pure utility functions for the Strype platform.
 * No state dependencies — these are safe to import anywhere.
 * @module platform-utils
 */

export function uid() {
  return 'f_' + Math.random().toString(36).slice(2, 11);
}

export function formatDate(iso) {
  if (!iso) return '';
  var d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'
  });
}

export function debounce(fn, ms) {
  var timer;
  return function() {
    var self = this, args = arguments;
    clearTimeout(timer);
    timer = setTimeout(function() { fn.apply(self, args); }, ms);
  };
}

export async function withLoading(btn, asyncFn) {
  if (!btn) return asyncFn();
  var original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Working…';
  try {
    return await asyncFn();
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

export function escapeHtml(str) {
  if (str == null) return '';
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}

export function showToast(message, type) {
  var container = document.getElementById('toastContainer');
  if (!container) return;
  var toast = document.createElement('div');
  toast.className = 'toast toast-' + (type || 'info');
  toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(function() { toast.classList.add('show'); });
  setTimeout(function() {
    toast.classList.remove('show');
    setTimeout(function() { toast.remove(); }, 300);
  }, 2600);
}

export function showModal(html) {
  document.getElementById('modalContent').innerHTML = html;
  document.getElementById('modalOverlay').classList.add('visible');
}

export function hideModal() {
  document.getElementById('modalOverlay').classList.remove('visible');
}

export function showContextMenu(x, y, items) {
  var menu = document.getElementById('contextMenu');
  menu.innerHTML = '';
  items.forEach(function(item) {
    var btn = document.createElement('button');
    btn.className = item.danger ? 'danger' : '';
    btn.innerHTML = (item.icon || '') + item.label;
    btn.addEventListener('click', function() {
      hideContextMenu();
      item.action();
    });
    menu.appendChild(btn);
  });
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';
  menu.classList.add('visible');
}

export function hideContextMenu() {
  document.getElementById('contextMenu').classList.remove('visible');
}

export function sanitizeFilename(name) {
  return name.replace(/[^a-zA-Z0-9_\-. ]/g, '').replace(/\s+/g, '_').slice(0, 100) || 'export';
}

export function downloadFile(filename, content, mimeType) {
  var blob = new Blob([content], { type: mimeType });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
