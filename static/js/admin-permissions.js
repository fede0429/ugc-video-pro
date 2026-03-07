
(function () {
  const state = { users: [], selected: null };

  function escapeHtml(v) {
    return String(v ?? '').replace(/[&<>"]/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[s]));
  }

  function ensureAdmin(payload) {
    const role = payload?.role || payload?.permissions?.role;
    if (payload?.target === '/admin.html' || role === 'admin') return;
  }

  async function boot() {
    try {
      const me = await API.getMe();
      if (me.role !== 'admin') {
        alert('仅管理员可访问');
        location.href = '/index.html';
        return;
      }
      bind();
      const pre = new URLSearchParams(location.search).get('user_id') || '';
      await load(pre);
    } catch (err) {
      alert('请先登录管理员账号');
      location.href = '/index.html';
    }
  }

  function bind() {
    document.getElementById('perm-refresh-btn')?.addEventListener('click', load);
    document.getElementById('perm-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!state.selected) return;
      const payload = {
        access_ugc: document.getElementById('perm-access-ugc').checked,
        access_animation: document.getElementById('perm-access-animation').checked,
        access_testing: document.getElementById('perm-access-testing').checked,
        can_manage_publish: document.getElementById('perm-manage-publish').checked,
        default_project: document.getElementById('perm-default-project').value,
        notes: document.getElementById('perm-notes').value.trim(),
      };
      try {
        await API.updateUserPermissions(state.selected.user_id, payload);
        alert('权限已保存');
        await load(state.selected.user_id);
      } catch (err) {
        alert(err.message || '保存失败');
      }
    });
  }

  async function load(selectUserId = '') {
    const data = await API.getUserPermissions();
    state.users = Array.isArray(data?.items) ? data.items : [];
    if (!state.users.length) {
      document.getElementById('perm-user-list').innerHTML = '<div class="muted">暂无用户</div>';
      return;
    }
    if (!selectUserId) selectUserId = state.selected?.user_id || state.users[0].user_id;
    state.selected = state.users.find(x => x.user_id === selectUserId) || state.users[0];
    renderList();
    renderForm();
  }

  function renderList() {
    const root = document.getElementById('perm-user-list');
    root.innerHTML = state.users.map(user => `
      <div class="user-item ${state.selected?.user_id === user.user_id ? 'active' : ''}" data-id="${escapeHtml(user.user_id)}">
        <div><strong>${escapeHtml(user.display_name || user.email)}</strong></div>
        <div class="muted">${escapeHtml(user.email)} · ${escapeHtml(user.role)}</div>
      </div>
    `).join('');
    root.querySelectorAll('.user-item').forEach(el => el.addEventListener('click', () => {
      state.selected = state.users.find(x => x.user_id === el.dataset.id) || null;
      renderList();
      renderForm();
    }));
  }

  function renderForm() {
    const form = document.getElementById('perm-form');
    const empty = document.getElementById('perm-empty');
    if (!state.selected) {
      form.style.display = 'none';
      empty.style.display = '';
      return;
    }
    form.style.display = '';
    empty.style.display = 'none';
    const user = state.selected;
    const p = user.permissions || {};
    document.getElementById('perm-user-label').value = `${user.display_name || ''} <${user.email}>`;
    document.getElementById('perm-access-ugc').checked = !!p.access_ugc;
    document.getElementById('perm-access-animation').checked = !!p.access_animation;
    document.getElementById('perm-access-testing').checked = !!p.access_testing;
    document.getElementById('perm-manage-publish').checked = !!p.can_manage_publish;
    document.getElementById('perm-default-project').value = p.default_project || (user.role === 'admin' ? 'admin' : 'ugc');
    document.getElementById('perm-notes').value = p.notes || '';
    if (user.role !== 'admin') {
      [...document.getElementById('perm-default-project').options].forEach(opt => {
        opt.disabled = opt.value === 'admin';
      });
    }
  }

  boot();
})();
