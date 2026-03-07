
const ACCESS_KEYS = ['ugcvp_access_token', 'token'];
const DEFAULT_CHARACTERS = [
  {
    name: '沈晚',
    role: '豪门千金 / 女主',
    age_range: '23-28',
    appearance: ['黑长发', '冷白皮', '精致五官', '细长眼型'],
    wardrobe: ['黑色修身西装裙', '银色耳饰'],
    personality: ['理智', '强势', '克制'],
    voice_style: '冷静、锋利、克制',
    catchphrases: ['你最好想清楚再说。'],
    reference_image_url: '',
  },
  {
    name: '周叙',
    role: '失业编剧 / 男主',
    age_range: '25-30',
    appearance: ['短黑发', '干净轮廓', '略显疲惫'],
    wardrobe: ['白衬衫', '深色长裤'],
    personality: ['聪明', '嘴硬', '有韧劲'],
    voice_style: '年轻、自然、有一点不服输',
    catchphrases: ['这戏我还真接了。'],
    reference_image_url: '',
  },
];

let activeTaskId = '';
let ws = null;
let pollTimer = null;
let charactersState = JSON.parse(JSON.stringify(DEFAULT_CHARACTERS));

function getAccessToken() {
  for (const key of ACCESS_KEYS) {
    const token = localStorage.getItem(key);
    if (token) return token;
  }
  return '';
}

function headersJson() {
  const headers = { 'Content-Type': 'application/json' };
  const token = getAccessToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

function authHeaders() {
  const headers = {};
  const token = getAccessToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

function splitList(value) {
  return (value || '').split(/[\n,，]/).map(s => s.trim()).filter(Boolean);
}

function currentGoal(defaultValue = '剧情冲突升级') {
  return (
    document.getElementById('episode-goal')?.value?.trim() ||
    document.getElementById('goal')?.value?.trim() ||
    document.getElementById('premise')?.value?.trim() ||
    defaultValue
  );
}

function updateCharactersJson() {
  document.getElementById('characters-json').value = JSON.stringify(charactersState, null, 2);
}

function loadCharactersFromJson() {
  try {
    const parsed = JSON.parse(document.getElementById('characters-json').value);
    if (!Array.isArray(parsed)) throw new Error('角色 JSON 必须是数组');
    charactersState = parsed;
    renderCharacterEditor();
    return true;
  } catch (error) {
    setStatus(`角色 JSON 解析失败：${error.message}`);
    return false;
  }
}

function renderCharacterEditor() {
  const box = document.getElementById('character-editor');
  box.innerHTML = charactersState.map((char, index) => `
    <div class="character-card">
      <div class="character-head">
        <strong>角色 ${index + 1}</strong>
        <button type="button" class="secondary remove-character-btn" data-index="${index}">删除</button>
      </div>
      <div class="meta">
        <div class="row"><label>姓名</label><input data-field="name" data-index="${index}" value="${char.name || ''}" /></div>
        <div class="row"><label>角色定位</label><input data-field="role" data-index="${index}" value="${char.role || ''}" /></div>
        <div class="row"><label>年龄段</label><input data-field="age_range" data-index="${index}" value="${char.age_range || ''}" /></div>
        <div class="row"><label>voice_style</label><input data-field="voice_style" data-index="${index}" value="${char.voice_style || ''}" /></div>
        <div class="row"><label>appearance</label><textarea data-list-field="appearance" data-index="${index}">${(char.appearance || []).join('\n')}</textarea></div>
        <div class="row"><label>wardrobe</label><textarea data-list-field="wardrobe" data-index="${index}">${(char.wardrobe || []).join('\n')}</textarea></div>
        <div class="row"><label>personality</label><textarea data-list-field="personality" data-index="${index}">${(char.personality || []).join('\n')}</textarea></div>
        <div class="row"><label>catchphrases</label><textarea data-list-field="catchphrases" data-index="${index}">${(char.catchphrases || []).join('\n')}</textarea></div>
        <div class="row">
          <label>角色参考图</label>
          <input type="file" accept="image/*" class="character-file-input" data-index="${index}" />
          <div class="small">${char.reference_image_url ? `已上传：<a href="${char.reference_image_url}" target="_blank">查看参考图</a>` : '未上传参考图'}</div>
        </div>
      </div>
    </div>
  `).join('');

  box.querySelectorAll('input[data-field], textarea[data-list-field]').forEach(el => {
    el.addEventListener('input', () => {
      const idx = Number(el.dataset.index);
      if (el.dataset.field) {
        charactersState[idx][el.dataset.field] = el.value;
      } else if (el.dataset.listField) {
        charactersState[idx][el.dataset.listField] = splitList(el.value);
      }
      updateCharactersJson();
    });
  });

  box.querySelectorAll('.remove-character-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      charactersState.splice(Number(btn.dataset.index), 1);
      renderCharacterEditor();
      updateCharactersJson();
    });
  });

  box.querySelectorAll('.character-file-input').forEach(input => {
    input.addEventListener('change', async () => {
      const idx = Number(input.dataset.index);
      const file = input.files?.[0];
      if (!file) return;
      await uploadReferenceImage(idx, file);
    });
  });
}

async function uploadReferenceImage(index, file) {
  const char = charactersState[index];
  const form = new FormData();
  form.append('file', file);
  form.append('character_name', char.name || `character_${index + 1}`);
  setStatus(`正在上传 ${char.name || `角色${index + 1}`} 参考图...`);
  try {
    const res = await fetch('/api/animation/reference/upload', {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    charactersState[index].reference_image_url = data.asset_url || data.local_path;
    charactersState[index].reference_image_asset_url = data.asset_url || '';
    updateCharactersJson();
    renderCharacterEditor();
    setStatus(`参考图上传完成：${char.name}`);
  } catch (error) {
    setStatus(`参考图上传失败：${error.message}`);
  }
}

function buildPayload() {
  if (!loadCharactersFromJson()) throw new Error('角色 JSON 无法解析');
  return {
    title: document.getElementById('title').value.trim(),
    core_premise: document.getElementById('premise').value.trim(),
    episode_goal: document.getElementById('episode-goal').value.trim(),
    visual_style: document.getElementById('visual-style').value.trim(),
    genre: document.getElementById('genre').value.trim(),
    format_type: '竖屏短剧',
    target_platform: document.getElementById('platform').value,
    tone: '高张力、强反转',
    scene_count: Number(document.getElementById('scene-count').value || 4),
    language: document.getElementById('language').value,
    aspect_ratio: document.getElementById('aspect-ratio').value,
    model_variant: document.getElementById('model-variant').value,
    fallback_model: document.getElementById('fallback-model').value,
    enable_tts: document.getElementById('enable-tts').checked,
    dry_run: document.getElementById('dry-run').checked,
    shot_retry_limit: Number(document.getElementById('shot-retry-limit').value || 2),
    characters: charactersState,
  };
}

function buildBatchPayload() {
  const payload = buildPayload();
  const goals = document.getElementById('batch-goals').value.split('\n').map(s => s.trim()).filter(Boolean);
  return {
    ...payload,
    episode_goals: goals,
    title_prefix: payload.title,
  };
}

function setStatus(text) {
  document.getElementById('form-status').textContent = text;
}

function renderTaskLinks(task) {
  const box = document.getElementById('task-links');
  const links = [];
  const taskId = task.task_id;
  if (task.output_video) links.push(`<div><a href="/api/animation/tasks/${taskId}/artifact/final_video" target="_blank">打开成片</a></div>`);
  if (task.subtitle_path) links.push(`<div><a href="/api/animation/tasks/${taskId}/artifact/subtitle" target="_blank">打开字幕</a></div>`);
  if (task.storyboard_path) links.push(`<div><a href="/api/animation/tasks/${taskId}/artifact/plan" target="_blank">打开规划 JSON</a></div>`);
  box.innerHTML = links.join('');
}

function showTask(task) {
  activeTaskId = task.task_id || activeTaskId;
  const status = document.getElementById('task-status');
  status.textContent = `${task.status} / ${task.stage} / ${task.stage_message || ''} / ${task.progress || 0}%`;
  document.getElementById('output').textContent = JSON.stringify(task, null, 2);
  document.getElementById('retry-task-id').value = task.task_id || '';
  const taskIdBox = document.getElementById('task-id');
  if (taskIdBox) taskIdBox.textContent = task.task_id || '';
  renderTaskLinks(task);
}

async function loadTemplateLibrary() {
  try {
    const res = await fetch('/api/animation/templates', { headers: headersJson() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    document.getElementById('template-preview').textContent = JSON.stringify(data, null, 2);
    setStatus(`已加载 ${data.count || 0} 个分镜模板。`);
  } catch (error) {
    setStatus(`模板库加载失败：${error.message}`);
  }
}

async function checkConsistency() {
  setStatus('正在执行角色一致性检查...');
  try {
    const res = await fetch('/api/animation/projects/consistency-check', {
      method: 'POST',
      headers: headersJson(),
      body: JSON.stringify(buildPayload()),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    document.getElementById('consistency-status').textContent =
      `一致性分数 ${data.consistency_report?.consistency_score || 0} / 100`;
    document.getElementById('template-preview').textContent = JSON.stringify(data, null, 2);
    setStatus('一致性检查完成。');
  } catch (error) {
    setStatus(`一致性检查失败：${error.message}`);
  }
}

async function createPlan() {
  setStatus('正在生成规划...');
  const output = document.getElementById('output');
  try {
    const res = await fetch('/api/animation/projects/plan', {
      method: 'POST',
      headers: headersJson(),
      body: JSON.stringify(buildPayload()),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    output.textContent = JSON.stringify(data, null, 2);
    setStatus('规划生成完成。');
  } catch (error) {
    output.textContent = `规划失败: ${error.message}`;
    setStatus('规划失败。');
  }
}

function closeRealtime() {
  if (ws) {
    try { ws.close(); } catch (e) {}
    ws = null;
  }
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function fetchTask(taskId) {
  const res = await fetch(`/api/animation/tasks/${taskId}`, { headers: headersJson() });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
  showTask(data);
  return data;
}

function startRealtime(taskId) {
  closeRealtime();
  activeTaskId = taskId;
  localStorage.setItem('animation_active_task_id', taskId);
  const token = getAccessToken();
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = token
    ? `${proto}://${location.host}/api/ws/progress/${taskId}?token=${encodeURIComponent(token)}`
    : `${proto}://${location.host}/api/ws/progress/${taskId}`;

  try {
    ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        document.getElementById('task-status').textContent =
          `${data.status || ''} / ${data.stage || ''} / ${data.stage_message || ''} / ${data.progress || 0}%`;
        if (data.status === 'completed' || data.status === 'failed') {
          fetchTask(taskId).catch(() => {});
          closeRealtime();
        }
      } catch (e) {}
    };
    ws.onerror = () => {
      if (!pollTimer) pollTimer = setInterval(() => fetchTask(taskId).catch(() => {}), 5000);
    };
    ws.onclose = () => {
      if (!pollTimer) pollTimer = setInterval(() => fetchTask(taskId).catch(() => {}), 5000);
    };
  } catch (e) {
    pollTimer = setInterval(() => fetchTask(taskId).catch(() => {}), 5000);
  }
  fetchTask(taskId).catch(() => {});
}

async function startRender() {
  setStatus('正在创建生产任务...');
  const output = document.getElementById('output');
  try {
    const res = await fetch('/api/animation/projects/render', {
      method: 'POST',
      headers: headersJson(),
      body: JSON.stringify(buildPayload()),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    output.textContent = JSON.stringify(data, null, 2);
    setStatus(`任务已创建: ${data.task_id}`);
    startRealtime(data.task_id);
    await refreshTasks();
  } catch (error) {
    output.textContent = `创建任务失败: ${error.message}`;
    setStatus('创建任务失败。');
  }
}

async function startBatchRender() {
  setStatus('正在创建批量生产任务...');
  const output = document.getElementById('output');
  try {
    const res = await fetch('/api/animation/projects/render-batch', {
      method: 'POST',
      headers: headersJson(),
      body: JSON.stringify(buildBatchPayload()),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    output.textContent = JSON.stringify(data, null, 2);
    setStatus(`批量任务已创建: ${data.batch_task_id}`);
    await refreshTasks();
  } catch (error) {
    output.textContent = `批量任务创建失败: ${error.message}`;
    setStatus('批量任务创建失败。');
  }
}

async function retryShot() {
  setStatus('正在重试镜头...');
  const output = document.getElementById('output');
  try {
    const taskId = document.getElementById('retry-task-id').value.trim();
    const shotId = document.getElementById('retry-shot-id').value.trim();
    if (!taskId || !shotId) throw new Error('请填写任务 ID 和镜头 ID');
    const res = await fetch('/api/animation/shots/retry', {
      method: 'POST',
      headers: headersJson(),
      body: JSON.stringify({ task_id: taskId, shot_id: shotId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    output.textContent = JSON.stringify(data, null, 2);
    setStatus(`镜头 ${shotId} 重试完成。`);
    startRealtime(taskId);
  } catch (error) {
    output.textContent = `镜头重试失败: ${error.message}`;
    setStatus('镜头重试失败。');
  }
}

async function refreshTasks() {
  const box = document.getElementById('task-list');
  try {
    const res = await fetch('/api/animation/tasks?limit=20', { headers: headersJson() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    const items = data.items || [];
    if (!items.length) {
      box.innerHTML = '<div class="status">暂无任务。</div>';
      return;
    }
    box.innerHTML = items.map(item => `
      <div class="panel" style="padding:10px; margin-bottom:8px;">
        <div><strong>${item.task_id}</strong></div>
        <div class="status">${item.status} / ${item.stage} / ${item.progress || 0}%</div>
        <div class="small">${item.batch_parent_id ? `批量父任务：${item.batch_parent_id}` : ''}</div>
        <div class="btns" style="margin-top:8px;">
          <button data-task="${item.task_id}" class="open-task-btn">查看</button>
        </div>
      </div>
    `).join('');
    box.querySelectorAll('.open-task-btn').forEach(btn => {
      btn.addEventListener('click', () => startRealtime(btn.dataset.task));
    });
  } catch (error) {
    box.innerHTML = `<div class="status">任务列表加载失败: ${error.message}</div>`;
  }
}

document.getElementById('plan-btn')?.addEventListener('click', createPlan);
document.getElementById('render-btn')?.addEventListener('click', startRender);
document.getElementById('batch-render-btn')?.addEventListener('click', startBatchRender);
document.getElementById('retry-shot-btn')?.addEventListener('click', retryShot);
document.getElementById('refresh-btn')?.addEventListener('click', refreshTasks);
document.getElementById('add-character-btn')?.addEventListener('click', () => {
  charactersState.push({
    name: '',
    role: '',
    age_range: '18-25',
    appearance: [],
    wardrobe: [],
    personality: [],
    voice_style: '',
    catchphrases: [],
    reference_image_url: '',
  });
  renderCharacterEditor();
  updateCharactersJson();
});
document.getElementById('sync-json-btn')?.addEventListener('click', () => {
  if (loadCharactersFromJson()) setStatus('角色 JSON 已同步到编辑器。');
});

window.addEventListener('load', async () => {
  updateCharactersJson();
  renderCharacterEditor();
  await refreshTasks();
  const active = localStorage.getItem('animation_active_task_id');
  if (active) startRealtime(active);
});

document.getElementById('check-consistency-btn')?.addEventListener('click', checkConsistency);
document.getElementById('load-templates-btn')?.addEventListener('click', loadTemplateLibrary);


async function loadStateMachine() {
  const res = await fetch('/api/animation/states', { headers: authHeaders() });
  const data = await res.json();
  document.getElementById('state-box').textContent = JSON.stringify(data, null, 2);
  setStatus('角色状态机已加载');
}

async function loadSceneAssets() {
  const params = new URLSearchParams({
    title: document.getElementById('title').value || '示例短剧',
    genre: document.getElementById('genre').value || '都市情感',
    visual_style: document.getElementById('visual-style').value || 'high consistency anime cinematic',
    tone: document.getElementById('premise').value || '高张力、强反转',
  });
  const res = await fetch(`/api/animation/scene-assets?${params.toString()}`, { headers: authHeaders() });
  const data = await res.json();
  document.getElementById('asset-box').textContent = JSON.stringify(data, null, 2);
  setStatus('场景资产库已加载');
}


async function loadSceneFlow() {
  const title = document.getElementById('title').value || '示例短剧';
  const goal = document.getElementById('episode-goal').value || '关系公开却被打断';
  const resp = await fetch(`/api/animation/scene-flow?body_title=${encodeURIComponent(title)}&goal=${encodeURIComponent(goal)}`, { headers: authHeaders() });
  const data = await resp.json();
  document.getElementById('scene-flow-output').textContent = JSON.stringify(data, null, 2);
}

async function loadBatchAssets() {
  const taskId = activeTaskId || document.getElementById('task-id').textContent.trim();
  if (!taskId) {
    setStatus('还没有可查询的 task_id / batch_task_id');
    return;
  }
  const resp = await fetch(`/api/animation/batch-assets/${encodeURIComponent(taskId)}`, { headers: authHeaders() });
  const data = await resp.json();
  document.getElementById('batch-assets-output').textContent = JSON.stringify(data, null, 2);
}


async function loadRelationshipGraph() {
  const title = document.getElementById('title').value.trim();
  const goal = document.getElementById('episode-goal').value.trim();
  const res = await fetch(`/api/animation/relationship-graph?title=${encodeURIComponent(title)}&goal=${encodeURIComponent(goal)}`, {
    headers: authHeaders(),
  });
  const data = await res.json();
  document.getElementById('relationship-preview').textContent = JSON.stringify(data, null, 2);
  return data;
}

async function loadStoryMemory() {
  const taskId = activeTaskId || document.getElementById('task-id').textContent.trim();
  if (!taskId) {
    setStatus('请先生成一个批量任务，或者选择最近任务。');
    return;
  }
  const res = await fetch(`/api/animation/memory/${encodeURIComponent(taskId)}`, {
    headers: authHeaders(),
  });
  const data = await res.json();
  document.getElementById('relationship-preview').textContent = JSON.stringify(data, null, 2);
  return data;
}


async function runOutlineEditor() {
  const payload = {
    title: document.getElementById('title').value.trim(),
    core_premise: document.getElementById('premise').value.trim(),
    episode_goal: document.getElementById('episode-goal').value.trim(),
    scene_count: Number(document.getElementById('scene-count').value || 4),
    batch_parent_id: document.getElementById('batch-parent-id') ? document.getElementById('batch-parent-id').value.trim() : '',
  };
  setStatus('正在生成剧情大纲编辑建议…');
  const resp = await fetch('/api/animation/outline-editor', { method: 'POST', headers: headersJson(), body: JSON.stringify(payload) });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || '剧情大纲编辑失败');
  document.getElementById('outline-preview').textContent = JSON.stringify(data.outline, null, 2);
  setStatus('剧情大纲编辑建议已生成');
}

async function loadSeasonMemory() {
  const batchId = document.getElementById('batch-parent-id') ? document.getElementById('batch-parent-id').value.trim() : '';
  if (!batchId) {
    setStatus('请先填写 batch_parent_id / 季度级记忆ID');
    return;
  }
  setStatus('正在读取季度级记忆库…');
  const resp = await fetch(`/api/animation/season-memory/${encodeURIComponent(batchId)}`, { headers: authHeaders() });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || '读取季度级记忆库失败');
  document.getElementById('season-memory-preview').textContent = JSON.stringify(data.season_memory, null, 2);
  setStatus('季度级记忆库已加载');
}

document.getElementById('btn-outline')?.addEventListener('click', () => runOutlineEditor().catch(err => setStatus(err.message)));
document.getElementById('btn-season-memory')?.addEventListener('click', () => loadSeasonMemory().catch(err => setStatus(err.message)));


async function loadDialogueStyles() {
  const title = document.getElementById('title').value.trim() || '示例短剧';
  const goal = document.getElementById('episode-goal').value.trim() || '关系升级却不敢表白';
  const resp = await fetch(`/api/animation/dialogue-styles?title=${encodeURIComponent(title)}&goal=${encodeURIComponent(goal)}`, { headers: authHeaders() });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || '对白风格器加载失败');
  document.getElementById('dialogue-style-preview').textContent = JSON.stringify(data, null, 2);
  setStatus('角色对白风格器已加载');
}

async function loadSeasonConflictTree() {
  const seasonId = document.getElementById('batch-parent-id')?.value.trim();
  if (!seasonId) {
    setStatus('请先填写 batch_parent_id / 季度ID');
    return;
  }
  const resp = await fetch(`/api/animation/season-conflict/${encodeURIComponent(seasonId)}`, { headers: authHeaders() });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || '季级剧情冲突树加载失败');
  document.getElementById('season-conflict-preview').textContent = JSON.stringify(data.season_conflict_tree || data, null, 2);
  setStatus('季级剧情冲突树已加载');
}

document.getElementById('btn-dialogue-style')?.addEventListener('click', () => loadDialogueStyles().catch(err => setStatus(err.message)));
document.getElementById('btn-season-conflict')?.addEventListener('click', () => loadSeasonConflictTree().catch(err => setStatus(err.message)));


async function previewScenePacing() {
  setStatus('正在生成分场节奏控制...');
  try {
    const res = await fetch('/api/animation/projects/scene-pacing', {
      method: 'POST',
      headers: headersJson(),
      body: JSON.stringify(buildPayload()),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    document.getElementById('pacing-preview').textContent = JSON.stringify(data, null, 2);
    setStatus('分场节奏控制已生成。');
  } catch (error) {
    setStatus(`分场节奏生成失败：${error.message}`);
  }
}

async function previewClimaxPlan() {
  setStatus('正在生成高潮点编排...');
  try {
    const res = await fetch('/api/animation/projects/climax-plan', {
      method: 'POST',
      headers: headersJson(),
      body: JSON.stringify(buildPayload()),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    document.getElementById('climax-preview').textContent = JSON.stringify(data, null, 2);
    setStatus('高潮点编排已生成。');
  } catch (error) {
    setStatus(`高潮点编排失败：${error.message}`);
  }
}

async function previewEmotionArcs() {
  const title = encodeURIComponent(document.getElementById('title').value || '示例短剧');
  const goal = encodeURIComponent(document.getElementById('goal').value || document.getElementById('premise').value || '关系失控');
  const res = await fetch(`/api/animation/emotion-arcs?title=${title}&goal=${goal}`, { headers: authHeaders() });
  const data = await res.json();
  document.getElementById('emotion-arcs-preview').textContent = JSON.stringify(data, null, 2);
  setStatus('已生成情绪弧线预览');
}

async function previewPunchlines() {
  const title = encodeURIComponent(document.getElementById('title').value || '示例短剧');
  const goal = encodeURIComponent(document.getElementById('goal').value || document.getElementById('premise').value || '正面冲突');
  const res = await fetch(`/api/animation/punchline-dialogue?title=${title}&goal=${goal}`, { headers: authHeaders() });
  const data = await res.json();
  document.getElementById('punchline-preview').textContent = JSON.stringify(data, null, 2);
  setStatus('已生成爆点台词预览');
}

document.getElementById('btn-emotion-arcs')?.addEventListener('click', previewEmotionArcs);
document.getElementById('btn-punchlines')?.addEventListener('click', previewPunchlines);


async function previewSceneTwists() {
  const title = encodeURIComponent(document.getElementById('title').value || '示例短剧');
  const goal = encodeURIComponent(currentGoal('真相反转'));
  const res = await fetch(`/api/animation/scene-twists?title=${title}&goal=${goal}`, { headers: authHeaders() });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '场景反转检测失败');
  document.getElementById('scene-twists-preview').textContent = JSON.stringify(data, null, 2);
  setStatus('已生成场景反转检测结果');
}

async function previewHighlightShots() {
  const title = encodeURIComponent(document.getElementById('title').value || '示例短剧');
  const goal = encodeURIComponent(currentGoal('公开身份反转'));
  const res = await fetch(`/api/animation/highlight-shots?title=${title}&goal=${goal}`, { headers: authHeaders() });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '爆点镜头编排失败');
  document.getElementById('highlight-shots-preview').textContent = JSON.stringify(data, null, 2);
  setStatus('已生成爆点镜头编排结果');
}

document.getElementById('btn-scene-twists')?.addEventListener('click', () => previewSceneTwists().catch(err => setStatus(err.message)));
document.getElementById('btn-highlight-shots')?.addEventListener('click', () => previewHighlightShots().catch(err => setStatus(err.message)));


async function previewShotEmotionFilters() {
  const title = encodeURIComponent(document.getElementById('title').value || '示例短剧');
  const goal = encodeURIComponent(currentGoal('当众摊牌前气氛持续升温'));
  const res = await fetch(`/api/animation/shot-emotion-filters?title=${title}&goal=${goal}`, { headers: authHeaders() });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '镜头情绪滤镜预览失败');
  document.getElementById('shot-emotion-filters-preview').textContent = JSON.stringify(data, null, 2);
  setStatus('已生成镜头情绪滤镜预览');
}

async function previewForeshadowPlan() {
  const title = encodeURIComponent(document.getElementById('title').value || '示例短剧');
  const goal = encodeURIComponent(currentGoal('反转前先埋下线索'));
  const res = await fetch(`/api/animation/foreshadow-plan?title=${title}&goal=${goal}`, { headers: authHeaders() });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '反转前埋点预览失败');
  document.getElementById('foreshadow-preview').textContent = JSON.stringify(data, null, 2);
  setStatus('已生成反转前埋点规划');
}

async function previewPayoffTracker() {
  const title = encodeURIComponent(document.getElementById('title').value || '示例短剧');
  const goal = encodeURIComponent(currentGoal('高潮处完成线索回收'));
  const res = await fetch(`/api/animation/payoff-tracker?title=${title}&goal=${goal}`, { headers: authHeaders() });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '回收追踪预览失败');
  document.getElementById('payoff-tracker-preview').textContent = JSON.stringify(data, null, 2);
  setStatus('已生成回收追踪预览');
}

document.getElementById('btn-shot-emotion-filters')?.addEventListener('click', () => previewShotEmotionFilters().catch(err => setStatus(err.message)));
document.getElementById('btn-foreshadow-plan')?.addEventListener('click', () => previewForeshadowPlan().catch(err => setStatus(err.message)));
document.getElementById('btn-payoff-tracker')?.addEventListener('click', () => previewPayoffTracker().catch(err => setStatus(err.message)));


async function loadSuspenseKeeper() {
  const title = document.getElementById('title')?.value?.trim() || '示例短剧';
  const goal = currentGoal();
  const res = await fetch(`/api/animation/suspense-keeper?title=${encodeURIComponent(title)}&goal=${encodeURIComponent(goal)}`, { headers: authHeaders() });
  const data = await res.json();
  document.getElementById('suspense-keeper-preview').textContent = JSON.stringify(data, null, 2);
  setStatus('已生成悬念保持预览');
}

async function loadPayoffStrength() {
  const title = document.getElementById('title')?.value?.trim() || '示例短剧';
  const goal = currentGoal();
  const res = await fetch(`/api/animation/payoff-strength?title=${encodeURIComponent(title)}&goal=${encodeURIComponent(goal)}`, { headers: authHeaders() });
  const data = await res.json();
  document.getElementById('payoff-strength-preview').textContent = JSON.stringify(data, null, 2);
  setStatus('已生成回收强度评分预览');
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btn-suspense-keeper')?.addEventListener('click', loadSuspenseKeeper);
  document.getElementById('btn-payoff-strength')?.addEventListener('click', loadPayoffStrength);
});


async function fetchPreviewJson(url, targetId, label) {
  const box = document.getElementById(targetId);
  if (box) box.textContent = `${label} 加载中...`;
  try {
    const resp = await fetch(url, { headers: authHeaders() });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || `${label} 加载失败`);
    if (box) box.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    if (box) box.textContent = `${label} 失败：${error.message}`;
  }
}

async function previewSeasonSuspenseChain() {
  const title = document.getElementById('title')?.value?.trim() || '示例短剧';
  const goal = currentGoal('线索跨集延迟兑现');
  const url = `/api/animation/season-suspense-chain?title=${encodeURIComponent(title)}&goal=${encodeURIComponent(goal)}`;
  await fetchPreviewJson(url, 'season-suspense-chain-preview', '季级悬念链');
}

async function previewFinalePayoffPlan() {
  const title = document.getElementById('title')?.value?.trim() || '示例短剧';
  const goal = currentGoal('终局集需要多线回收');
  const url = `/api/animation/finale-payoff-plan?title=${encodeURIComponent(title)}&goal=${encodeURIComponent(goal)}`;
  await fetchPreviewJson(url, 'finale-payoff-plan-preview', '终局回收规划器');
}

document.getElementById('season-suspense-chain-btn')?.addEventListener('click', previewSeasonSuspenseChain);
document.getElementById('finale-payoff-plan-btn')?.addEventListener('click', previewFinalePayoffPlan);



async function previewSeasonTrailerGenerator() {
  const title = document.getElementById('title')?.value?.trim() || '示例短剧';
  const goal = currentGoal('季终后还要继续吊观众');
  const url = `/api/animation/season-trailer-generator?title=${encodeURIComponent(title)}&goal=${encodeURIComponent(goal)}`;
  await fetchPreviewJson(url, 'season-trailer-generator-preview', '季终预告生成器');
}

async function previewNextSeasonHookPlanner() {
  const title = document.getElementById('title')?.value?.trim() || '示例短剧';
  const goal = currentGoal('结局必须能引出下一季');
  const url = `/api/animation/next-season-hook-planner?title=${encodeURIComponent(title)}&goal=${encodeURIComponent(goal)}`;
  await fetchPreviewJson(url, 'next-season-hook-planner-preview', '下季钩子规划器');
}

document.getElementById('season-trailer-generator-btn')?.addEventListener('click', previewSeasonTrailerGenerator);
document.getElementById('next-season-hook-planner-btn')?.addEventListener('click', previewNextSeasonHookPlanner);

async function loadTrailerEditor() {
  const title = document.getElementById('title')?.value?.trim() || '示例短剧';
  const goal = currentGoal();
  const res = await fetch(`/api/animation/trailer-editor?title=${encodeURIComponent(title)}&goal=${encodeURIComponent(goal)}`, { headers: authHeaders() });
  const data = await res.json();
  const box = document.getElementById('trailer-editor-preview');
  if (box) box.textContent = JSON.stringify(data, null, 2);
  setStatus('已生成预告片剪辑器预览');
}

async function loadNextEpisodeColdOpen() {
  const title = document.getElementById('title')?.value?.trim() || '示例短剧';
  const goal = currentGoal();
  const res = await fetch(`/api/animation/next-episode-cold-open?title=${encodeURIComponent(title)}&goal=${encodeURIComponent(goal)}`, { headers: authHeaders() });
  const data = await res.json();
  const box = document.getElementById('next-episode-cold-open-preview');
  if (box) box.textContent = JSON.stringify(data, null, 2);
  setStatus('已生成下季首集冷开场预览');
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('trailer-editor-btn')?.addEventListener('click', loadTrailerEditor);
  document.getElementById('next-episode-cold-open-btn')?.addEventListener('click', loadNextEpisodeColdOpen);
});
