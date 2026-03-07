/**
 * dashboard.js — UGC Video Pro Frontend
 * Full 4-panel UGC form with:
 *   - Multi-image product upload grid
 *   - Presenter image/video upload
 *   - Chip-based creative settings
 *   - Timeline preview (live segment status)
 *   - Granular stage progress bar
 */

const API = '/api';
const STAGES = [
  { key: 'analyzing_product',   label: '商品分析' },
  { key: 'analyzing_presenter', label: '主播分析' },
  { key: 'planning_script',     label: '生成脚本' },
  { key: 'generating_voice',    label: '口播音频' },
  { key: 'generating_a_roll',   label: 'A-roll' },
  { key: 'generating_b_roll',   label: 'B-roll' },
  { key: 'compositing',         label: '合成' },
  { key: 'rendering_subtitles', label: '字幕' },
  { key: 'qa_review',           label: '质检' },
  { key: 'completed',           label: '完成' },
];

// ── State ─────────────────────────────────────────────────────────────────────
const AUTH_KEYS = {
  legacy: 'token',
  access: 'ugcvp_access_token',
  refresh: 'ugcvp_refresh_token',
};

function getStoredAccessToken() {
  return localStorage.getItem(AUTH_KEYS.access) || localStorage.getItem(AUTH_KEYS.legacy) || '';
}

function setStoredTokens(accessToken, refreshToken = '') {
  if (accessToken) {
    localStorage.setItem(AUTH_KEYS.access, accessToken);
    localStorage.setItem(AUTH_KEYS.legacy, accessToken); // backward compat
  }
  if (refreshToken) {
    localStorage.setItem(AUTH_KEYS.refresh, refreshToken);
  }
}

function clearStoredTokens() {
  localStorage.removeItem(AUTH_KEYS.access);
  localStorage.removeItem(AUTH_KEYS.legacy);
  localStorage.removeItem(AUTH_KEYS.refresh);
}

let _token = getStoredAccessToken();
let _ws = null;
let _activeTaskId = null;
let _completedStages = new Set();
let _currentStage = null;
let _currentUser = null;

// Uploaded file references
let _productFiles = new Array(9).fill(null); // index 0 = primary
let _presenterImage = null;
let _presenterVideo = null;

// Chip selection state
const _chipValues = {
  persona_template: 'energetic_female',
  language: 'it',
  platform: 'douyin',
  hook_style: 'result_first',
  tone_style: 'authentic_friend',
  cta_style: 'link_in_bio',
};

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  _token = getStoredAccessToken();
  if (_token) { await routeAfterLogin({ initialLoad: true }); }
  else showAuth();
});


// ── Auth ──────────────────────────────────────────────────────────────────────


async function routeAfterLogin({ initialLoad = false } = {}) {
  if (!_token) {
    showAuth();
    return;
  }
  try {
    const res = await fetch(`${API}/auth/landing`, {
      headers: { Authorization: `Bearer ${_token}` }
    });
    if (!res.ok) throw new Error('landing');
    const landing = await res.json();
    const target = landing?.target || '/index.html';
    const currentPath = location.pathname || '/index.html';
    const isIndex = currentPath === '/' || currentPath.endsWith('/index.html');
    if (!isIndex && initialLoad) return;
    if (target.endsWith('/admin.html') || target === '/admin.html') {
      location.href = '/admin.html';
      return;
    }
    if (target.endsWith('/animation-studio.html') || target === '/animation-studio.html') {
      location.href = '/animation-studio.html';
      return;
    }
  } catch (err) {
    console.warn('landing route failed', err);
  }
  await showMain();
}

function showAuth() {
  document.getElementById('auth-screen').style.display = '';
  document.getElementById('main-screen').style.display = 'none';
}

async function loadCurrentUser() {
  const navUser = document.getElementById('nav-user');
  const adminLink = document.getElementById('nav-admin-link');
  const adminInline = document.getElementById('nav-admin-inline');
  if (!_token) {
    if (navUser) navUser.textContent = '未登录';
    adminLink?.classList.add('hidden');
    adminInline?.classList.add('hidden');
    return;
  }
  try {
    const res = await fetch(`${API}/auth/me`, {
      headers: { Authorization: `Bearer ${_token}` }
    });
    if (!res.ok) throw new Error('profile');
    _currentUser = await res.json();
    if (navUser) {
      const label = _currentUser.display_name || _currentUser.email || '已登录';
      navUser.textContent = `${label}${_currentUser.role === 'admin' ? ' · 管理员' : ''}`;
    }
    const showAdmin = _currentUser?.role === 'admin';
    if (showAdmin) {
      adminLink?.classList.remove('hidden');
      adminInline?.classList.remove('hidden');
    } else {
      adminLink?.classList.add('hidden');
      adminInline?.classList.add('hidden');
    }
  } catch {
    _currentUser = null;
    if (navUser) navUser.textContent = '已登录';
    adminLink?.classList.add('hidden');
    adminInline?.classList.add('hidden');
  }
}


async function showMain() {
  document.getElementById('auth-screen').style.display = 'none';
  document.getElementById('main-screen').style.display = '';
  initProductGrid();
  initPresenterUploads();
  await loadCurrentUser();
  loadPresets();
  loadTasks();
}

document.getElementById('login-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const email = document.getElementById('login-email').value;
  const pass  = document.getElementById('login-pass').value;
  const errEl = document.getElementById('login-error');
  try {
    const r = await fetch(`${API}/auth/login`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ email, password: pass }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || '登录失败');
    const data = await r.json();
    _token = data.access_token;
    setStoredTokens(_token, data.refresh_token || '');
    errEl.style.display = 'none';
    await routeAfterLogin();
  } catch(err) {
    errEl.textContent = err.message;
    errEl.style.display = '';
  }
});

document.getElementById('register-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const email = document.getElementById('reg-email').value;
  const pass  = document.getElementById('reg-pass').value;
  const code  = document.getElementById('reg-code').value;
  const errEl = document.getElementById('reg-error');
  try {
    const r = await fetch(`${API}/auth/register`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ email, password: pass, invite_code: code }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || '注册失败');
    const data = await r.json();
    _token = data.access_token;
    setStoredTokens(_token, data.refresh_token || '');
    errEl.style.display = 'none';
    await routeAfterLogin();
  } catch(err) {
    errEl.textContent = err.message;
    errEl.style.display = '';
  }
});

document.getElementById('btn-logout')?.addEventListener('click', () => {
  _token = null;
  _currentUser = null;
  clearStoredTokens();
  showAuth();
  loadCurrentUser();
});

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const target = tab.dataset.tab;
    document.getElementById('login-form').style.display  = target === 'login'    ? '' : 'none';
    document.getElementById('register-form').style.display = target === 'register' ? '' : 'none';
  });
});

// ── Product image grid ────────────────────────────────────────────────────────
function initProductGrid() {
  const grid = document.getElementById('product-grid');
  grid.innerHTML = '';
  const labels = ['主图★', '细节', '细节', '使用', '使用', '包装', '包装', '其他', '其他'];
  for (let i = 0; i < 9; i++) {
    const slot = document.createElement('div');
    slot.className = 'img-slot' + (i === 0 ? ' primary' : '');
    slot.dataset.index = i;
    slot.innerHTML = `
      <span class="slot-label">${labels[i]}</span>
      <input type="file" accept="image/*" id="pslot-${i}">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      <img id="pslot-img-${i}" alt="">
    `;
    slot.addEventListener('click', e => {
      if (e.target.tagName !== 'INPUT') slot.querySelector('input').click();
    });
    slot.querySelector('input').addEventListener('change', e => {
      const file = e.target.files[0];
      if (!file) return;
      _productFiles[i] = file;
      const img = document.getElementById(`pslot-img-${i}`);
      img.src = URL.createObjectURL(file);
      slot.classList.add('has-file');
    });
    // drag support
    slot.addEventListener('dragover', e => { e.preventDefault(); slot.classList.add('drag-over'); });
    slot.addEventListener('dragleave', () => slot.classList.remove('drag-over'));
    slot.addEventListener('drop', e => {
      e.preventDefault();
      slot.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (!file || !file.type.startsWith('image/')) return;
      _productFiles[i] = file;
      const img = document.getElementById(`pslot-img-${i}`);
      img.src = URL.createObjectURL(file);
      slot.classList.add('has-file');
    });
    grid.appendChild(slot);
  }
}

// ── Presenter uploads ─────────────────────────────────────────────────────────
function initPresenterUploads() {
  document.getElementById('pimg-input').addEventListener('change', e => {
    const f = e.target.files[0];
    if (!f) return;
    _presenterImage = f;
    document.getElementById('pimg-name').textContent = f.name;
    document.getElementById('pimg-box').classList.add('has-file');
  });
  document.getElementById('pvid-input').addEventListener('change', e => {
    const f = e.target.files[0];
    if (!f) return;
    _presenterVideo = f;
    document.getElementById('pvid-name').textContent = f.name;
    document.getElementById('pvid-box').classList.add('has-file');
  });
}

// ── Load presets from API ─────────────────────────────────────────────────────
async function loadPresets() {
  try {
    const r = await authFetch(`${API}/video/presets`);
    if (!r.ok) return;
    const data = await r.json();

    renderChips('persona-chips', data.personas, 'key', 'name', 'persona_template');
    renderChips('platform-chips', data.platforms, 'key', 'name', 'platform');
    renderChips('hook-chips', data.hook_styles, 'key', 'name', 'hook_style');
    renderChips('tone-chips', data.tone_styles, 'key', 'name', 'tone_style');
    renderChips('cta-chips', data.cta_styles, 'key', 'name', 'cta_style');
  } catch(e) {
    console.warn('Presets load failed:', e);
    // Fallback static chips
    _renderStaticChips();
  }
}

function renderChips(containerId, items, keyField, nameField, stateField) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';
  items.forEach((item, i) => {
    const chip = document.createElement('div');
    chip.className = 'chip' + (item[keyField] === _chipValues[stateField] || (!_chipValues[stateField] && i === 0) ? ' active' : '');
    chip.dataset.value = item[keyField];
    chip.textContent = item[nameField];
    chip.title = item.description || '';
    chip.addEventListener('click', () => {
      container.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      _chipValues[stateField] = item[keyField];
    });
    container.appendChild(chip);
  });
}

function _renderStaticChips() {
  const fallbacks = {
    'persona-chips': [
      {key:'energetic_female',name:'活力女生'},{key:'girlfriend_recommendation',name:'闺蜜种草'},
      {key:'review_blogger',name:'测评博主'},{key:'bao_ma_recommendation',name:'宝妈推荐'},
    ],
    'platform-chips': [
      {key:'douyin',name:'抖音'},{key:'tiktok',name:'TikTok'},
      {key:'instagram',name:'Instagram'},{key:'youtube_shorts',name:'YouTube Shorts'},
    ],
    'hook-chips': [
      {key:'result_first',name:'结果先行'},{key:'pain_point',name:'问题打断'},
      {key:'curiosity_gap',name:'好奇缺口'},{key:'comparison_challenge',name:'对比挑战'},
    ],
    'tone-chips': [
      {key:'authentic_friend',name:'闺蜜推荐'},{key:'professional_expert',name:'专业讲解'},
      {key:'energetic_hype',name:'高能种草'},{key:'funny_relatable',name:'搞笑接地气'},
    ],
    'cta-chips': [
      {key:'link_in_bio',name:'主页链接'},{key:'buy_now',name:'立即购买'},
      {key:'limited_offer',name:'限时优惠'},{key:'comment_below',name:'评论区'},
    ],
  };
  const fields = { 'persona-chips':'persona_template','platform-chips':'platform','hook-chips':'hook_style','tone-chips':'tone_style','cta-chips':'cta_style' };
  for (const [id, items] of Object.entries(fallbacks)) {
    renderChips(id, items, 'key', 'name', fields[id]);
  }
}

// Language chips (static)
document.querySelectorAll('#voice-chips .chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('#voice-chips .chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    _chipValues['language'] = chip.dataset.value;
  });
});

// ── Form submit ───────────────────────────────────────────────────────────────
document.getElementById('ugc-form')?.addEventListener('submit', async e => {
  e.preventDefault();

  if (!_productFiles[0]) {
    showToast('请上传主图（第一张商品图片）', 'error');
    return;
  }

  const btn = document.getElementById('btn-generate');
  btn.disabled = true;
  btn.textContent = '⏳ 提交中...';

  try {
    const fd = new FormData();

    // Product images
    fd.append('primary_image', _productFiles[0]);
    for (let i = 1; i <= 3; i++) {
      if (_productFiles[i]) fd.append('gallery_images', _productFiles[i]);
    }
    for (let i = 4; i <= 8; i++) {
      if (_productFiles[i]) fd.append('usage_images', _productFiles[i]);
    }

    // Presenter
    if (_presenterImage) fd.append('presenter_image', _presenterImage);
    if (_presenterVideo) fd.append('presenter_video', _presenterVideo);

    // Text fields
    const textFields = ['product_url','product_description','brand_name','selling_points','target_audience'];
    textFields.forEach(id => {
      const el = document.getElementById(id.replace(/_/g, '-').replace('product-url','product-url'));
      // fallback id mapping
      const elAlt = document.getElementById(id);
      const val = (el || elAlt)?.value?.trim();
      if (val) fd.append(id, val);
    });

    // Creative params from chip state
    fd.append('duration',      document.getElementById('duration').value);
    fd.append('quality_tier',  document.getElementById('quality-tier').value);
    fd.append('language',      _chipValues.language);
    fd.append('platform',      _chipValues.platform);
    fd.append('persona_template', _chipValues.persona_template);
    fd.append('hook_style',    _chipValues.hook_style);
    fd.append('tone_style',    _chipValues.tone_style);
    fd.append('cta_style',     _chipValues.cta_style);
    fd.append('aspect_ratio',  '9:16');

    const r = await authFetch(`${API}/video/generate/ugc`, {
      method: 'POST', body: fd,
    });
    if (!r.ok) {
      const err = await r.json();
      throw new Error(err.detail || '提交失败');
    }
    const { task_id } = await r.json();
    _activeTaskId = task_id;
    showActiveTaskPanel();
    initStageBar();
    connectWebSocket(task_id);
    loadTasks();
    showToast('🚀 视频生产开始！', 'success');
  } catch(err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 开始生成带货视频';
  }
});

// ── Stage bar ─────────────────────────────────────────────────────────────────
function initStageBar() {
  _completedStages.clear();
  _currentStage = null;
  const bar = document.getElementById('stage-bar');
  bar.innerHTML = STAGES.map(s => `
    <div class="stage-item" id="stage-item-${s.key}">
      <div class="stage-dot" id="stage-dot-${s.key}"></div>
      <span class="stage-label" id="stage-lbl-${s.key}">${s.label}</span>
    </div>
  `).join('');
}

function updateStageBar(stage) {
  if (!stage) return;
  if (_currentStage && _currentStage !== stage) {
    _completedStages.add(_currentStage);
    const prevDot = document.getElementById(`stage-dot-${_currentStage}`);
    const prevLbl = document.getElementById(`stage-lbl-${_currentStage}`);
    if (prevDot) prevDot.className = 'stage-dot done';
    if (prevLbl) prevLbl.className = 'stage-label';
  }
  _currentStage = stage;
  const dot = document.getElementById(`stage-dot-${stage}`);
  const lbl = document.getElementById(`stage-lbl-${stage}`);
  if (dot) dot.className = 'stage-dot active';
  if (lbl) lbl.className = 'stage-label active';
}

// ── WebSocket progress ────────────────────────────────────────────────────────
function connectWebSocket(taskId) {
  if (_ws) { _ws.close(); _ws = null; }
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  _ws = new WebSocket(`${proto}://${location.host}/api/ws/progress/${taskId}?token=${encodeURIComponent(_token || getStoredAccessToken())}`);

  _ws.addEventListener('message', e => {
    const msg = JSON.parse(e.data);
    if (msg.stage) {
      updateStageBar(msg.stage);
      const msgEl = document.getElementById('stage-message');
      if (msgEl && msg.stage_message) msgEl.textContent = msg.stage_message;
    }
    if (msg.status === 'completed') {
      markAllStagesDone();
      showResultCard(msg);
      _ws.close();
    }
    if (msg.status === 'failed') {
      showToast('生成失败: ' + (msg.error || '未知错误'), 'error');
      _ws.close();
    }
    // Reload timeline preview when script is done
    if (msg.stage === 'generating_voice' || msg.stage === 'generating_a_roll') {
      loadTimelinePreview(taskId);
    }
    loadTasks();
  });

  _ws.addEventListener('error', () => showToast('WebSocket 连接错误', 'error'));
}

function markAllStagesDone() {
  STAGES.forEach(s => {
    const dot = document.getElementById(`stage-dot-${s.key}`);
    const lbl = document.getElementById(`stage-lbl-${s.key}`);
    if (dot) dot.className = 'stage-dot done';
    if (lbl) lbl.className = 'stage-label';
  });
}

// ── Timeline preview ──────────────────────────────────────────────────────────
async function loadTimelinePreview(taskId) {
  try {
    const r = await authFetch(`${API}/video/tasks/${taskId}/timeline`);
    if (!r.ok) return;
    const data = await r.json();
    renderTimelinePreview(data);
  } catch(e) { /* not ready yet */ }
}

function renderTimelinePreview(data) {
  const wrap = document.getElementById('timeline-preview');
  if (!wrap) return;
  wrap.style.display = '';
  const trackClass = { a_roll: 'track-a', b_roll: 'track-b', overlay: 'track-o' };
  const trackLabel = { a_roll: 'A-roll', b_roll: 'B-roll', overlay: 'Overlay' };
  wrap.innerHTML = data.segments.map(seg => `
    <div class="timeline-row">
      <div class="timeline-track ${trackClass[seg.track_type] || ''}">${trackLabel[seg.track_type] || seg.track_type}</div>
      <div class="timeline-spoken">${seg.spoken_line || seg.overlay_text || '—'}</div>
      <div class="timeline-dur">${(+seg.duration).toFixed(1)}s</div>
      <div class="timeline-status-dot ${seg.status}"></div>
    </div>
  `).join('');
}

// ── Active task panel ─────────────────────────────────────────────────────────
function showActiveTaskPanel() {
  document.getElementById('active-task-card').style.display = '';
  document.getElementById('result-card').style.display = 'none';
}

function showResultCard(msg) {
  document.getElementById('active-task-card').style.display = 'none';
  const card = document.getElementById('result-card');
  card.style.display = '';

  if (msg.result_filename) {
    const taskId = _activeTaskId;
    const videoUrl = `${API}/video/download/${taskId}`;
    const vid = document.getElementById('result-video');
    vid.src = videoUrl;
    const dl = document.getElementById('btn-download');
    dl.href = videoUrl;
    dl.download = msg.result_filename;
  }
  if (msg.drive_link) {
    const driveBtn = document.getElementById('btn-drive-link');
    driveBtn.href = msg.drive_link;
    driveBtn.style.display = '';
  }
  if (msg.qa_passed !== undefined) {
    document.getElementById('qa-report').textContent =
      msg.qa_passed ? '✅ 质检通过' : '⚠️ 质检警告，请查看视频';
  }
}

// ── Task list ─────────────────────────────────────────────────────────────────
async function loadTasks() {
  try {
    const r = await authFetch(`${API}/video/tasks?page=1&page_size=15`);
    if (!r.ok) return;
    const data = await r.json();
    renderTaskList(data.items);
  } catch(e) { console.warn('Task list error:', e); }
}

function renderTaskList(tasks) {
  const el = document.getElementById('task-list');
  if (!tasks.length) {
    el.innerHTML = '<div class="empty-state">暂无任务</div>';
    return;
  }
  const statusIcon = { pending:'⏳', processing:'⚙️', completed:'✅', failed:'❌' };
  el.innerHTML = tasks.map(t => `
    <div class="task-row ${t.id === _activeTaskId ? 'task-row--active' : ''}" data-id="${t.id}">
      <div class="task-icon">${statusIcon[t.status] || '📹'}</div>
      <div class="task-info">
        <div class="task-name">${t.mode} · ${t.duration}s · ${t.language}</div>
        <div class="task-meta">${t.platform || ''} ${t.persona_template || ''} <span class="task-status status-${t.status}">${t.status}</span></div>
      </div>
      <div class="task-actions">
        ${t.status === 'completed' ? `<a href="${API}/video/download/${t.id}" class="btn btn-ghost btn-xs" download>⬇</a>` : ''}
        ${t.status === 'processing' ? `<button class="btn btn-ghost btn-xs" onclick="resumeTask('${t.id}')">👁</button>` : ''}
      </div>
    </div>
  `).join('');
}

function resumeTask(taskId) {
  _activeTaskId = taskId;
  showActiveTaskPanel();
  initStageBar();
  connectWebSocket(taskId);
  loadTimelinePreview(taskId);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function authFetch(url, opts = {}) {
  return fetch(url, {
    ...opts,
    headers: {
      ...opts.headers,
      'Authorization': `Bearer ${_token}`,
    },
  });
}

function showToast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

// Refresh task list every 10s while page open
setInterval(() => { if (_token) loadTasks(); }, 10000);
