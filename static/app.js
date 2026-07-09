/* ============================================================
   app.js — Dashboard vanilla JS logic
   ============================================================ */

// ----------------------------------------------------------------
// Utility helpers
// ----------------------------------------------------------------

const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function showToast(msg, type = 'info', duration = 3500) {
  const container = $('#toast-container');
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type] ?? '💬'}</span><span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.style.animation = 'toastOut .3s ease forwards';
    setTimeout(() => el.remove(), 300);
  }, duration);
}

async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return data;
}

// ----------------------------------------------------------------
// Navigation
// ----------------------------------------------------------------

function navigate(page) {
  $$('.page-panel').forEach(p => p.classList.remove('active'));
  $$('.nav-item').forEach(n => n.classList.remove('active'));

  const panel = $(`#page-${page}`);
  if (panel) panel.classList.add('active');

  const navBtn = $(`[data-page="${page}"]`);
  if (navBtn) navBtn.classList.add('active');

  const titles = {
    campaigns: '🚀 Campaigns',
    settings: '⚙️ Settings',
  };
  $('#topbar-title').textContent = titles[page] ?? page;
}

$$('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => navigate(btn.dataset.page));
});

// ----------------------------------------------------------------
// Stats
// ----------------------------------------------------------------

async function refreshStats() {
  try {
    const stats = await apiFetch('/api/stats');
    $('#stat-active').textContent = stats.active_campaigns;
    $('#stat-total').textContent = stats.total_campaigns;
    $('#stat-processed').textContent = stats.total_processed_comments;
  } catch (e) {
    console.warn('Stats fetch failed:', e);
  }
}

// ----------------------------------------------------------------
// Settings page
// ----------------------------------------------------------------

const CONFIG_KEYS = [
  'INSTAGRAM_ACCESS_TOKEN',
  'INSTAGRAM_BUSINESS_ACCOUNT_ID',
  'FACEBOOK_APP_SECRET',
  'WEBHOOK_VERIFY_TOKEN',
];

async function loadSettings() {
  try {
    const config = await apiFetch('/api/config');
    CONFIG_KEYS.forEach(key => {
      const input = $(`#cfg-${key}`);
      if (input && config[key]) input.placeholder = config[key];
    });
  } catch (e) {
    console.warn('Could not load config:', e);
  }
}

$('#settings-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = $('#settings-save-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Saving…';

  let saved = 0;
  for (const key of CONFIG_KEYS) {
    const input = $(`#cfg-${key}`);
    const val = input?.value.trim();
    if (val) {
      try {
        await apiFetch('/api/config', {
          method: 'POST',
          body: JSON.stringify({ key, value: val }),
        });
        input.value = '';
        input.placeholder = '••••••' + val.slice(-6);
        saved++;
      } catch (err) {
        showToast(`Failed to save ${key}: ${err.message}`, 'error');
      }
    }
  }

  btn.disabled = false;
  btn.innerHTML = '💾 Save Settings';
  if (saved > 0) showToast(`${saved} setting(s) saved successfully!`, 'success');
});

// ----------------------------------------------------------------
// Campaigns page
// ----------------------------------------------------------------

let editingCampaignId = null;

async function loadCampaigns() {
  const grid = $('#campaigns-grid');
  grid.innerHTML = '<p style="color:var(--text-muted);padding:20px;">Loading…</p>';

  try {
    const campaigns = await apiFetch('/api/campaigns');
    renderCampaigns(campaigns);
  } catch (e) {
    grid.innerHTML = `<p style="color:var(--danger);">Error: ${e.message}</p>`;
  }
}

function renderCampaigns(campaigns) {
  const grid = $('#campaigns-grid');
  if (!campaigns.length) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-icon">📭</div>
        <h3>No campaigns yet</h3>
        <p>Create your first automation campaign to get started.</p>
        <button class="btn btn-primary" onclick="openModal()">
          ✨ New Campaign
        </button>
      </div>`;
    return;
  }

  grid.innerHTML = campaigns.map(c => {
    const keywords = c.keywords.split(',').map(k => k.trim()).filter(Boolean);
    const kwHtml = keywords.map(k => `<span class="kw-tag">${escHtml(k)}</span>`).join('');
    const thumb = c.post_thumbnail_url
      ? `<img src="${escHtml(c.post_thumbnail_url)}" alt="post thumbnail" loading="lazy">`
      : `<div style="height:160px;display:flex;align-items:center;justify-content:center;background:var(--bg-elevated);font-size:40px;">📷</div>`;

    return `
    <div class="campaign-card ${c.is_active ? '' : 'inactive'}" data-id="${c.id}">
      <div class="campaign-thumb">${thumb}</div>
      <div class="campaign-body">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
          <div class="campaign-name">${escHtml(c.name)}</div>
          <span class="badge badge-${c.is_active ? 'active' : 'inactive'}">
            ${c.is_active ? 'Active' : 'Paused'}
          </span>
        </div>
        ${c.post_caption ? `<div class="campaign-caption">${escHtml(c.post_caption)}</div>` : ''}
        <div class="campaign-keywords">${kwHtml}</div>
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:4px;">
          💬 Reply: <span style="color:var(--text-secondary)">${escHtml(c.comment_reply.slice(0,60))}${c.comment_reply.length>60?'…':''}</span>
        </div>
        <div style="font-size:12px;color:var(--text-muted);">
          ✉️ DM: <span style="color:var(--text-secondary)">${escHtml(c.dm_message.slice(0,60))}${c.dm_message.length>60?'…':''}</span>
        </div>
        <div class="campaign-footer">
          <div class="campaign-actions">
            <button class="btn btn-secondary btn-sm" onclick="editCampaign(${c.id})">✏️ Edit</button>
            <button class="btn btn-secondary btn-sm" onclick="toggleCampaign(${c.id}, this)">
              ${c.is_active ? '⏸️ Pause' : '▶️ Resume'}
            </button>
            <button class="btn btn-danger btn-sm" onclick="deleteCampaign(${c.id})">🗑️</button>
          </div>
          <div style="font-size:10px;color:var(--text-muted);">Post: ${escHtml(c.post_id.slice(0,12))}…</div>
        </div>
      </div>
    </div>`;
  }).join('');
}

function escHtml(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function toggleCampaign(id, btn) {
  try {
    const result = await apiFetch(`/api/campaigns/${id}/toggle`, { method: 'PATCH' });
    showToast(`Campaign ${result.is_active ? 'activated' : 'paused'}.`, 'success');
    loadCampaigns();
    refreshStats();
  } catch (e) {
    showToast(`Error: ${e.message}`, 'error');
  }
}

async function deleteCampaign(id) {
  if (!confirm('Delete this campaign? This cannot be undone.')) return;
  try {
    await apiFetch(`/api/campaigns/${id}`, { method: 'DELETE' });
    showToast('Campaign deleted.', 'success');
    loadCampaigns();
    refreshStats();
  } catch (e) {
    showToast(`Error: ${e.message}`, 'error');
  }
}

async function editCampaign(id) {
  try {
    const c = await apiFetch(`/api/campaigns/${id}`);
    editingCampaignId = id;
    $('#modal-title').textContent = '✏️ Edit Campaign';
    $('#field-name').value = c.name;
    $('#field-post-id').value = c.post_id;
    $('#field-keywords').value = c.keywords;
    $('#field-comment-reply').value = c.comment_reply;
    $('#field-dm-message').value = c.dm_message;

    if (c.post_thumbnail_url || c.post_caption) {
      showPostPreview({
        thumbnail_url: c.post_thumbnail_url,
        caption: c.post_caption,
        media_type: 'POST',
      });
    }

    openModal();
  } catch (e) {
    showToast(`Error: ${e.message}`, 'error');
  }
}

// ----------------------------------------------------------------
// Post ID preview on blur
// ----------------------------------------------------------------

let previewTimeout;
$('#field-post-id').addEventListener('blur', async () => {
  const postId = $('#field-post-id').value.trim();
  if (!postId) { hidePostPreview(); return; }

  clearTimeout(previewTimeout);
  previewTimeout = setTimeout(async () => {
    try {
      const data = await apiFetch(`/api/post-preview?post_id=${encodeURIComponent(postId)}`);
      showPostPreview(data);
    } catch (e) {
      hidePostPreview();
      showToast(`Could not fetch post: ${e.message}`, 'error');
    }
  }, 300);
});

function showPostPreview(data) {
  const box = $('#post-preview');
  $('#preview-img').src = data.thumbnail_url || '';
  $('#preview-img').style.display = data.thumbnail_url ? 'block' : 'none';
  $('#preview-type').textContent = data.media_type || 'POST';
  $('#preview-caption').textContent = data.caption || '(no caption)';
  box.classList.add('visible');
}

function hidePostPreview() {
  $('#post-preview').classList.remove('visible');
}

// ----------------------------------------------------------------
// Modal open/close
// ----------------------------------------------------------------

function openModal() {
  if (!editingCampaignId) {
    resetModal();
  }
  $('#campaign-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  $('#campaign-modal').classList.remove('open');
  document.body.style.overflow = '';
  resetModal();
}

function resetModal() {
  editingCampaignId = null;
  $('#modal-title').textContent = '✨ New Campaign';
  $('#campaign-form').reset();
  hidePostPreview();
}

$('#btn-new-campaign').addEventListener('click', openModal);
$('#modal-close').addEventListener('click', closeModal);
$('#modal-cancel').addEventListener('click', closeModal);
$('#campaign-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeModal();
});

// ----------------------------------------------------------------
// Campaign form submit (create or update)
// ----------------------------------------------------------------

$('#campaign-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const saveBtn = $('#campaign-save-btn');
  saveBtn.disabled = true;
  saveBtn.innerHTML = '<span class="spinner"></span> Saving…';

  const payload = {
    name:          $('#field-name').value.trim(),
    post_id:       $('#field-post-id').value.trim(),
    keywords:      $('#field-keywords').value.trim(),
    comment_reply: $('#field-comment-reply').value.trim(),
    dm_message:    $('#field-dm-message').value.trim(),
    is_active:     true,
  };

  try {
    if (editingCampaignId) {
      await apiFetch(`/api/campaigns/${editingCampaignId}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      showToast('Campaign updated!', 'success');
    } else {
      await apiFetch('/api/campaigns', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      showToast('Campaign created!', 'success');
    }
    closeModal();
    loadCampaigns();
    refreshStats();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  } finally {
    saveBtn.disabled = false;
    saveBtn.innerHTML = '💾 Save Campaign';
  }
});

// ----------------------------------------------------------------
// Init
// ----------------------------------------------------------------

(function init() {
  navigate('campaigns');
  loadCampaigns();
  loadSettings();
  refreshStats();
})();
