/**
 * js/dashboard.js
 * Main dashboard logic for UGC Video Pro
 * Wizard rewritten for 3-step flow with auto-mode detection and quality tiers.
 * All non-wizard functions (navigation, sidebar, video tasks, settings, modals, etc.)
 * are kept exactly as the original.
 */

const Dashboard = (() => {
  'use strict';

  // ── Constants ─────────────────────────────────────────────

  const MODEL_MAX_DURATIONS = {
    veo_31_fast:    8,
    veo_31_quality: 8,
    seedance_15:   10,
    seedance_2:    10,
    sora_2:        10,
    runway:        10,
    kling_30:      10,
    hailuo:         6,
  };

  const MODEL_DISPLAY_NAMES = {
    veo_31_fast:    'Veo 3.1 Fast',
    veo_31_quality: 'Veo 3.1 Quality',
    seedance_15:    'Seedance 1.5 Pro',
    seedance_2:     'Seedance 2.0',
    sora_2:         'Sora 2',
    runway:         'Runway',
    kling_30:       'Kling 3.0',
    hailuo:         'Hailuo 2.3',
  };

  const MODE_DISPLAY_NAMES = {
    image_to_video: '图片转视频',
    text_to_video:  '文字转视频',
    url_to_video:   'URL参考转视频',
  };

  const LANG_DISPLAY_NAMES = {
    zh: '中文',
    en: 'English',
    it: 'Italiano',
  };

  const STATUS_LABELS = {
    pending:    { text: '等待中',  cls: 'badge-pending'    },
    processing: { text: '生成中',  cls: 'badge-processing' },
    completed:  { text: '已完成',  cls: 'badge-completed'  },
    failed:     { text: '失败',    cls: 'badge-failed'     },
  };

  const SECTION_TITLES = {
    'new-video':     '新建视频',
    'my-videos':     '我的视频',
    'settings':      '设置',
    'admin-users':   '用户管理',
    'admin-invites': '邀请码管理',
  };

  // New 3-step wizard labels
  const STEP_LABELS = ['上传内容', '输出设置', '确认生成'];

  // Quality tiers → auto-select model
  const QUALITY_TIERS = {
    economy: { model: 'seedance_15',    label: '经济版',     desc: '高性价比 · Seedance 1.5',    price: '~$0.035/片段' },
    premium: { model: 'veo_31_quality', label: '高质量版',   desc: '最佳画质 · Veo 3.1 Quality', price: '~$1.25/片段'  },
    china:   { model: 'kling_30',       label: '中国市场版', desc: '含原生音频 · Kling 3.0',     price: '特价'         },
  };

  // Pipeline stages for progress tracking
  const PIPELINE_STAGES = [
    { key: 'analyzing_image',   label: '分析图片', icon: '🔍' },
    { key: 'extracting_url',    label: '提取URL',  icon: '🔗' },
    { key: 'generating_script', label: '生成脚本', icon: '📝' },
    { key: 'generating_video',  label: '生成视频', icon: '🎬' },
    { key: 'generating_tts',    label: 'TTS语音',  icon: '🔊' },
    { key: 'lipsync',           label: '唇形同步', icon: '💋' },
    { key: 'stitching',         label: '拼接合成', icon: '🎞️' },
  ];

  // ── State ─────────────────────────────────────────────────

  let currentUser  = null;
  let currentStep  = 1;
  const totalSteps = 3;  // wizard indicator shows 3 steps; progress view is step 4 (hidden from indicator)

  // Multi-image array: each entry is a File object; index 0 = primary
  const wizardData = {
    images:       [],    // Array<File> up to 5; index 0 = primary
    productUrl:   null,
    textPrompt:   null,
    duration:     null,
    languages:    ['it'], // multi-select, default Italian
    qualityTier:  null,
    model:        null,   // resolved from tier or manual
    manualModel:  null,   // set when user picks from advanced panel
  };

  // Progress/task state
  let activeProgressTaskId = null;
  let activeProgressWs     = null;

  let videoTasksPage  = 1;
  let videoTasksTotal = 0;
  let videosViewMode  = 'list'; // 'list' | 'grid'
  let activeWebSockets = {};    // taskId → wsInstance
  let videoRefreshTimer = null;
  let pendingDeleteId  = null;

  // ── Toast ─────────────────────────────────────────────────

  function showToast(type, title, message) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
      success: `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="8" stroke="#22c55e" stroke-width="1.5"/><path d="M5.5 9l2.5 2.5 4.5-5" stroke="#22c55e" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
      error:   `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="8" stroke="#ef4444" stroke-width="1.5"/><path d="M9 5v4M9 12v.5" stroke="#ef4444" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      warning: `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 2L17 16H1L9 2Z" stroke="#f59e0b" stroke-width="1.5" stroke-linejoin="round"/><path d="M9 7v4M9 13v.5" stroke="#f59e0b" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      info:    `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="8" stroke="#3b82f6" stroke-width="1.5"/><path d="M9 8v5M9 5.5v.5" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round"/></svg>`,
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <div class="toast-icon">${icons[type] || icons.info}</div>
      <div class="toast-body">
        <div class="toast-title">${escapeHtml(title)}</div>
        ${message ? `<div class="toast-message">${escapeHtml(message)}</div>` : ''}
      </div>
    `;
    container.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('leaving');
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }

  // ── Utility ─────────────────────────────────────────────────

  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function formatDate(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  }

  function getInitials(name) {
    if (!name) return 'U';
    return name.trim().charAt(0).toUpperCase();
  }

  // ── Navigation ─────────────────────────────────────────────────

  function navigate(sectionName) {
    window.location.hash = sectionName;
    activateSection(sectionName);
  }

  function activateSection(sectionName) {
    // Update sidebar nav
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.toggle('active', item.dataset.section === sectionName);
    });

    // Show/hide page sections
    document.querySelectorAll('.page-section').forEach(section => {
      section.classList.remove('active');
    });

    const target = document.getElementById(`section-${sectionName}`);
    if (target) target.classList.add('active');

    // Update header title
    const titleEl = document.getElementById('headerTitle');
    if (titleEl) titleEl.textContent = SECTION_TITLES[sectionName] || '';

    // Load section-specific data
    if (sectionName === 'my-videos') {
      loadVideoTasks(1);
    } else if (sectionName === 'settings') {
      loadSettings();
    } else if (sectionName === 'admin-users') {
      Admin.loadUsers();
    } else if (sectionName === 'admin-invites') {
      Admin.loadInviteCodes();
    }

    // Close mobile sidebar
    closeMobileSidebar();
  }

  // ── Sidebar ─────────────────────────────────────────────────

  function initSidebar() {
    const sidebar   = document.getElementById('sidebar');
    const toggle    = document.getElementById('sidebarToggle');
    const hamburger = document.getElementById('hamburger');
    const backdrop  = document.getElementById('sidebarBackdrop');

    // Desktop collapse/expand
    if (toggle) {
      toggle.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        toggle.innerHTML = isCollapsed
          ? `<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M5 2L10 7L5 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`
          : `<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M9 2L4 7L9 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      });
    }

    // Mobile hamburger
    if (hamburger) {
      hamburger.addEventListener('click', () => {
        sidebar.classList.add('mobile-open');
        backdrop.classList.add('visible');
      });
    }

    // Close on backdrop click
    if (backdrop) {
      backdrop.addEventListener('click', closeMobileSidebar);
    }

    // Nav item clicks
    document.querySelectorAll('.nav-item[data-section]').forEach(item => {
      item.addEventListener('click', () => navigate(item.dataset.section));
      item.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          navigate(item.dataset.section);
        }
      });
    });

    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => {
        API.logout();
      });
    }
  }

  function closeMobileSidebar() {
    const sidebar  = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (sidebar)  sidebar.classList.remove('mobile-open');
    if (backdrop) backdrop.classList.remove('visible');
  }

  // ── User Profile ────────────────────────────────────────────────

  async function loadUserProfile() {
    try {
      currentUser = await API.getMe();

      const avatarEl  = document.getElementById('userAvatar');
      const nameEl    = document.getElementById('userName');
      const roleBadge = document.getElementById('userRoleBadge');

      if (avatarEl) avatarEl.textContent = getInitials(currentUser.display_name);
      if (nameEl)   nameEl.textContent   = currentUser.display_name || currentUser.email;
      if (roleBadge) {
        roleBadge.textContent = currentUser.role === 'admin' ? '管理员' : '用户';
        roleBadge.className   = `badge ${currentUser.role === 'admin' ? 'badge-admin' : 'badge-user'}`;
      }

      // Show admin nav items
      if (currentUser.role === 'admin') {
        document.querySelectorAll('.admin-only').forEach(el => {
          el.style.display = '';
        });
      }

    } catch (err) {
      console.error('Failed to load user profile:', err);
    }
  }

  // ══════════════════════════════════════════════════════════
  // ── WIZARD (Rewritten: 3 steps + progress view) ──────────
  // ══════════════════════════════════════════════════════════

  function initWizard() {
    renderStepsHeader();
    initImageUploadGrid();
    bindStep1();
    bindStep2();
    bindStep3();
    renderPipelineStages();
    bindProgressView();
  }

  // ── Step indicator (only 3 steps shown) ──

  function renderStepsHeader() {
    const container = document.getElementById('wizardStepsHeader');
    if (!container) return;
    container.innerHTML = '';

    STEP_LABELS.forEach((label, idx) => {
      const stepNum = idx + 1;

      if (idx > 0) {
        const connector = document.createElement('div');
        connector.className = `step-connector${stepNum <= currentStep ? ' filled' : ''}`;
        connector.id = `stepConnector${stepNum}`;
        container.appendChild(connector);
      }

      const dot = document.createElement('div');
      dot.className = `wizard-step-dot${stepNum < currentStep ? ' completed' : stepNum === currentStep ? ' active' : ''}`;
      dot.id = `stepDot${stepNum}`;
      dot.innerHTML = `
        <div class="step-dot-circle">${stepNum < currentStep ? '✓' : stepNum}</div>
        <div class="step-dot-label">${label}</div>
      `;
      container.appendChild(dot);
    });
  }

  function updateStepUI() {
    STEP_LABELS.forEach((_, idx) => {
      const stepNum = idx + 1;
      const dot = document.getElementById(`stepDot${stepNum}`);
      if (!dot) return;
      dot.className = `wizard-step-dot${stepNum < currentStep ? ' completed' : stepNum === currentStep ? ' active' : ''}`;
      dot.querySelector('.step-dot-circle').textContent = stepNum < currentStep ? '✓' : stepNum;

      if (stepNum > 1) {
        const connector = document.getElementById(`stepConnector${stepNum}`);
        if (connector) connector.className = `step-connector${stepNum <= currentStep ? ' filled' : ''}`;
      }
    });

    const bar = document.getElementById('wizardProgressBar');
    if (bar) bar.style.width = `${(Math.min(currentStep, totalSteps) / totalSteps) * 100}%`;

    const numEl = document.getElementById('currentStepNum');
    if (numEl) numEl.textContent = Math.min(currentStep, totalSteps);

    // Hide progress indicator when in progress view (step 4)
    const progressArea = document.getElementById('wizardProgressArea');
    if (progressArea) {
      progressArea.style.display = currentStep === 4 ? 'none' : '';
    }
  }

  function showStep(step) {
    // Steps 1-4 (4 = progress view, not in indicator)
    for (let i = 1; i <= 4; i++) {
      const el = document.getElementById(`wizardStep${i}`);
      if (el) el.style.display = i === step ? 'block' : 'none';
    }
    currentStep = step;
    updateStepUI();
    document.querySelector('.wizard-container')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ── Step 1: Upload Product Content ──

  function initImageUploadGrid() {
    const grid = document.getElementById('imageUploadGrid');
    if (!grid) return;
    grid.innerHTML = '';

    for (let i = 0; i < 5; i++) {
      const slot = document.createElement('div');
      slot.className = 'upload-slot' + (i === 0 ? ' primary' : '');
      slot.id = `uploadSlot${i}`;
      slot.tabIndex = 0;
      slot.setAttribute('role', 'button');
      slot.setAttribute('aria-label', i === 0 ? '上传主图（必填）' : `上传附图 ${i}`);

      slot.innerHTML = `
        ${i === 0 ? '<span class="slot-label">主图</span>' : ''}
        <input type="file" accept="image/jpeg,image/png,image/webp" style="display:none;" id="slotInput${i}">
        <img src="" alt="预览" id="slotImg${i}">
        <span class="slot-add-icon">${i === 0 ? '🖼' : '＋'}</span>
        <span class="slot-add-text" style="font-size:10px;color:var(--text-muted);">${i === 0 ? '上传主图' : '添加图片'}</span>
        <button class="slot-remove" id="slotRemove${i}" title="移除图片" tabindex="-1">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M1 1l8 8M9 1L1 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </button>
      `;

      grid.appendChild(slot);
      bindSlot(slot, i);
    }
  }

  function bindSlot(slot, idx) {
    const input     = document.getElementById(`slotInput${idx}`);
    const removeBtn = document.getElementById(`slotRemove${idx}`);
    const img       = document.getElementById(`slotImg${idx}`);

    // Click slot → open file picker (but not if clicking remove button)
    slot.addEventListener('click', (e) => {
      if (e.target === removeBtn || removeBtn.contains(e.target)) return;
      input.click();
    });
    slot.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
    });

    // Drag & drop
    slot.addEventListener('dragover', (e) => { e.preventDefault(); slot.classList.add('drag-over'); });
    slot.addEventListener('dragleave', () => slot.classList.remove('drag-over'));
    slot.addEventListener('drop', (e) => {
      e.preventDefault();
      slot.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) handleSlotFile(idx, file, img, slot);
    });

    // File input change
    input.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) handleSlotFile(idx, file, img, slot);
      input.value = '';
    });

    // Remove
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      clearSlot(idx, img, slot);
    });
  }

  function handleSlotFile(idx, file, img, slot) {
    if (!file.type.startsWith('image/')) {
      showToast('error', '文件类型错误', '请上传 JPG、PNG 或 WebP 图片');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      showToast('error', '图片过大', '最大支持 20MB');
      return;
    }

    // CRITICAL: store original File object without modification to preserve quality
    wizardData.images[idx] = file;

    const reader = new FileReader();
    reader.onload = (e) => {
      img.src = e.target.result;
      slot.classList.add('has-file');
    };
    reader.readAsDataURL(file);

    updateStep1State();
  }

  function clearSlot(idx, img, slot) {
    wizardData.images[idx] = undefined;
    img.src = '';
    slot.classList.remove('has-file');
    updateStep1State();
  }

  function detectMode() {
    const hasImages = wizardData.images.filter(Boolean).length > 0;
    const hasUrl    = !!(document.getElementById('productUrl')?.value?.trim());
    if (hasUrl && hasImages) return 'url_to_video';
    if (hasImages)           return 'image_to_video';
    return 'text_to_video';
  }

  function updateStep1State() {
    const hasImages  = wizardData.images.filter(Boolean).length > 0;
    const hasText    = (document.getElementById('productText')?.value?.trim()?.length || 0) > 5;
    const isValid    = hasImages || hasText;

    document.getElementById('step1Next').disabled = !isValid;

    // Update auto-mode badge
    const indicator = document.getElementById('autoModeIndicator');
    const badge     = document.getElementById('autoModeBadge');
    const modeText  = document.getElementById('autoModeText');

    if (isValid) {
      const mode = detectMode();
      indicator.style.display = 'block';
      modeText.textContent    = `自动模式: ${MODE_DISPLAY_NAMES[mode] || mode}`;
    } else {
      indicator.style.display = 'none';
    }
  }

  function bindStep1() {
    // Watch text/URL inputs to update validity
    document.getElementById('productText')?.addEventListener('input', updateStep1State);
    document.getElementById('productUrl')?.addEventListener('input', updateStep1State);

    document.getElementById('step1Next').addEventListener('click', () => {
      const hasImages = wizardData.images.filter(Boolean).length > 0;
      const hasText   = (document.getElementById('productText')?.value?.trim()?.length || 0) > 5;
      if (hasImages || hasText) {
        showStep(2);
      }
    });
  }

  // ── Step 2: Configure Output ──

  function bindStep2() {
    // Duration preset buttons
    document.querySelectorAll('.duration-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        wizardData.duration = parseInt(btn.dataset.val, 10);
        document.getElementById('customDuration').value = '';
        checkStep2Valid();
      });
    });

    // Custom duration
    document.getElementById('applyCustomDuration')?.addEventListener('click', () => {
      const val = parseInt(document.getElementById('customDuration').value, 10);
      const errEl = document.getElementById('customDurationError');
      if (!val || val < 1) {
        errEl.textContent = '请输入有效的秒数（最少1秒）';
        errEl.classList.add('visible');
        return;
      }
      errEl.classList.remove('visible');
      document.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('selected'));
      wizardData.duration = val;
      showToast('success', '时长已设置', `${val} 秒`);
      checkStep2Valid();
    });

    document.getElementById('customDuration')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') document.getElementById('applyCustomDuration').click();
    });
    document.getElementById('customDuration')?.addEventListener('input', () => {
      const errEl = document.getElementById('customDurationError');
      if (errEl) errEl.classList.remove('visible');
    });

    // Language checkboxes
    document.querySelectorAll('input[name="lang"]').forEach(cb => {
      cb.addEventListener('change', () => {
        const checked = Array.from(document.querySelectorAll('input[name="lang"]:checked')).map(c => c.value);
        wizardData.languages = checked.length > 0 ? checked : ['it'];
        // Re-check at least one
        if (checked.length === 0) {
          document.getElementById('langIt').checked = true;
          wizardData.languages = ['it'];
        }
        checkStep2Valid();
      });
    });

    // Quality tier cards
    document.querySelectorAll('[data-tier]').forEach(card => {
      card.addEventListener('click', () => {
        document.querySelectorAll('[data-tier]').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        wizardData.qualityTier = card.dataset.tier;
        wizardData.manualModel = null;
        // Deselect any advanced model
        document.querySelectorAll('#advancedModelGrid [data-model]').forEach(c => c.classList.remove('selected'));
        checkStep2Valid();
      });
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); card.click(); }
      });
    });

    // Advanced model toggle
    const advancedToggleBtn = document.getElementById('advancedToggleBtn');
    const advancedWrap      = document.getElementById('advancedModelsWrap');
    if (advancedToggleBtn && advancedWrap) {
      advancedToggleBtn.addEventListener('click', () => {
        const isOpen = advancedWrap.classList.toggle('open');
        advancedToggleBtn.classList.toggle('open', isOpen);
        advancedToggleBtn.innerHTML = `
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
          ${isOpen ? '收起模型列表' : '展开全部模型（高级选项）'}
        `;
      });
    }

    // Advanced model cards (manual override)
    document.querySelectorAll('#advancedModelGrid [data-model]').forEach(card => {
      card.addEventListener('click', () => {
        document.querySelectorAll('#advancedModelGrid [data-model]').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        wizardData.manualModel  = card.dataset.model;
        wizardData.qualityTier  = null;
        // Deselect tier cards
        document.querySelectorAll('[data-tier]').forEach(c => c.classList.remove('selected'));
        checkStep2Valid();
      });
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); card.click(); }
      });
    });

    document.getElementById('step2Back').addEventListener('click', () => showStep(1));
    document.getElementById('step2Next').addEventListener('click', () => {
      if (checkStep2Valid()) {
        buildSummary();
        showStep(3);
      }
    });
  }

  function checkStep2Valid() {
    const checkedLangs = Array.from(document.querySelectorAll('input[name="lang"]:checked'));
    const hasDuration  = !!wizardData.duration;
    const hasLang      = checkedLangs.length > 0;
    const hasModel     = !!(wizardData.qualityTier || wizardData.manualModel);

    const valid = hasDuration && hasLang && hasModel;
    const nextBtn = document.getElementById('step2Next');
    if (nextBtn) nextBtn.disabled = !valid;
    return valid;
  }

  // Resolve final model from tier or manual selection
  function resolveModel() {
    if (wizardData.manualModel) return wizardData.manualModel;
    if (wizardData.qualityTier) return QUALITY_TIERS[wizardData.qualityTier]?.model || 'seedance_15';
    return 'seedance_15';
  }

  // ── Step 3: Confirm & Generate ──

  function buildSummary() {
    const grid = document.getElementById('summaryGrid');
    if (!grid) return;

    const model    = resolveModel();
    const maxClip  = MODEL_MAX_DURATIONS[model] || 8;
    const segments = Math.ceil((wizardData.duration || 30) / maxClip);

    // Collect current languages from checkboxes
    const checkedLangs = Array.from(document.querySelectorAll('input[name="lang"]:checked')).map(c => c.value);
    wizardData.languages = checkedLangs.length > 0 ? checkedLangs : ['it'];

    // Collect current text/URL
    wizardData.textPrompt = document.getElementById('productText')?.value?.trim() || null;
    wizardData.productUrl = document.getElementById('productUrl')?.value?.trim()  || null;

    const mode    = detectMode();
    const tierKey = wizardData.qualityTier;
    const tierLabel = tierKey ? `${QUALITY_TIERS[tierKey].label} (${QUALITY_TIERS[tierKey].desc})` : '手动选择';
    const langDisplay = wizardData.languages.map(l => LANG_DISPLAY_NAMES[l] || l).join(' / ');

    const imageCount = wizardData.images.filter(Boolean).length;

    const rows = [
      { label: '生成模式', value: MODE_DISPLAY_NAMES[mode] || mode },
      { label: '质量等级', value: tierLabel },
      { label: '模型',     value: MODEL_DISPLAY_NAMES[model] || model },
      { label: '时长',     value: `${wizardData.duration} 秒` },
      { label: '片段数',   value: `${segments} 个片段（每段最长 ${maxClip}s）` },
      { label: '语言',     value: langDisplay },
    ];

    if (imageCount > 0) {
      rows.push({ label: '图片', value: `${imageCount} 张（主图: ${wizardData.images[0]?.name || '未知'}）` });
    }
    if (wizardData.productUrl) {
      rows.push({ label: '链接', value: wizardData.productUrl.slice(0, 60) + (wizardData.productUrl.length > 60 ? '…' : '') });
    }
    if (wizardData.textPrompt) {
      rows.push({ label: '描述', value: wizardData.textPrompt.slice(0, 80) + (wizardData.textPrompt.length > 80 ? '…' : '') });
    }

    // Cost estimate
    const tierPriceMap = { economy: '$0.04', premium: '$1.25', china: '特价' };
    const pricePerClip = tierKey ? tierPriceMap[tierKey] : '—';
    if (pricePerClip && pricePerClip !== '—') {
      rows.push({ label: '预估费用', value: `约 ${pricePerClip}/片段 × ${segments} 片段` });
    }

    grid.innerHTML = rows.map(r => `
      <div class="summary-row">
        <span class="summary-label">${escapeHtml(r.label)}</span>
        <span class="summary-value">${escapeHtml(r.value)}</span>
      </div>
    `).join('');
  }

  function bindStep3() {
    document.getElementById('step3Back').addEventListener('click', () => showStep(2));

    document.getElementById('startGenerateBtn').addEventListener('click', async () => {
      const btn = document.getElementById('startGenerateBtn');
      btn.disabled = true;
      btn.innerHTML = `<span class="btn-spinner"></span>提交中...`;

      try {
        const formData = buildFormData();
        const result   = await API.generateVideo(formData);

        showToast('success', '任务已提交', `任务 ID: ${result.task_id || '已创建'}`);

        // Navigate to progress view
        activeProgressTaskId = result.task_id;
        startProgressTracking(result.task_id);
        showProgressView(result.task_id);

      } catch (err) {
        showToast('error', '提交失败', err.message || '请稍后再试');
        btn.disabled = false;
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M5 3l9 5-9 5V3Z" fill="currentColor"/></svg> 开始生成`;
      }
    });
  }

  function buildFormData() {
    const fd      = new FormData();
    const mode    = detectMode();
    const model   = resolveModel();

    // Collect latest values
    wizardData.textPrompt = document.getElementById('productText')?.value?.trim() || null;
    wizardData.productUrl = document.getElementById('productUrl')?.value?.trim()  || null;
    const checkedLangs    = Array.from(document.querySelectorAll('input[name="lang"]:checked')).map(c => c.value);
    wizardData.languages  = checkedLangs.length > 0 ? checkedLangs : ['it'];

    fd.append('mode',     mode);
    fd.append('model',    model);
    fd.append('duration', wizardData.duration);
    fd.append('language', wizardData.languages.join(','));  // comma-separated for multi-language

    // Images: primary as 'image', additional as 'image_2', 'image_3', etc.
    const validImages = wizardData.images.filter(Boolean);
    validImages.forEach((file, i) => {
      const fieldName = i === 0 ? 'image' : `image_${i + 1}`;
      // CRITICAL: upload original file without modification to preserve quality
      fd.append(fieldName, file, file.name);
    });

    if (wizardData.textPrompt)  fd.append('text_prompt',        wizardData.textPrompt);
    if (wizardData.productUrl)  fd.append('url',                wizardData.productUrl);
    if (wizardData.textPrompt || wizardData.productUrl) {
      // Also send as product_description for backward compat
      const desc = wizardData.textPrompt || '';
      if (desc) fd.append('product_description', desc);
    }

    return fd;
  }

  function resetWizard() {
    // Reset data
    wizardData.images       = [];
    wizardData.productUrl   = null;
    wizardData.textPrompt   = null;
    wizardData.duration     = null;
    wizardData.languages    = ['it'];
    wizardData.qualityTier  = null;
    wizardData.model        = null;
    wizardData.manualModel  = null;

    // Reset image slots
    for (let i = 0; i < 5; i++) {
      const slot = document.getElementById(`uploadSlot${i}`);
      const img  = document.getElementById(`slotImg${i}`);
      if (slot) slot.classList.remove('has-file');
      if (img)  img.src = '';
    }

    // Reset text/url fields
    const textEl = document.getElementById('productText');
    const urlEl  = document.getElementById('productUrl');
    if (textEl) textEl.value = '';
    if (urlEl)  urlEl.value  = '';

    // Reset language (Italian pre-checked)
    document.querySelectorAll('input[name="lang"]').forEach(cb => {
      cb.checked = cb.value === 'it';
    });

    // Reset duration
    document.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('selected'));
    const customDur = document.getElementById('customDuration');
    if (customDur) customDur.value = '';
    const durErr = document.getElementById('customDurationError');
    if (durErr) durErr.classList.remove('visible');

    // Reset quality/model
    document.querySelectorAll('[data-tier]').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('#advancedModelGrid [data-model]').forEach(c => c.classList.remove('selected'));

    // Reset next buttons
    const step1Next = document.getElementById('step1Next');
    const step2Next = document.getElementById('step2Next');
    if (step1Next) step1Next.disabled = true;
    if (step2Next) step2Next.disabled = true;

    // Reset start button
    const startBtn = document.getElementById('startGenerateBtn');
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M5 3l9 5-9 5V3Z" fill="currentColor"/></svg> 开始生成`;
    }

    // Hide auto-mode indicator
    const indicator = document.getElementById('autoModeIndicator');
    if (indicator) indicator.style.display = 'none';

    // Close advanced panel
    document.getElementById('advancedModelsWrap')?.classList.remove('open');
    const advBtn = document.getElementById('advancedToggleBtn');
    if (advBtn) {
      advBtn.classList.remove('open');
      advBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg> 展开全部模型（高级选项）`;
    }

    // Reset progress state
    if (activeProgressWs) {
      activeProgressWs.close();
      activeProgressWs = null;
    }
    activeProgressTaskId = null;

    // Reset pipeline stages UI
    resetPipelineStages();

    showStep(1);
  }

  // ── Step 4: Progress View ──

  function renderPipelineStages() {
    const container = document.getElementById('pipelineStages');
    if (!container) return;
    container.innerHTML = '';

    PIPELINE_STAGES.forEach((stage, idx) => {
      const div = document.createElement('div');
      div.className = 'pipeline-stage';
      div.id = `pipelineStage_${stage.key}`;
      div.innerHTML = `
        <div class="pipeline-stage-left">
          <div class="pipeline-stage-dot" id="pipelineDot_${stage.key}">
            <span>${stage.icon}</span>
          </div>
          <div class="pipeline-stage-line"></div>
        </div>
        <div class="pipeline-stage-content">
          <div class="pipeline-stage-label">${stage.label}</div>
          <div class="pipeline-stage-status" id="pipelineStatus_${stage.key}">等待中</div>
        </div>
      `;
      container.appendChild(div);
    });
  }

  function resetPipelineStages() {
    PIPELINE_STAGES.forEach(stage => {
      const el         = document.getElementById(`pipelineStage_${stage.key}`);
      const statusEl   = document.getElementById(`pipelineStatus_${stage.key}`);
      const dotEl      = document.getElementById(`pipelineDot_${stage.key}`);
      if (el)       el.className       = 'pipeline-stage';
      if (statusEl) statusEl.textContent = '等待中';
      if (dotEl)    dotEl.innerHTML    = `<span>${PIPELINE_STAGES.find(s => s.key === stage.key)?.icon || ''}</span>`;
    });

    const bar = document.getElementById('progressOverallBar');
    if (bar) bar.style.width = '0%';

    const segLabel = document.getElementById('progressSegmentLabel');
    if (segLabel) segLabel.textContent = '等待开始';

    document.getElementById('progressCompleteBox')?.style &&
      (document.getElementById('progressCompleteBox').style.display = 'none');
    document.getElementById('progressFailedBox')?.style &&
      (document.getElementById('progressFailedBox').style.display = 'none');

    const pipelineStagesEl = document.getElementById('pipelineStages');
    if (pipelineStagesEl) pipelineStagesEl.style.display = '';
  }

  function showProgressView(taskId) {
    const taskLabel = document.getElementById('progressTaskId');
    if (taskLabel) taskLabel.textContent = `任务 ID: ${taskId}`;

    // Hide complete/failed boxes
    const completeBox = document.getElementById('progressCompleteBox');
    const failedBox   = document.getElementById('progressFailedBox');
    if (completeBox) completeBox.style.display = 'none';
    if (failedBox)   failedBox.style.display   = 'none';

    // Show pipeline
    const stagesEl = document.getElementById('pipelineStages');
    if (stagesEl) stagesEl.style.display = '';

    showStep(4);
  }

  function updatePipelineStage(stageKey, status, statusText) {
    const el       = document.getElementById(`pipelineStage_${stageKey}`);
    const statusEl = document.getElementById(`pipelineStatus_${stageKey}`);
    if (!el) return;

    el.className = `pipeline-stage${status === 'active' ? ' active' : status === 'done' ? ' done' : ''}`;
    if (statusEl) statusEl.textContent = statusText || (status === 'done' ? '已完成' : status === 'active' ? '处理中...' : '等待中');
  }

  function startProgressTracking(taskId) {
    if (!taskId) return;

    // Close any existing WS for this progress
    if (activeProgressWs) {
      activeProgressWs.close();
      activeProgressWs = null;
    }

    activeProgressWs = API.createProgressWebSocket(taskId, {
      onMessage(data) {
        handleProgressMessage(taskId, data);
      },
      onError() {
        // Silently ignore
      },
      onClose() {
        activeProgressWs = null;
      },
    });
  }

  function handleProgressMessage(taskId, data) {
    // Also update "My Videos" task list if visible
    updateTaskStatus(taskId, data);

    // Update the progress view
    const bar      = document.getElementById('progressOverallBar');
    const segLabel = document.getElementById('progressSegmentLabel');

    if (data.status === 'processing') {
      // Segment progress
      if (data.progress_total > 0) {
        const pct = Math.round((data.progress_segment / data.progress_total) * 100);
        if (bar) bar.style.width = `${pct}%`;
        if (segLabel) segLabel.textContent = `片段 ${data.progress_segment} / ${data.progress_total} 生成中`;
      }

      // Stage tracking
      if (data.stage) {
        // Mark all previous stages as done
        const stageIdx = PIPELINE_STAGES.findIndex(s => s.key === data.stage);
        PIPELINE_STAGES.forEach((s, i) => {
          if (i < stageIdx)      updatePipelineStage(s.key, 'done');
          else if (i === stageIdx) updatePipelineStage(s.key, 'active', data.stage_message || '处理中...');
          else                    updatePipelineStage(s.key, 'pending', '等待中');
        });
      }

    } else if (data.status === 'completed') {
      // All stages done
      PIPELINE_STAGES.forEach(s => updatePipelineStage(s.key, 'done'));
      if (bar) bar.style.width = '100%';
      if (segLabel) segLabel.textContent = '已完成';

      // Show complete box
      const stagesEl    = document.getElementById('pipelineStages');
      const completeBox = document.getElementById('progressCompleteBox');
      const dlBtn       = document.getElementById('progressDownloadBtn');

      if (stagesEl)    stagesEl.style.display    = 'none';
      if (completeBox) completeBox.style.display  = 'flex';
      if (dlBtn) {
        dlBtn.style.display = 'inline-flex';
        dlBtn.onclick       = () => downloadTask(taskId);
      }

      // Close WS
      if (activeProgressWs) {
        activeProgressWs.close();
        activeProgressWs = null;
      }

      showToast('success', '视频生成完成！', '可直接下载或前往我的视频查看');

    } else if (data.status === 'failed') {
      const stagesEl  = document.getElementById('pipelineStages');
      const failedBox = document.getElementById('progressFailedBox');
      const errMsg    = document.getElementById('progressErrorMsg');

      if (stagesEl)  stagesEl.style.display  = 'none';
      if (failedBox) failedBox.style.display  = 'flex';
      if (errMsg)    errMsg.textContent       = data.error_message || '生成过程中发生错误，请重试';
      if (segLabel)  segLabel.textContent     = '生成失败';

      if (activeProgressWs) {
        activeProgressWs.close();
        activeProgressWs = null;
      }

      showToast('error', '视频生成失败', data.error_message || '请重试');
    }
  }

  function bindProgressView() {
    // Cancel/back
    document.getElementById('progressCancelBtn')?.addEventListener('click', () => {
      if (activeProgressWs) {
        activeProgressWs.close();
        activeProgressWs = null;
      }
      resetWizard();
    });

    // Go to my videos
    document.getElementById('progressGoToVideosBtn')?.addEventListener('click', () => {
      navigate('my-videos');
    });
    document.getElementById('progressGoToVideosBtn2')?.addEventListener('click', () => {
      navigate('my-videos');
    });

    // Retry
    document.getElementById('progressRetryBtn')?.addEventListener('click', () => {
      resetWizard();
      showStep(1);
    });
  }

  // ══════════════════════════════════════════════════════════
  // ── Video Tasks (unchanged from original) ─────────────────
  // ══════════════════════════════════════════════════════════

  async function loadVideoTasks(page = 1) {
    videoTasksPage = page;
    const loadingEl = document.getElementById('videosLoading');
    const emptyEl   = document.getElementById('videosEmpty');
    const tableEl   = document.getElementById('videosTable');
    const gridEl    = document.getElementById('videosGrid');

    if (loadingEl) loadingEl.style.display = 'block';
    if (tableEl)   tableEl.style.display   = 'none';
    if (gridEl)    gridEl.innerHTML = '';
    if (emptyEl)   emptyEl.style.display   = 'none';

    try {
      const data = await API.getVideoTasks(page, 20);
      const tasks = Array.isArray(data) ? data : (data.tasks || data.items || []);
      videoTasksTotal = data.total || tasks.length;

      if (loadingEl) loadingEl.style.display = 'none';

      if (tasks.length === 0) {
        if (emptyEl) emptyEl.style.display = 'flex';
        return;
      }

      if (videosViewMode === 'list') {
        renderTasksTable(tasks);
      } else {
        renderTasksGrid(tasks);
      }

      renderPagination();

      // Subscribe to WS for any pending/processing tasks
      tasks.forEach(task => {
        if (['pending', 'processing'].includes(task.status)) {
          subscribeTaskProgress(task.id);
        }
      });

    } catch (err) {
      if (loadingEl) loadingEl.style.display = 'none';
      showToast('error', '加载失败', err.message);
    }
  }

  function renderTasksTable(tasks) {
    const tableEl = document.getElementById('videosTable');
    const tbody   = document.getElementById('videosTableBody');
    if (!tbody || !tableEl) return;

    tableEl.style.display = 'block';
    tbody.innerHTML = '';

    tasks.forEach(task => {
      const status = STATUS_LABELS[task.status] || { text: task.status, cls: 'badge-user' };
      const tr = document.createElement('tr');
      tr.id = `taskRow_${task.id}`;
      tr.innerHTML = `
        <td>
          <span class="badge ${status.cls}" id="statusBadge_${task.id}">${status.text}</span>
          <div class="inline-progress" id="inlineProgress_${task.id}" style="display:none;margin-top:4px;">
            <svg width="12" height="12" viewBox="0 0 12 12"><circle cx="6" cy="6" r="5" stroke="#3b82f6" stroke-width="1.5" stroke-dasharray="31.4" stroke-dashoffset="15.7" fill="none"><animateTransform attributeName="transform" type="rotate" dur="1s" repeatCount="indefinite" from="0 6 6" to="360 6 6"/></circle></svg>
            <span id="progressText_${task.id}"></span>
          </div>
        </td>
        <td>${escapeHtml(MODE_DISPLAY_NAMES[task.mode] || task.mode)}</td>
        <td>${escapeHtml(MODEL_DISPLAY_NAMES[task.model] || task.model)}</td>
        <td>${task.duration ? task.duration + 's' : '—'}</td>
        <td>${escapeHtml(LANG_DISPLAY_NAMES[task.language] || task.language || '—')}</td>
        <td style="white-space:nowrap">${formatDate(task.created_at)}</td>
        <td>
          <div class="table-actions">
            ${task.status === 'completed' ? `
              <button class="btn btn-success btn-sm" onclick="Dashboard.downloadTask('${task.id}')">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1v7M3 5l3 3 3-3M1 10h10" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
                下载
              </button>
            ` : ''}
            ${task.status === 'failed' ? `
              <span class="text-danger text-xs" style="max-width:120px;overflow:hidden;text-overflow:ellipsis;" title="${escapeHtml(task.error_message || '')}">
                ${escapeHtml((task.error_message || '').slice(0, 30))}
              </span>
            ` : ''}
            <button class="btn btn-ghost btn-icon btn-sm" onclick="Dashboard.confirmDelete('${task.id}')" title="删除">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 3h8M4 3V2h4v1M5 5v4M7 5v4M3 3l.6 7h4.8L9 3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  function renderTasksGrid(tasks) {
    const grid = document.getElementById('videosGrid');
    if (!grid) return;
    grid.innerHTML = '';

    tasks.forEach(task => {
      const status = STATUS_LABELS[task.status] || { text: task.status, cls: 'badge-user' };
      const card = document.createElement('div');
      card.className = 'video-task-card';
      card.id = `taskCard_${task.id}`;
      card.innerHTML = `
        <div class="task-header">
          <div class="task-meta">
            <div class="task-mode">${escapeHtml(MODE_DISPLAY_NAMES[task.mode] || task.mode)}</div>
            <div class="task-model">${escapeHtml(MODEL_DISPLAY_NAMES[task.model] || task.model)}</div>
          </div>
          <span class="badge ${status.cls}" id="cardStatus_${task.id}">${status.text}</span>
        </div>
        <div class="task-body">
          <div class="task-info-row">
            <div class="task-info-item">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1.2"/><path d="M6 3v3l2 2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
              ${task.duration ? task.duration + '秒' : '—'}
            </div>
            <div class="task-info-item">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1l1.5 3 3.5.5-2.5 2.5.5 3.5L6 9l-3 1.5.5-3.5L1 4.5l3.5-.5z" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/></svg>
              ${escapeHtml(LANG_DISPLAY_NAMES[task.language] || task.language || '—')}
            </div>
          </div>
          <div class="task-progress" id="cardProgress_${task.id}">
            <div class="task-progress-bar-wrap">
              <div class="task-progress-bar" id="cardProgressBar_${task.id}" style="width:0%"></div>
            </div>
            <div class="task-progress-text" id="cardProgressText_${task.id}"></div>
          </div>
          <div class="task-error" id="cardError_${task.id}">
            ${escapeHtml(task.error_message || '')}
          </div>
        </div>
        <div class="task-footer">
          <span class="task-date">${formatDate(task.created_at)}</span>
          <div style="display:flex;gap:var(--sp-2);">
            ${task.status === 'completed' ? `
              <button class="btn btn-success btn-sm" onclick="Dashboard.downloadTask('${task.id}')">下载</button>
            ` : ''}
            <button class="btn btn-ghost btn-sm btn-icon" onclick="Dashboard.confirmDelete('${task.id}')" title="删除">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 3h8M4 3V2h4v1M5 5v4M7 5v4M3 3l.6 7h4.8L9 3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
          </div>
        </div>
      `;
      grid.appendChild(card);
    });

    document.getElementById('videosGridView').style.display = 'block';
  }

  function renderPagination() {
    const container = document.getElementById('videosPagination');
    if (!container) return;
    container.innerHTML = '';

    const totalPages = Math.ceil(videoTasksTotal / 20);
    if (totalPages <= 1) return;

    for (let p = 1; p <= totalPages; p++) {
      const btn = document.createElement('button');
      btn.className = `btn btn-sm ${p === videoTasksPage ? 'btn-primary' : 'btn-secondary'}`;
      btn.textContent = p;
      btn.addEventListener('click', () => loadVideoTasks(p));
      container.appendChild(btn);
    }
  }

  function updateTaskStatus(taskId, data) {
    const statusBadge    = document.getElementById(`statusBadge_${taskId}`);
    const inlineProgress = document.getElementById(`inlineProgress_${taskId}`);
    const progressText   = document.getElementById(`progressText_${taskId}`);

    const cardStatus      = document.getElementById(`cardStatus_${taskId}`);
    const cardProgress    = document.getElementById(`cardProgress_${taskId}`);
    const cardProgressBar = document.getElementById(`cardProgressBar_${taskId}`);
    const cardProgressText = document.getElementById(`cardProgressText_${taskId}`);
    const cardError       = document.getElementById(`cardError_${taskId}`);

    const status = STATUS_LABELS[data.status] || { text: data.status, cls: 'badge-user' };

    if (statusBadge) {
      statusBadge.textContent = status.text;
      statusBadge.className   = `badge ${status.cls}`;
    }
    if (cardStatus) {
      cardStatus.textContent = status.text;
      cardStatus.className   = `badge ${status.cls}`;
    }

    if (data.status === 'processing') {
      const pct = data.progress_total > 0
        ? Math.round((data.progress_segment / data.progress_total) * 100)
        : 0;
      const txt = `片段 ${data.progress_segment}/${data.progress_total}`;

      if (inlineProgress) inlineProgress.style.display = 'flex';
      if (progressText)   progressText.textContent     = txt;
      if (cardProgress)   cardProgress.classList.add('visible');
      if (cardProgressBar) cardProgressBar.style.width = `${pct}%`;
      if (cardProgressText) cardProgressText.textContent = txt;

    } else {
      if (inlineProgress) inlineProgress.style.display = 'none';
      if (cardProgress)   cardProgress.classList.remove('visible');

      if (data.status === 'failed' && data.error_message) {
        if (cardError) {
          cardError.textContent = data.error_message;
          cardError.classList.add('visible');
        }
      }

      if (data.status === 'completed' || data.status === 'failed') {
        if (activeWebSockets[taskId]) {
          activeWebSockets[taskId].close();
          delete activeWebSockets[taskId];
        }

        if (data.status === 'completed') {
          showToast('success', '视频生成完成', '可在我的视频中下载');
          const actionsCell = document.querySelector(`#taskRow_${taskId} .table-actions`);
          if (actionsCell && !actionsCell.querySelector('.btn-success')) {
            const dlBtn = document.createElement('button');
            dlBtn.className = 'btn btn-success btn-sm';
            dlBtn.innerHTML = '下载';
            dlBtn.onclick   = () => downloadTask(taskId);
            actionsCell.prepend(dlBtn);
          }
        }
      }
    }
  }

  function subscribeTaskProgress(taskId) {
    if (activeWebSockets[taskId]) return;

    const ws = API.createProgressWebSocket(taskId, {
      onMessage(data) {
        updateTaskStatus(taskId, data);
      },
      onError() {},
      onClose() {
        delete activeWebSockets[taskId];
      },
    });

    activeWebSockets[taskId] = ws;
  }

  async function downloadTask(taskId) {
    try {
      const response = await API.downloadVideo(taskId);
      if (response && typeof response.blob === 'function') {
        const blob = await response.blob();
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href     = url;
        a.download = `ugcvideo_${taskId}.mp4`;
        a.click();
        URL.revokeObjectURL(url);
      }
      showToast('success', '开始下载', '视频文件下载中...');
    } catch (err) {
      showToast('error', '下载失败', err.message);
    }
  }

  function confirmDelete(taskId) {
    pendingDeleteId = taskId;
    const modal = document.getElementById('confirmDeleteModal');
    if (modal) modal.classList.add('open');
  }

  async function executeDelete() {
    if (!pendingDeleteId) return;
    const id = pendingDeleteId;
    pendingDeleteId = null;

    const modal = document.getElementById('confirmDeleteModal');
    if (modal) modal.classList.remove('open');

    try {
      await API.deleteVideoTask(id);
      showToast('success', '已删除', '视频任务已删除');
      loadVideoTasks(videoTasksPage);
    } catch (err) {
      showToast('error', '删除失败', err.message);
    }
  }

  // ── Settings ──────────────────────────────────────────────────

  function loadSettings() {
    if (!currentUser) return;
    const emailEl = document.getElementById('settingsEmail');
    const nameEl  = document.getElementById('settingsName');
    if (emailEl) emailEl.value = currentUser.email || '';
    if (nameEl)  nameEl.value  = currentUser.display_name || '';
  }

  function initSettings() {
    const savePwdBtn = document.getElementById('savePwdBtn');
    if (!savePwdBtn) return;

    savePwdBtn.addEventListener('click', async () => {
      const current = document.getElementById('currentPwd')?.value;
      const newPwd  = document.getElementById('newPwd')?.value;
      const confirm = document.getElementById('confirmPwd')?.value;

      if (!current || !newPwd || !confirm) {
        showToast('warning', '请填写所有字段', '');
        return;
      }
      if (newPwd.length < 8) {
        showToast('warning', '新密码至少8位', '');
        return;
      }
      if (newPwd !== confirm) {
        showToast('warning', '两次密码不一致', '');
        return;
      }

      savePwdBtn.disabled = true;
      try {
        await API.changePassword(current, newPwd);
        showToast('success', '密码已修改', '');
        document.getElementById('currentPwd').value = '';
        document.getElementById('newPwd').value     = '';
        document.getElementById('confirmPwd').value = '';
      } catch (err) {
        showToast('error', '修改失败', err.message);
      } finally {
        savePwdBtn.disabled = false;
      }
    });
  }

  // ── View Toggle ──────────────────────────────────────────────────

  function initViewToggle() {
    document.querySelectorAll('[data-view]').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('[data-view]').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        videosViewMode = tab.dataset.view;

        const listView = document.getElementById('videosListView');
        const gridView = document.getElementById('videosGridView');

        if (videosViewMode === 'list') {
          if (listView) listView.style.display = 'block';
          if (gridView) gridView.style.display = 'none';
        } else {
          if (listView) listView.style.display = 'none';
          if (gridView) gridView.style.display = 'block';
        }

        loadVideoTasks(1);
      });
    });
  }

  // ── New Video button in My Videos section ─────────────────────────────

  function initMyVideosControls() {
    document.getElementById('newVideoBtn')?.addEventListener('click', () => navigate('new-video'));
  }

  // ── Modals ──────────────────────────────────────────────────

  function initModals() {
    document.getElementById('confirmDeleteClose')?.addEventListener('click', () => {
      document.getElementById('confirmDeleteModal').classList.remove('open');
      pendingDeleteId = null;
    });
    document.getElementById('confirmDeleteCancel')?.addEventListener('click', () => {
      document.getElementById('confirmDeleteModal').classList.remove('open');
      pendingDeleteId = null;
    });
    document.getElementById('confirmDeleteOk')?.addEventListener('click', executeDelete);

    document.querySelectorAll('.modal-overlay').forEach(overlay => {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
          overlay.classList.remove('open');
          pendingDeleteId = null;
        }
      });
    });
  }

  // ── Auto-refresh ──────────────────────────────────────────────────

  function startAutoRefresh() {
    videoRefreshTimer = setInterval(() => {
      const myVideosSection = document.getElementById('section-my-videos');
      if (myVideosSection?.classList.contains('active')) {
        loadVideoTasks(videoTasksPage);
      }
    }, 30000);
  }

  // ── Hash Navigation ──────────────────────────────────────────────────

  function handleHashChange() {
    const hash = window.location.hash.replace('#', '');
    const validSections = ['new-video', 'my-videos', 'settings', 'admin-users', 'admin-invites'];

    if (validSections.includes(hash)) {
      activateSection(hash);
    } else {
      activateSection('new-video');
    }
  }

  // ── Init ────────────────────────────────────────────────────────────────

  async function init() {
    if (!API.isAuthenticated()) {
      window.location.href = 'login.html';
      return;
    }

    await loadUserProfile();

    initSidebar();
    initWizard();
    initViewToggle();
    initMyVideosControls();
    initSettings();
    initModals();
    startAutoRefresh();

    window.addEventListener('hashchange', handleHashChange);
    handleHashChange();
  }

  // ── Public ────────────────────────────────────────────────────────────────

  return {
    init,
    navigate,
    downloadTask,
    confirmDelete,
    showToast,
  };
})();

window.Dashboard = Dashboard;
