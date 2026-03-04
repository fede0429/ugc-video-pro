/**
 * js/dashboard.js
 * Main dashboard logic for UGC Video Pro
 * Handles wizard, video list, WebSocket progress, settings
 */

const Dashboard = (() => {
  'use strict';

  // ── Constants ─────────────────────────────────────────────

  const MODEL_MAX_DURATIONS = {
    sora_2:     12,
    sora_2_pro: 25,
    seedance_2: 10,
    veo_3:       8,
    veo_3_pro:   8,
    veo_31_pro:  8,
  };

  const MODEL_DISPLAY_NAMES = {
    sora_2:     'Sora 2',
    sora_2_pro: 'Sora 2 Pro',
    seedance_2: 'Seedance 2.0',
    veo_3:      'Veo 3.0',
    veo_3_pro:  'Veo 3.0 Pro',
    veo_31_pro: 'Veo 3.1 Pro',
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

  const STEP_LABELS = ['选模式', '选模型', '选时长', '选语言', '上传', '确认'];

  // ── State ─────────────────────────────────────────────────

  let currentUser = null;
  let currentStep = 1;
  let totalSteps  = 6;

  const wizardData = {
    mode:        null,
    model:       null,
    duration:    null,
    language:    null,
    imageFile:   null,
    imageFileUrl: null,
    textPrompt:  null,
    productUrl:  null,
    optionalDesc: null,
  };

  let videoTasksPage = 1;
  let videoTasksTotal = 0;
  let videosViewMode = 'list'; // 'list' | 'grid'
  let activeWebSockets = {}; // taskId → wsInstance
  let videoRefreshTimer = null;
  let pendingDeleteId = null;

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
    // Update hash
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
    const sidebar    = document.getElementById('sidebar');
    const toggle     = document.getElementById('sidebarToggle');
    const hamburger  = document.getElementById('hamburger');
    const backdrop   = document.getElementById('sidebarBackdrop');

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

      // Update UI
      const avatarEl   = document.getElementById('userAvatar');
      const nameEl     = document.getElementById('userName');
      const roleBadge  = document.getElementById('userRoleBadge');

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

  // ── Wizard ─────────────────────────────────────────────────

  function initWizard() {
    renderStepsHeader();
    bindStep1();
    bindStep2();
    bindStep3();
    bindStep4();
    bindStep5();
    bindStep6();
  }

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
    // Update step dots
    STEP_LABELS.forEach((_, idx) => {
      const stepNum = idx + 1;
      const dot = document.getElementById(`stepDot${stepNum}`);
      if (!dot) return;
      dot.className = `wizard-step-dot${stepNum < currentStep ? ' completed' : stepNum === currentStep ? ' active' : ''}`;
      dot.querySelector('.step-dot-circle').textContent = stepNum < currentStep ? '✓' : stepNum;

      // Connector
      if (stepNum > 1) {
        const connector = document.getElementById(`stepConnector${stepNum}`);
        if (connector) connector.className = `step-connector${stepNum <= currentStep ? ' filled' : ''}`;
      }
    });

    // Progress bar
    const bar = document.getElementById('wizardProgressBar');
    if (bar) bar.style.width = `${(currentStep / totalSteps) * 100}%`;

    // Step label
    const numEl = document.getElementById('currentStepNum');
    if (numEl) numEl.textContent = currentStep;
  }

  function showStep(step) {
    for (let i = 1; i <= totalSteps; i++) {
      const el = document.getElementById(`wizardStep${i}`);
      if (el) el.style.display = i === step ? 'block' : 'none';
    }
    currentStep = step;
    updateStepUI();
    // Scroll to top of wizard
    document.querySelector('.wizard-container')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // Step 1: Mode
  function bindStep1() {
    document.querySelectorAll('[data-mode]').forEach(card => {
      card.addEventListener('click', () => {
        document.querySelectorAll('[data-mode]').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        wizardData.mode = card.dataset.mode;
        document.getElementById('step1Next').disabled = false;
      });
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); card.click(); }
      });
    });

    document.getElementById('step1Next').addEventListener('click', () => {
      if (wizardData.mode) showStep(2);
    });
  }

  // Step 2: Model
  function bindStep2() {
    document.querySelectorAll('[data-model]').forEach(card => {
      card.addEventListener('click', () => {
        document.querySelectorAll('[data-model]').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        wizardData.model = card.dataset.model;
        document.getElementById('step2Next').disabled = false;
      });
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); card.click(); }
      });
    });

    document.getElementById('step2Back').addEventListener('click', () => showStep(1));
    document.getElementById('step2Next').addEventListener('click', () => {
      if (wizardData.model) { buildDurationOptions(); showStep(3); }
    });
  }

  // Step 3: Duration
  function buildDurationOptions() {
    const maxClip = MODEL_MAX_DURATIONS[wizardData.model] || 8;
    const grid = document.getElementById('durationGrid');
    if (!grid) return;
    grid.innerHTML = '';
    wizardData.duration = null;
    document.getElementById('step3Next').disabled = true;

    // Update description
    const desc = document.getElementById('durationDesc');
    if (desc) desc.textContent = `当前模型单次最长 ${maxClip} 秒，时长必须为 ${maxClip} 的整数倍`;

    // Hint
    const hint = document.getElementById('customDurationHint');
    if (hint) hint.textContent = `必须为 ${maxClip} 的整数倍（如 ${maxClip}, ${maxClip * 2}, ${maxClip * 3}...）`;

    // Generate 5 multiples up to 120s
    const multiples = [];
    for (let i = 1; multiples.length < 5 && (i * maxClip) <= 120; i++) {
      multiples.push(i * maxClip);
    }
    // If none reach 120, also add 120 if it's valid
    if (maxClip <= 120 && (120 % maxClip === 0) && !multiples.includes(120)) {
      multiples.push(120);
    }

    multiples.forEach(val => {
      const btn = document.createElement('button');
      btn.className = 'duration-btn';
      btn.textContent = `${val}秒`;
      btn.dataset.val = val;
      btn.addEventListener('click', () => {
        document.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        wizardData.duration = val;
        document.getElementById('step3Next').disabled = false;
        document.getElementById('customDuration').value = '';
        document.getElementById('customDurationError').classList.remove('visible');
      });
      grid.appendChild(btn);
    });
  }

  function bindStep3() {
    document.getElementById('applyCustomDuration')?.addEventListener('click', () => {
      const maxClip = MODEL_MAX_DURATIONS[wizardData.model] || 8;
      const val = parseInt(document.getElementById('customDuration').value, 10);
      const errEl = document.getElementById('customDurationError');

      if (!val || val < maxClip) {
        errEl.textContent = `请输入至少 ${maxClip} 秒`;
        errEl.classList.add('visible');
        return;
      }

      if (val % maxClip !== 0) {
        const nearest = Math.round(val / maxClip) * maxClip;
        errEl.textContent = `${val}秒 不是 ${maxClip} 的整数倍，最近有效: ${nearest}秒`;
        errEl.classList.add('visible');
        return;
      }

      errEl.classList.remove('visible');
      document.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('selected'));
      wizardData.duration = val;
      document.getElementById('step3Next').disabled = false;
      showToast('success', '时长已设置', `${val} 秒`);
    });

    document.getElementById('customDuration')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') document.getElementById('applyCustomDuration').click();
    });

    document.getElementById('step3Back').addEventListener('click', () => showStep(2));
    document.getElementById('step3Next').addEventListener('click', () => {
      if (wizardData.duration) showStep(4);
    });
  }

  // Step 4: Language
  function bindStep4() {
    document.querySelectorAll('[data-lang]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('[data-lang]').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        wizardData.language = btn.dataset.lang;
        document.getElementById('step4Next').disabled = false;
      });
    });

    document.getElementById('step4Back').addEventListener('click', () => showStep(3));
    document.getElementById('step4Next').addEventListener('click', () => {
      if (wizardData.language) { setupStep5(); showStep(5); }
    });
  }

  // Step 5: Content Upload
  function setupStep5() {
    const mode = wizardData.mode;

    // Hide all input areas
    ['inputImageUpload', 'inputTextDesc', 'inputUrlImage', 'optionalDescWrap'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });

    // Update step description
    const desc = document.getElementById('step5Desc');

    if (mode === 'image_to_video') {
      document.getElementById('inputImageUpload').style.display = 'block';
      document.getElementById('optionalDescWrap').style.display = 'block';
      if (desc) desc.textContent = '上传产品图片（保留原图质量）：';
    } else if (mode === 'text_to_video') {
      document.getElementById('inputTextDesc').style.display = 'block';
      if (desc) desc.textContent = '输入产品文字描述：';
    } else if (mode === 'url_to_video') {
      document.getElementById('inputUrlImage').style.display = 'block';
      document.getElementById('optionalDescWrap').style.display = 'block';
      if (desc) desc.textContent = '输入商品链接并上传产品图片：';
    }

    // Reset the next button
    document.getElementById('step5Next').disabled = !checkStep5Valid();
  }

  function checkStep5Valid() {
    const mode = wizardData.mode;
    if (mode === 'image_to_video') {
      return !!wizardData.imageFile;
    } else if (mode === 'text_to_video') {
      const text = document.getElementById('productText')?.value?.trim();
      return text && text.length > 5;
    } else if (mode === 'url_to_video') {
      const url = document.getElementById('productUrl')?.value?.trim();
      return !!wizardData.imageFileUrl && !!url;
    }
    return false;
  }

  function bindStep5() {
    // Image upload zone (image_to_video)
    setupUploadZone(
      'uploadZone', 'imageFileInput', 'uploadPreview', 'uploadPreviewImg',
      'uploadFilename', 'uploadFilesize', 'uploadRemove',
      (file) => { wizardData.imageFile = file; updateStep5Next(); }
    );

    // Image upload zone (url_to_video)
    setupUploadZone(
      'uploadZoneUrl', 'imageFileInputUrl', 'uploadPreviewUrl', 'uploadPreviewImgUrl',
      'uploadFilenameUrl', 'uploadFilesizeUrl', 'uploadRemoveUrl',
      (file) => { wizardData.imageFileUrl = file; updateStep5Next(); }
    );

    // Text input watch
    document.getElementById('productText')?.addEventListener('input', updateStep5Next);
    document.getElementById('productUrl')?.addEventListener('input', updateStep5Next);

    document.getElementById('step5Back').addEventListener('click', () => showStep(4));
    document.getElementById('step5Next').addEventListener('click', () => {
      // Capture final values
      wizardData.textPrompt   = document.getElementById('productText')?.value?.trim() || null;
      wizardData.productUrl   = document.getElementById('productUrl')?.value?.trim()  || null;
      wizardData.optionalDesc = document.getElementById('optionalDesc')?.value?.trim() || null;
      buildSummary();
      showStep(6);
    });
  }

  function updateStep5Next() {
    document.getElementById('step5Next').disabled = !checkStep5Valid();
  }

  function setupUploadZone(zoneId, inputId, previewId, previewImgId, filenameId, filesizeId, removeId, onFile) {
    const zone     = document.getElementById(zoneId);
    const input    = document.getElementById(inputId);
    const preview  = document.getElementById(previewId);
    const img      = document.getElementById(previewImgId);
    const filename = document.getElementById(filenameId);
    const filesize = document.getElementById(filesizeId);
    const removeBtn = document.getElementById(removeId);

    if (!zone || !input) return;

    // Click to open file picker
    zone.addEventListener('click', () => input.click());
    zone.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
    });

    // Drag and drop
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    });

    // File input change
    input.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) handleFile(file);
    });

    // Remove button
    if (removeBtn) {
      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFile();
      });
    }

    function handleFile(file) {
      // Validate type
      if (!file.type.startsWith('image/')) {
        showToast('error', '文件类型错误', '请上传 JPG、PNG 或 WebP 图片');
        return;
      }
      // Validate size (20MB max)
      if (file.size > 20 * 1024 * 1024) {
        showToast('error', '图片过大', '最大支持 20MB，请压缩后重试');
        return;
      }

      // Show preview
      const reader = new FileReader();
      reader.onload = (e) => {
        if (img) { img.src = e.target.result; }
        if (preview) preview.classList.add('visible');
        if (filename) filename.textContent = file.name;
        if (filesize) filesize.textContent = formatFileSize(file.size);
        zone.classList.add('has-file');
      };
      reader.readAsDataURL(file);

      onFile(file);
    }

    function clearFile() {
      if (img) img.src = '';
      if (preview) preview.classList.remove('visible');
      if (filename) filename.textContent = '';
      if (filesize) filesize.textContent = '';
      zone.classList.remove('has-file');
      input.value = '';
      onFile(null);
    }
  }

  // Step 6: Summary
  function buildSummary() {
    const grid = document.getElementById('summaryGrid');
    if (!grid) return;

    const maxClip = MODEL_MAX_DURATIONS[wizardData.model] || 8;
    const segments = Math.ceil(wizardData.duration / maxClip);

    const rows = [
      { label: '模式',   value: MODE_DISPLAY_NAMES[wizardData.mode]  || wizardData.mode },
      { label: '模型',   value: MODEL_DISPLAY_NAMES[wizardData.model] || wizardData.model },
      { label: '时长',   value: `${wizardData.duration} 秒` },
      { label: '片段数', value: `${segments} 个片段（每段最长 ${maxClip}s）` },
      { label: '语言',   value: LANG_DISPLAY_NAMES[wizardData.language] || wizardData.language },
    ];

    if (wizardData.textPrompt) {
      rows.push({ label: '描述', value: wizardData.textPrompt.slice(0, 80) + (wizardData.textPrompt.length > 80 ? '…' : '') });
    }
    if (wizardData.productUrl) {
      rows.push({ label: '链接', value: wizardData.productUrl.slice(0, 60) + (wizardData.productUrl.length > 60 ? '…' : '') });
    }
    if (wizardData.imageFile) {
      rows.push({ label: '图片', value: wizardData.imageFile.name });
    }
    if (wizardData.optionalDesc) {
      rows.push({ label: '说明', value: wizardData.optionalDesc.slice(0, 60) + (wizardData.optionalDesc.length > 60 ? '…' : '') });
    }

    grid.innerHTML = rows.map(r => `
      <div class="summary-row">
        <span class="summary-label">${escapeHtml(r.label)}</span>
        <span class="summary-value">${escapeHtml(r.value)}</span>
      </div>
    `).join('');
  }

  function bindStep6() {
    document.getElementById('step6Back').addEventListener('click', () => showStep(5));

    document.getElementById('startGenerateBtn').addEventListener('click', async () => {
      const btn = document.getElementById('startGenerateBtn');
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner"></span> 提交中...`;

      try {
        const formData = buildFormData();
        const result   = await API.generateVideo(formData);

        showToast('success', '任务已提交', `任务 ID: ${result.task_id || '已创建'}`);

        // Reset wizard and navigate to my videos
        resetWizard();
        navigate('my-videos');

        // Subscribe to WS for this task
        if (result.task_id) {
          subscribeTaskProgress(result.task_id);
        }

      } catch (err) {
        showToast('error', '提交失败', err.message || '请稍后再试');
        btn.disabled = false;
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M5 3l9 5-9 5V3Z" fill="currentColor"/></svg> 开始生成`;
      }
    });
  }

  function buildFormData() {
    const fd = new FormData();
    fd.append('mode',     wizardData.mode);
    fd.append('model',    wizardData.model);
    fd.append('duration', wizardData.duration);
    fd.append('language', wizardData.language);

    if (wizardData.imageFile) {
      // IMPORTANT: upload original file without modification to preserve quality
      fd.append('image', wizardData.imageFile, wizardData.imageFile.name);
    }
    if (wizardData.imageFileUrl) {
      fd.append('image', wizardData.imageFileUrl, wizardData.imageFileUrl.name);
    }
    if (wizardData.textPrompt)   fd.append('text_prompt',    wizardData.textPrompt);
    if (wizardData.productUrl)   fd.append('url',            wizardData.productUrl);
    if (wizardData.optionalDesc) fd.append('product_description', wizardData.optionalDesc);

    return fd;
  }

  function resetWizard() {
    // Reset data
    Object.keys(wizardData).forEach(k => { wizardData[k] = null; });

    // Reset UI
    document.querySelectorAll('[data-mode]').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('[data-model]').forEach(c => c.classList.remove('selected'));
    document.querySelectorAll('[data-lang]').forEach(b => b.classList.remove('selected'));
    document.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('selected'));

    ['step1Next','step2Next','step3Next','step4Next','step5Next'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.disabled = true;
    });

    const startBtn = document.getElementById('startGenerateBtn');
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M5 3l9 5-9 5V3Z" fill="currentColor"/></svg> 开始生成`;
    }

    showStep(1);
  }

  // ── Video Tasks ─────────────────────────────────────────────────

  async function loadVideoTasks(page = 1) {
    videoTasksPage = page;
    const loadingEl = document.getElementById('videosLoading');
    const emptyEl   = document.getElementById('videosEmpty');
    const tableEl   = document.getElementById('videosTable');
    const gridEl    = document.getElementById('videosGrid');

    // Show loading
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
    // Update table row if visible
    const statusBadge = document.getElementById(`statusBadge_${taskId}`);
    const inlineProgress = document.getElementById(`inlineProgress_${taskId}`);
    const progressText = document.getElementById(`progressText_${taskId}`);

    // Grid card
    const cardStatus = document.getElementById(`cardStatus_${taskId}`);
    const cardProgress = document.getElementById(`cardProgress_${taskId}`);
    const cardProgressBar = document.getElementById(`cardProgressBar_${taskId}`);
    const cardProgressText = document.getElementById(`cardProgressText_${taskId}`);
    const cardError = document.getElementById(`cardError_${taskId}`);

    const status = STATUS_LABELS[data.status] || { text: data.status, cls: 'badge-user' };

    if (statusBadge) {
      statusBadge.textContent = status.text;
      statusBadge.className = `badge ${status.cls}`;
    }
    if (cardStatus) {
      cardStatus.textContent = status.text;
      cardStatus.className = `badge ${status.cls}`;
    }

    if (data.status === 'processing') {
      const pct = data.progress_total > 0
        ? Math.round((data.progress_segment / data.progress_total) * 100)
        : 0;
      const txt = `片段 ${data.progress_segment}/${data.progress_total}`;

      if (inlineProgress) inlineProgress.style.display = 'flex';
      if (progressText) progressText.textContent = txt;
      if (cardProgress) cardProgress.classList.add('visible');
      if (cardProgressBar) cardProgressBar.style.width = `${pct}%`;
      if (cardProgressText) cardProgressText.textContent = txt;

    } else {
      if (inlineProgress) inlineProgress.style.display = 'none';
      if (cardProgress) cardProgress.classList.remove('visible');

      if (data.status === 'failed' && data.error_message) {
        if (cardError) {
          cardError.textContent = data.error_message;
          cardError.classList.add('visible');
        }
      }

      if (data.status === 'completed' || data.status === 'failed') {
        // Close WS for this task
        if (activeWebSockets[taskId]) {
          activeWebSockets[taskId].close();
          delete activeWebSockets[taskId];
        }

        if (data.status === 'completed') {
          showToast('success', '视频生成完成', '可在我的视频中下载');
          // Add download button if in table view
          const actionsCell = document.querySelector(`#taskRow_${taskId} .table-actions`);
          if (actionsCell && !actionsCell.querySelector('.btn-success')) {
            const dlBtn = document.createElement('button');
            dlBtn.className = 'btn btn-success btn-sm';
            dlBtn.innerHTML = '下载';
            dlBtn.onclick = () => downloadTask(taskId);
            actionsCell.prepend(dlBtn);
          }
        }
      }
    }
  }

  function subscribeTaskProgress(taskId) {
    if (activeWebSockets[taskId]) return; // Already subscribed

    const ws = API.createProgressWebSocket(taskId, {
      onMessage(data) {
        updateTaskStatus(taskId, data);
      },
      onError() {
        // Silently ignore WS errors
      },
      onClose() {
        delete activeWebSockets[taskId];
      },
    });

    activeWebSockets[taskId] = ws;
  }

  async function downloadTask(taskId) {
    try {
      const response = await API.downloadVideo(taskId);
      if (!response || !response.blob) {
        // If apiFetch returned raw Response
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
      const current  = document.getElementById('currentPwd')?.value;
      const newPwd   = document.getElementById('newPwd')?.value;
      const confirm  = document.getElementById('confirmPwd')?.value;

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
        document.getElementById('newPwd').value = '';
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
    // Confirm delete modal
    document.getElementById('confirmDeleteClose')?.addEventListener('click', () => {
      document.getElementById('confirmDeleteModal').classList.remove('open');
      pendingDeleteId = null;
    });
    document.getElementById('confirmDeleteCancel')?.addEventListener('click', () => {
      document.getElementById('confirmDeleteModal').classList.remove('open');
      pendingDeleteId = null;
    });
    document.getElementById('confirmDeleteOk')?.addEventListener('click', executeDelete);

    // Close modals on overlay click
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
    // Refresh video list every 30s if on my-videos section
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
    // Guard: must be authenticated
    if (!API.isAuthenticated()) {
      window.location.href = 'login.html';
      return;
    }

    // Load user profile first (needed for admin check)
    await loadUserProfile();

    // Initialize components
    initSidebar();
    initWizard();
    initViewToggle();
    initMyVideosControls();
    initSettings();
    initModals();
    startAutoRefresh();

    // Handle navigation
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
